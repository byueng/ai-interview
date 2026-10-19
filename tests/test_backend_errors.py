import asyncio
import json
import time
from collections import namedtuple
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend.cli import create_app
from backend.errors import InterviewError, StorageError
from backend.interview_service import run_turn, save_state_snapshot
from backend.storage import data_directory
from interview_agent.agent import InterviewAgent
from interview_agent.graph_builder import graph_build
from runtime import Runtime
from schemas import AgentRequest


Snapshot = namedtuple("Snapshot", "values")
PRESET = {
    "candidate_config": {"language": "中文", "education": "本科", "position": "后端", "resume": None},
    "interviewer_config": {"role_identity": "技术面试官", "role_responsibilities": None},
}


class FakeGraph:
    """模拟检查点成功路径；每项故障测试只替换失败的操作。"""

    def __init__(self):
        self.states = {}
        self.updates = []
        self.stream_calls = 0

    async def aget_state(self, config):
        return Snapshot(self.states.get(config["configurable"]["thread_id"], {}).copy())

    async def aupdate_state(self, config, values, as_node=None):
        self.updates.append(values)
        self.states.setdefault(config["configurable"]["thread_id"], {}).update(values)
        return config

    async def astream(self, values, config, stream_mode):
        self.stream_calls += 1
        yield {"InterviewAgent": {"chat_round": 1}}


class BackendErrorTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.environment = patch.dict("os.environ", {"DATA_DIR": temporary.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.graph = FakeGraph()
        self.client = TestClient(create_app(Runtime(self.graph)), raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.session = str(uuid4())
        self.graph.states[self.session] = {"session_id": self.session, "status": "active", "last_activity": time.time(), "chat_round": 0}
        self.logger_patch = patch("backend.cli.logger")
        self.logger = self.logger_patch.start()
        self.addCleanup(self.logger_patch.stop)
        stream_logger = patch("backend.interview_routes.logger")
        stream_logger.start()
        self.addCleanup(stream_logger.stop)

    def save_preset(self, content=None):
        path = self.root / "interview_preset" / "后端.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(PRESET) if content is None else content, encoding="utf-8")
        return path

    def load(self, filename="后端.json", session=None):
        return self.client.post(
            "/interview/load_preset", params={"filename": filename},
            json=self.session if session is None else session,
        )

    def configure(self, session=None, candidate=None):
        return self.client.post("/interview/personal_information_config", json={
            "session_id": self.session if session is None else session,
            "candidate": PRESET["candidate_config"] if candidate is None else candidate,
            "interviewer": PRESET["interviewer_config"],
        })

    def stream(self, session=None):
        return self.client.post("/interview/stream", json={
            "session_id": self.session if session is None else session,
            "message": "你好", "chat_round": 0,
        })

    def configured(self):
        self.graph.states[self.session].update(PRESET)

    def test_health_and_begin_success_contract(self):
        self.assertEqual(self.client.get("/").json(), {"status": "ok"})
        response = self.client.get("/interview/begin")
        self.assertEqual(response.status_code, 200)
        session = UUID(response.json()["session_id"])
        self.assertEqual(self.graph.states[str(session)]["session_id"], str(session))

    def test_begin_failure_is_json_500_with_original_cause_logged(self):
        with patch.object(self.graph, "aupdate_state", side_effect=RuntimeError("private db path")):
            response = self.client.get("/interview/begin")
        self.assertEqual(response.status_code, 500)
        self.assertIn("创建会话失败", response.json()["detail"])
        self.assertNotIn("private db path", response.text)
        logged = self.logger.error.call_args.kwargs["exc_info"][1]
        self.assertIsInstance(logged.__cause__, RuntimeError)

    def test_request_validation_remains_422_and_does_not_write_state(self):
        for response in (
            self.load(session="not-a-uuid"),
            self.client.post("/interview/load_preset", json=self.session),
            self.client.post("/interview/load_preset", params={"filename": "后端.json"}, json={"session_id": self.session}),
            self.client.post("/interview/personal_information_config", json={"session_id": self.session}),
            self.client.post("/interview/stream", json={"session_id": "bad"}),
            self.client.post("/interview/del_preset"),
        ):
            self.assertEqual(response.status_code, 422)
            self.assertIsInstance(response.json()["detail"], list)
        self.assertEqual(self.graph.updates, [])

    def test_missing_data_dir_uses_project_default(self):
        # Patch directory creation so checking the fallback never writes to project data.
        with patch.dict("os.environ", {}, clear=True), patch("backend.storage.Path.mkdir") as mkdir:
            directory = data_directory("interview_preset")
        import backend.storage as storage
        expected = Path(storage.__file__).resolve().parents[1] / "data" / "interview_preset"
        self.assertEqual(directory, expected)
        mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_data_directory_creation_permission_error(self):
        with patch("backend.storage.Path.mkdir", side_effect=PermissionError("private path")):
            response = self.client.get("/interview/read_preset")
        self.assertEqual(response.status_code, 500)
        self.assertIn("目录初始化失败", response.json()["detail"])

    def test_list_initially_empty_and_filters_non_files(self):
        self.assertEqual(self.client.get("/interview/read_preset").json(), {"files": []})
        self.save_preset()
        directory = self.root / "interview_preset"
        (directory / "notes.txt").touch()
        (directory / "folder.json").mkdir()
        self.assertEqual(self.client.get("/interview/read_preset").json(), {"files": ["后端.json"]})

    def test_list_io_error_is_500(self):
        with patch("backend.preset_service.Path.iterdir", side_effect=PermissionError()):
            response = self.client.get("/interview/read_preset")
        self.assertEqual(response.status_code, 500)
        self.assertIn("列表失败", response.json()["detail"])

    def test_load_success_updates_same_session_and_keeps_response_contract(self):
        self.save_preset()
        response = self.load()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"preset_config": PRESET})
        self.assertEqual(self.graph.states[self.session]["candidate_config"]["position"], "后端")

    def test_load_missing_file_is_404_without_state_change(self):
        response = self.load()
        self.assertEqual(response.status_code, 404)
        self.assertIn("预设不存在", response.json()["detail"])
        self.assertEqual(self.graph.updates, [])

    def test_unknown_session_is_404_for_load_and_configure(self):
        self.save_preset()
        for response in (self.load(session=str(uuid4())), self.configure(session=str(uuid4()))):
            self.assertEqual(response.status_code, 404)
            self.assertIn("会话不存在", response.json()["detail"])
        self.assertEqual(self.graph.updates, [])

    def test_load_rejects_unsafe_filename_before_touching_state(self):
        for filename in ("../private.json", "folder/a.json", "folder\\a.json", "a.txt", ".json", "bad\x00.json"):
            with self.subTest(filename=filename):
                self.assertEqual(self.load(filename).status_code, 400)
        self.assertEqual(self.graph.updates, [])

    def test_symlink_presets_are_not_read_or_deleted(self):
        target = self.root / "outside.json"
        target.write_text(json.dumps(PRESET), encoding="utf-8")
        directory = self.root / "interview_preset"
        directory.mkdir()
        (directory / "link.json").symlink_to(target)
        self.assertEqual(self.load("link.json").status_code, 400)
        self.assertEqual(self.client.post("/interview/del_preset", params={"filename": "link.json"}).status_code, 400)
        self.assertTrue(target.exists())
        self.assertTrue((directory / "link.json").is_symlink())

    def test_corrupt_json_and_invalid_config_never_update_state(self):
        for content in ("{broken", "null", "[]", "{}", json.dumps({**PRESET, "candidate_config": {}})):
            with self.subTest(content=content):
                self.save_preset(content)
                response = self.load()
                self.assertEqual(response.status_code, 500)
                self.assertIn("预设", response.json()["detail"])
        self.assertEqual(self.graph.updates, [])

    def test_invalid_utf8_is_preset_data_error(self):
        self.save_preset().write_bytes(b"\xff")
        response = self.load()
        self.assertEqual(response.status_code, 500)
        self.assertIn("UTF-8", response.json()["detail"])

    def test_load_permission_error_is_not_404(self):
        self.save_preset()
        with patch("backend.preset_service.read_json", side_effect=PermissionError("private path")):
            response = self.load()
        self.assertEqual(response.status_code, 500)
        self.assertIn("读取预设文件失败", response.json()["detail"])

    def test_checkpoint_read_failure_is_server_error(self):
        with patch.object(self.graph, "aget_state", side_effect=RuntimeError("private state error")):
            response = self.configure()
        self.assertEqual(response.status_code, 500)
        self.assertIn("读取会话状态失败", response.json()["detail"])

    def test_load_checkpoint_update_failure_is_not_reported_as_success(self):
        self.save_preset()
        with patch.object(self.graph, "aupdate_state", side_effect=RuntimeError("private checkpoint error")):
            response = self.load()
        self.assertEqual(response.status_code, 500)
        self.assertIn("写入会话失败", response.json()["detail"])
        self.assertNotIn("private checkpoint error", response.text)

    def test_configure_success_saves_only_configuration(self):
        self.assertEqual(self.configure().json(), 200)
        saved = json.loads((self.root / "interview_preset" / "后端.json").read_text())
        self.assertEqual(saved, PRESET)

    def test_bad_position_filename_does_not_update_session(self):
        response = self.configure(candidate={**PRESET["candidate_config"], "position": "../escape"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.graph.updates, [])

    def test_configure_checkpoint_write_error_prevents_save(self):
        with patch.object(self.graph, "aupdate_state", side_effect=RuntimeError()):
            response = self.configure()
        self.assertEqual(response.status_code, 500)
        self.assertIn("更新面试配置失败", response.json()["detail"])
        self.assertFalse((self.root / "interview_preset" / "后端.json").exists())

    def test_configure_reports_partial_success_when_preset_save_fails(self):
        with patch("backend.preset_service.write_unique_json", side_effect=PermissionError("private path")):
            response = self.configure()
        self.assertEqual(response.status_code, 500)
        self.assertIn("配置已更新，但预设保存失败", response.json()["detail"])
        self.assertIn("candidate_config", self.graph.states[self.session])

    def test_delete_success_and_missing_file(self):
        path = self.save_preset()
        response = self.client.post("/interview/del_preset", params={"filename": path.name})
        self.assertEqual(response.json(), 200)
        self.assertFalse(path.exists())
        self.assertEqual(self.client.post("/interview/del_preset", params={"filename": path.name}).status_code, 404)

    def test_delete_permission_error_retains_file(self):
        path = self.save_preset()
        with patch("backend.preset_service.Path.unlink", side_effect=PermissionError()):
            response = self.client.post("/interview/del_preset", params={"filename": path.name})
        self.assertEqual(response.status_code, 500)
        self.assertTrue(path.exists())

    def test_upload_stub_returns_501(self):
        response = self.client.post("/interview/upload_resume")
        self.assertEqual(response.status_code, 501)
        self.assertIn("未实现", response.json()["detail"])

    def test_unexpected_error_gets_safe_json_and_log(self):
        with patch("backend.preset_service.list_presets", side_effect=RuntimeError("private details")):
            response = self.client.get("/interview/read_preset")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private details", response.text)
        self.assertIn("detail", response.json())
        self.logger.error.assert_called_once()

    def test_stream_success_emits_message_then_done(self):
        self.configured()
        response = self.stream()
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.text.index("event: message"), response.text.index("event: done"))
        self.assertNotIn("event: error", response.text)
        self.assertTrue((self.root / "state_status" / f"{self.session}.json").exists())

    def test_stream_unknown_or_unconfigured_session_emits_only_error(self):
        for session in (self.session, str(uuid4())):
            response = self.stream(session)
            self.assertEqual(response.status_code, 200)
            self.assertIn("event: error", response.text)
            self.assertNotIn("event: done", response.text)
            self.assertNotIn("event: message", response.text)
        self.assertEqual(self.graph.stream_calls, 0)

    def test_stream_snapshot_failure_stops_before_graph_execution(self):
        self.configured()
        with patch("backend.interview_service.write_json", side_effect=PermissionError("private path")):
            response = self.stream()
        data = next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        self.assertIn("快照失败", json.loads(data)["detail"])
        self.assertIn("event: error", response.text)
        self.assertNotIn("event: done", response.text)
        self.assertEqual(self.graph.stream_calls, 0)

    def test_failure_after_first_stream_chunk_emits_error_without_done(self):
        self.configured()

        async def broken_stream(*args, **kwargs):
            yield {"InterviewAgent": {"messages": []}}
            raise RuntimeError("private provider failure")

        with patch.object(self.graph, "astream", broken_stream):
            response = self.stream()
        self.assertIn("event: message", response.text)
        self.assertIn("event: error", response.text)
        self.assertNotIn("event: done", response.text)
        self.assertNotIn("private provider failure", response.text)

    def test_real_graph_session_configuration_load_and_mock_model_stream(self):
        llm = AsyncMock(spec=BaseChatModel)
        llm.ainvoke.return_value = AIMessage(content="你好，我们开始面试。")
        graph = graph_build(InMemorySaver(), interview_agent=InterviewAgent(llm=llm))
        with TestClient(create_app(Runtime(graph))) as client:
            session = client.get("/interview/begin").json()["session_id"]
            self.assertEqual(client.post("/interview/personal_information_config", json={
                "session_id": session,
                "candidate": PRESET["candidate_config"], "interviewer": PRESET["interviewer_config"],
            }).json(), 200)
            self.assertEqual(client.post("/interview/load_preset", params={"filename": "后端.json"}, json=session).status_code, 200)
            response = client.post("/interview/stream", json={
                "session_id": session, "message": "你好", "chat_round": 0,
            })
            self.assertIn("event: done", response.text)
            self.assertNotIn("event: error", response.text)
        llm.ainvoke.assert_awaited_once()


class ServiceErrorTests(IsolatedAsyncioTestCase):
    async def test_snapshot_error_preserves_exception_cause(self):
        graph = FakeGraph()
        session = uuid4()
        graph.states[str(session)] = {"session_id": str(session), "last_activity": time.time()}
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"DATA_DIR": directory}):
            with patch("backend.interview_service.write_json", side_effect=PermissionError("blocked")):
                with self.assertRaises(StorageError) as raised:
                    await save_state_snapshot(graph, session)
        self.assertIsInstance(raised.exception.__cause__, PermissionError)

    async def test_cancellation_propagates_without_becoming_business_error(self):
        graph = FakeGraph()
        session = uuid4()
        graph.states[str(session)] = {"session_id": str(session), "last_activity": time.time(), **PRESET}

        async def cancelled(*args, **kwargs):
            raise asyncio.CancelledError()
            yield

        request = AgentRequest(
            session_id=session, message="你好", chat_round=0,
        )
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"DATA_DIR": directory}):
            with patch.object(graph, "astream", cancelled):
                with self.assertRaises(asyncio.CancelledError):
                    _ = [chunk async for chunk in run_turn(graph, request)]

    async def test_graph_failure_preserves_original_exception(self):
        graph = FakeGraph()
        session = uuid4()
        graph.states[str(session)] = {"session_id": str(session), "last_activity": time.time(), **PRESET}

        async def broken(*args, **kwargs):
            raise RuntimeError("model unavailable")
            yield

        request = AgentRequest(
            session_id=session, message="你好", chat_round=0,
        )
        with TemporaryDirectory() as directory, patch.dict("os.environ", {"DATA_DIR": directory}):
            with patch.object(graph, "astream", broken):
                with self.assertRaises(InterviewError) as raised:
                    _ = [chunk async for chunk in run_turn(graph, request)]
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
