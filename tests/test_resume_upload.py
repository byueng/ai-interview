import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend.cli import create_app
from backend import interview_service
from backend.resume_service import MAX_RESUME_BYTES
from runtime import Runtime
from schemas import TaskState

PDF = b"%PDF-1.7\nresume bytes\n%%EOF\n"
CONFIG = {
    "candidate_config": {"language": "zh-CN", "education": "本科", "position": "后端"},
    "interviewer_config": {"role_identity": "面试官", "role_responsibilities": "技术面试"},
}


class ResumeUploadTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        environment = patch.dict("os.environ", {"DATA_DIR": str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)
        logger = patch("backend.cli.logger")
        logger.start()
        self.addCleanup(logger.stop)
        self.session = uuid4()
        self.values = {"session_id": str(self.session), "status": "active", "last_activity": time.time()}
        self.graph = Mock()
        self.graph.aget_state = AsyncMock(side_effect=lambda *_: SimpleNamespace(values=self.values))
        async def update(*, config, values, as_node):
            self.values.update(values)
        self.graph.aupdate_state = AsyncMock(side_effect=update)
        self.client = AsyncClient(
            transport=ASGITransport(app=create_app(Runtime(self.graph)), raise_app_exceptions=False),
            base_url="http://test",
        )
        self.addAsyncCleanup(self.client.aclose)

    async def save(self, filename="resume.pdf", content=PDF, config=None):
        data = {"session_id": str(self.session), "config": json.dumps(config or CONFIG)}
        files = {"file": (filename, content, "application/pdf")} if filename else None
        return await self.client.post("/interview/personal_information_config", data=data, files=files)

    async def test_one_request_saves_pdf_session_configuration_and_preset(self):
        response = await self.save()
        self.assertEqual(response.status_code, 200, response.text)
        path = self.root / "swap" / str(self.session) / "简历.pdf"
        self.assertEqual(response.json(), {"session_id": str(self.session), "resume": str(path)})
        self.assertEqual(path.read_bytes(), PDF)
        self.assertEqual(self.values["candidate_config"]["resume"], str(path))
        preset = json.loads((self.root / "interview_preset" / "后端.json").read_text())
        self.assertEqual(preset["candidate_config"]["position"], "后端")
        self.assertIsNone(preset["candidate_config"]["resume"])
        self.graph.aupdate_state.assert_awaited_once()

    async def test_optional_pdf_and_config_only_resave_preserves_existing_resume(self):
        response = await self.save(filename=None)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["resume"])
        uploaded = await self.save()
        response = await self.save(filename=None)
        self.assertEqual(response.json(), uploaded.json())
        self.assertEqual(Path(response.json()["resume"]).read_bytes(), PDF)

    async def test_fixed_name_replacement_and_session_isolation(self):
        first = await self.save(filename="../../resume.pdf")
        path = Path(first.json()["resume"])
        second = await self.save(content=PDF + b"updated")
        self.assertEqual(second.json(), first.json())
        self.session = uuid4()
        self.values = {"session_id": str(self.session), "status": "active", "last_activity": time.time()}
        other = await self.save()
        self.assertEqual(other.status_code, 200, other.text)
        self.assertNotEqual(other.json()["resume"], str(path))
        self.assertEqual(path.read_bytes(), PDF + b"updated")
        self.assertEqual(Path(other.json()["resume"]).read_bytes(), PDF)

    async def test_invalid_files_do_not_save_configuration_or_preset(self):
        for filename, content, status in (
            ("resume.txt", PDF, 400), ("empty.pdf", b"", 400),
            ("fake.pdf", b"plain text", 400),
            ("large.pdf", b"%PDF-" + b"x" * MAX_RESUME_BYTES, 413),
        ):
            response = await self.save(filename=filename, content=content)
            self.assertEqual(response.status_code, status, response.text)
        self.graph.aupdate_state.assert_not_awaited()
        self.assertFalse(list(self.root.rglob("*.pdf")))
        self.assertFalse(list(self.root.rglob("*.json")))

    async def test_invalid_configuration_is_rejected_before_file_save(self):
        for config in ('{broken', json.dumps({"candidate_config": {}})):
            response = await self.client.post("/interview/personal_information_config", data={
                "session_id": str(self.session), "config": config,
            }, files={"file": ("resume.pdf", PDF, "application/pdf")})
            self.assertEqual(response.status_code, 422, response.text)
        bad = {**CONFIG, "candidate_config": {**CONFIG["candidate_config"], "position": "../invalid"}}
        self.assertEqual((await self.save(config=bad)).status_code, 400)
        self.graph.aupdate_state.assert_not_awaited()
        self.assertFalse(list(self.root.rglob("*.pdf")))

    async def test_missing_ended_and_busy_sessions_cannot_save(self):
        original = self.values
        for values, status in (({}, 404), ({**original, "status": "ended"}, 410)):
            self.values = values
            self.assertEqual((await self.save()).status_code, status)
        self.values = original
        async with interview_service.session_operation(self.graph, self.session):
            self.assertEqual((await self.save()).status_code, 409)
        self.assertFalse(list(self.root.rglob("*.pdf")))
        self.graph.aupdate_state.assert_not_awaited()

    async def test_storage_error_preserves_old_pdf_and_does_not_update_config(self):
        saved = await self.save()
        path = Path(saved.json()["resume"])
        self.graph.aupdate_state.reset_mock()
        with patch("backend.resume_service.Path.open", side_effect=PermissionError("private path")):
            response = await self.save(content=PDF + b"updated")
        self.assertEqual(response.status_code, 500)
        self.assertIn("保存简历失败", response.json()["detail"])
        self.assertNotIn("private path", response.text)
        self.assertEqual(path.read_bytes(), PDF)
        self.graph.aupdate_state.assert_not_awaited()

    async def test_later_failures_are_reported_as_partial_save_not_success(self):
        with patch.object(self.graph, "aupdate_state", side_effect=RuntimeError("private error")):
            response = await self.save()
        self.assertEqual(response.status_code, 500)
        self.assertIn("简历已暂存", response.json()["detail"])
        with patch("backend.preset_service.save_preset", side_effect=interview_service.StorageError("failed")):
            response = await self.save()
        self.assertEqual(response.status_code, 500)
        self.assertIn("预设保存失败", response.json()["detail"])

    async def test_preset_loading_keeps_only_current_session_resume(self):
        saved = await self.save()
        loaded = await interview_service.load_preset_into_session(self.graph, self.session, "后端.json")
        self.assertEqual(loaded["candidate_config"]["resume"], saved.json()["resume"])
        self.session = uuid4()
        self.values = {"session_id": str(self.session), "status": "active", "last_activity": time.time()}
        loaded = await interview_service.load_preset_into_session(self.graph, self.session, "后端.json")
        self.assertIsNone(loaded["candidate_config"]["resume"])

    async def test_client_cannot_attach_arbitrary_server_path(self):
        config = {**CONFIG, "candidate_config": {**CONFIG["candidate_config"], "resume": "/tmp/other.pdf"}}
        response = await self.save(filename=None, config=config)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["resume"])

    async def test_real_checkpoint_restores_saved_resume_without_running_agent(self):
        builder = StateGraph(TaskState)
        builder.add_node("idle", lambda state: {})
        builder.add_edge(START, "idle")
        builder.add_edge("idle", END)
        graph = builder.compile(checkpointer=InMemorySaver())
        async with AsyncClient(transport=ASGITransport(app=create_app(Runtime(graph))), base_url="http://test") as client:
            session = (await client.get("/interview/begin")).json()["session_id"]
            saved = await client.post("/interview/personal_information_config", data={
                "session_id": session, "config": json.dumps(CONFIG),
            }, files={"file": ("resume.pdf", PDF, "application/pdf")})
            self.assertEqual(saved.status_code, 200, saved.text)
            restored = await client.get(f"/interview/sessions/{session}")
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertEqual(restored.json()["candidate_config"]["resume"], saved.json()["resume"])
            self.assertEqual(Path(saved.json()["resume"]).read_bytes(), PDF)


    async def test_loading_then_uploading_pdf_does_not_create_duplicate_preset(self):
        response = await self.save(filename=None)
        self.assertEqual(response.status_code, 200)
        directory = self.root / "interview_preset"
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
        loaded = await self.client.post("/interview/load_preset?filename=后端.json", json=str(self.session))
        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertEqual({p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}, before)
        for _ in range(2):
            self.assertEqual((await self.save()).status_code, 200)
        self.assertEqual({p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}, before)

    async def test_analysis_cache_is_invalidated_only_when_its_inputs_change(self):
        await self.save()
        self.values["resume_evalute"] = "cached analysis"
        await self.save(filename=None)
        self.assertEqual(self.values["resume_evalute"], "cached analysis")
        await interview_service.load_preset_into_session(self.graph, self.session, "后端.json")
        self.assertEqual(self.values["resume_evalute"], "cached analysis")
        await self.save(content=PDF + b"updated")
        self.assertIsNone(self.values["resume_evalute"])
        self.values["resume_evalute"] = "updated analysis"
        changed = {**CONFIG, "candidate_config": {**CONFIG["candidate_config"], "position": "前端"}}
        await self.save(filename=None, config=changed)
        self.assertIsNone(self.values["resume_evalute"])
        self.values["resume_evalute"] = "frontend analysis"
        await interview_service.load_preset_into_session(self.graph, self.session, "后端.json")
        self.assertIsNone(self.values["resume_evalute"])
