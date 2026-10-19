import json
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend.cli import create_app
from backend.errors import SessionEndedError
from backend.interview_service import create_session, data_directory, end_session, graph_config_build, session_snapshot
from interview_agent.agent import InterviewAgent
from interview_agent.graph_builder import graph_build
from runtime import Runtime


def make_client() -> tuple[TestClient, object, AsyncMock]:
    llm = AsyncMock(spec=BaseChatModel)
    llm.ainvoke.side_effect = lambda _: AIMessage(content="这是面试官回复。")
    graph = graph_build(InMemorySaver(), interview_agent=InterviewAgent(llm=llm))
    return TestClient(create_app(Runtime(graph))), graph, llm


def configure(client: TestClient, session_id: str):
    return client.post(
        "/interview/personal_information_config",
        json={
            "session_id": session_id,
            "candidate": {"language": "zh-CN", "education": "本科", "position": "后端工程师", "resume": None},
            "interviewer": {"role_identity": "技术面试官", "role_responsibilities": "围绕项目追问"},
        },
    )


def sse_details(body: str) -> list[str]:
    return [json.loads(line.removeprefix("data: "))["detail"] for line in body.splitlines() if line.startswith("data: ")]


class InterviewHttpContractTests(TestCase):
    def setUp(self):
        self.data_root = TemporaryDirectory()
        self.addCleanup(self.data_root.cleanup)
        self.environment = patch.dict("os.environ", {"DATA_DIR": self.data_root.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client, self.graph, self.llm = make_client()
        self.addCleanup(self.client.close)

    def begin(self) -> str:
        response = self.client.get("/interview/begin")
        self.assertEqual(response.status_code, 200)
        return response.json()["session_id"]

    def test_configured_session_continues_history_and_server_owns_round(self):
        session_id = self.begin()
        self.assertEqual(configure(self.client, session_id).json(), 200)

        for message in ("我做过 FastAPI 项目。", "我也处理过异常边界。"):
            with self.client.stream(
                "POST", "/interview/stream", json={"session_id": session_id, "message": message}
            ) as response:
                self.assertEqual(response.status_code, 200)
                body = "".join(response.iter_text())
            self.assertIn("event: message", body)
            self.assertIn("event: done", body)
            self.assertNotIn("event: error", body)

        # 测试图内状态而非客户端传入轮次，确认两轮人类消息和两轮 Agent 回复均被续接。
        import asyncio
        snapshot = asyncio.run(self.graph.aget_state(graph_config_build(UUID(session_id))))
        self.assertEqual(snapshot.values["chat_round"], 2)
        self.assertEqual(len(snapshot.values["messages"]), 4)

    def test_missing_and_unconfigured_sessions_return_the_defined_error_channel(self):
        missing = str(uuid4())
        with self.client.stream(
            "POST", "/interview/stream", json={"session_id": missing, "message": "你好"}
        ) as response:
            missing_body = "".join(response.iter_text())
        self.assertIn("event: error", missing_body)
        self.assertNotIn("event: done", missing_body)
        self.assertIn("会话不存在或已失效", "\n".join(sse_details(missing_body)))

        session_id = self.begin()
        with self.client.stream(
            "POST", "/interview/stream", json={"session_id": session_id, "message": "你好"}
        ) as response:
            unconfigured_body = "".join(response.iter_text())
        self.assertIn("event: error", unconfigured_body)
        self.assertIn("请先提交面试配置", "\n".join(sse_details(unconfigured_body)))
        self.assertNotIn("event: done", unconfigured_body)

    def test_ended_session_is_gone_and_cannot_be_reconfigured_or_streamed(self):
        session_id = self.begin()
        response = self.client.post("/interview/end", json={"session_id": session_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"session_id": session_id, "status": "ended"})

        response = configure(self.client, session_id)
        self.assertEqual(response.status_code, 410)
        self.assertIn("面试已结束", response.json()["detail"])
        with self.client.stream(
            "POST", "/interview/stream", json={"session_id": session_id, "message": "继续"}
        ) as response:
            body = "".join(response.iter_text())
        self.assertIn("event: error", body)
        self.assertIn("面试已结束", "\n".join(sse_details(body)))
        self.assertNotIn("event: done", body)

    def test_stream_request_rejects_legacy_and_blank_fields_before_sse_starts(self):
        session_id = self.begin()
        response = self.client.post(
            "/interview/stream",
            json={"session_id": session_id, "message": "  ", "role": "Human", "chat_round": 0},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.headers["content-type"].split(";", 1)[0], "application/json")

    def test_snapshot_write_failure_is_an_sse_error_not_a_done_event(self):
        session_id = self.begin()
        self.assertEqual(configure(self.client, session_id).status_code, 200)
        with patch("backend.interview_service.write_json", side_effect=OSError("disk full")):
            with self.client.stream(
                "POST", "/interview/stream", json={"session_id": session_id, "message": "你好"}
            ) as response:
                body = "".join(response.iter_text())
        self.assertIn("event: error", body)
        self.assertIn("保存会话快照失败", "\n".join(sse_details(body)))
        self.assertNotIn("event: done", body)

    def test_graph_failure_is_an_sse_error_not_a_done_event(self):
        session_id = self.begin()
        self.assertEqual(configure(self.client, session_id).status_code, 200)
        self.llm.ainvoke.side_effect = RuntimeError("model unavailable")
        with self.client.stream(
            "POST", "/interview/stream", json={"session_id": session_id, "message": "你好"}
        ) as response:
            body = "".join(response.iter_text())
        self.assertIn("event: error", body)
        self.assertIn("面试执行失败", "\n".join(sse_details(body)))
        self.assertNotIn("event: done", body)

    def test_preset_save_failure_is_a_json_error_before_a_stream_is_started(self):
        session_id = self.begin()
        with patch("backend.interview_service.write_unique_json", side_effect=OSError("disk full")):
            response = configure(self.client, session_id)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["content-type"].split(";", 1)[0], "application/json")
        self.assertIn("预设保存失败", response.json()["detail"])


class InterviewServiceBoundaryTests(TestCase):
    def test_custom_data_root_is_created_and_used_consistently(self):
        with TemporaryDirectory() as root, patch.dict("os.environ", {"DATA_DIR": root}, clear=True):
            self.assertEqual(data_directory("state_status"), (Path(root) / "state_status").resolve())

    def test_end_marks_state_and_subsequent_snapshot_is_rejected(self):
        async def verify():
            llm = AsyncMock(spec=BaseChatModel)
            graph = graph_build(InMemorySaver(), interview_agent=InterviewAgent(llm=llm))
            session_id = await create_session(graph)
            await end_session(graph, session_id)
            with self.assertRaises(SessionEndedError):
                await session_snapshot(graph, session_id)

        import asyncio
        asyncio.run(verify())
