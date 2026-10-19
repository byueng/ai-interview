"""真实 ASGI/FastAPI + LangGraph + InMemorySaver；仅模型使用确定性替身。"""
import asyncio
import json
import logging
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend.cli import create_app
from backend import interview_service as service
from interview_agent.agent import InterviewAgent
from interview_agent.graph_builder import graph_build
from runtime import Runtime
from schemas import AgentRequest


def configuration(session_id, position="岗位A"):
    return {"session_id": session_id,
            "candidate": {"language": "zh-CN", "education": "本科", "position": position},
            "interviewer": {"role_identity": "技术面试官", "role_responsibilities": position}}


def request_body(session_id, message="你好", chat_round=0):
    return {"session_id": session_id, "message": message, "chat_round": chat_round,
            "role": "Human", "dtime": "2026-10-20T00:00:00Z"}


def events(response):
    return [line[7:] for line in response.text.splitlines() if line.startswith("event: ")]


class LifecycleTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict("os.environ", {"data_dir": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.llm = AsyncMock(spec=BaseChatModel)
        self.llm.ainvoke.side_effect = lambda messages: AIMessage(content="回复：" + messages[-1].content)
        self.saver = InMemorySaver()
        self.graph = graph_build(self.saver, interview_agent=InterviewAgent(llm=self.llm))
        self.client = AsyncClient(transport=ASGITransport(app=create_app(Runtime(self.graph))), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def new(self, position="岗位A"):
        response = await self.client.get("/interview/begin")
        self.assertEqual(response.status_code, 200)
        sid = response.json()["session_id"]
        response = await self.client.post("/interview/personal_information_config", json=configuration(sid, position))
        self.assertEqual(response.status_code, 200, response.text)
        return sid

    async def turn(self, sid, message="你好", chat_round=0):
        return await self.client.post("/interview/stream", json=request_body(sid, message, chat_round))

    async def state(self, sid):
        response = await self.client.get(f"/interview/sessions/{sid}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_interleaved_sessions_keep_model_input_and_history_isolated(self):
        a, b = await self.new(), await self.new("岗位B")
        for sid, message, round_ in [(a, "A1", 0), (b, "B1", 0), (a, "A2", 1), (b, "B2", 1)]:
            self.assertEqual(events(await self.turn(sid, message, round_)), ["message", "done"])
        for sid, label, other in [(a, "A", "B"), (b, "B", "A")]:
            state = await self.state(sid)
            self.assertEqual(state["chat_round"], 2)
            self.assertEqual(len(state["messages"]), 4)
            self.assertNotIn(other, json.dumps(state, ensure_ascii=False))
        for call in self.llm.ainvoke.call_args_list:
            messages = call.args[0]
            label = messages[-1].content[0]
            other = "B" if label == "A" else "A"
            self.assertIn("岗位" + label, messages[0].content)
            self.assertNotIn("岗位" + other, messages[0].content)
            self.assertTrue(all(other not in m.content for m in messages[1:]))

    async def test_duplicate_and_stale_round_cannot_append_messages(self):
        sid = await self.new()
        self.assertEqual(events(await self.turn(sid)), ["message", "done"])
        before = await self.state(sid)
        for round_ in [0, 5]:
            self.assertEqual(events(await self.turn(sid, chat_round=round_)), ["error"])
        self.assertEqual((await self.state(sid))["messages"], before["messages"])
        self.assertEqual(self.llm.ainvoke.await_count, 1)

    async def test_same_session_operations_conflict_other_session_progresses(self):
        a, b = await self.new(), await self.new("岗位B")
        entered, release = asyncio.Event(), asyncio.Event()

        async def blocked(messages):
            if messages[-1].content == "hold":
                entered.set()
                await release.wait()
            return AIMessage(content="ok")

        self.llm.ainvoke.side_effect = blocked
        task = asyncio.create_task(self.turn(a, "hold"))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            self.assertEqual(events(await self.turn(a)), ["error"])
            for method, path, body in [
                ("GET", f"/interview/sessions/{a}", None),
                ("POST", f"/interview/sessions/{a}/end", None),
                ("POST", "/interview/personal_information_config", configuration(a)),
                ("POST", "/interview/load_preset?filename=岗位A.json", a),
            ]:
                response = await self.client.request(method, path, json=body)
                self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(events(await self.turn(b)), ["message", "done"])
        finally:
            release.set()
            await task
        self.assertEqual((await self.state(a))["chat_round"], 1)

    async def test_end_is_idempotent_and_blocks_every_session_mutation(self):
        sid = await self.new()
        await self.turn(sid)
        for _ in range(2):
            self.assertEqual((await self.client.post(f"/interview/sessions/{sid}/end")).status_code, 200)
        for method, path, body in [
            ("GET", f"/interview/sessions/{sid}", None),
            ("POST", "/interview/personal_information_config", configuration(sid)),
            ("POST", "/interview/load_preset?filename=岗位A.json", sid),
        ]:
            self.assertEqual((await self.client.request(method, path, json=body)).status_code, 410)
        self.assertEqual(events(await self.turn(sid, chat_round=1)), ["error"])
        self.assertEqual(self.llm.ainvoke.await_count, 1)
        self.assertNotEqual(await self.new(), sid)

    async def test_expiry_boundary_and_restart_never_recreate_old_id(self):
        with patch.object(service.time, "time", return_value=1000):
            sid = await self.new()
        with patch.object(service.time, "time", return_value=1000 + service.SESSION_TTL_SECONDS - 1):
            self.assertEqual((await self.state(sid))["expires_at"], 1000 + service.SESSION_TTL_SECONDS)
        with patch.object(service.time, "time", return_value=1000 + service.SESSION_TTL_SECONDS):
            self.assertEqual((await self.client.get(f"/interview/sessions/{sid}")).status_code, 410)
            self.assertEqual(events(await self.turn(sid)), ["error"])
            self.assertEqual((await self.client.post("/interview/personal_information_config", json=configuration(sid))).status_code, 410)
            self.assertEqual((await self.client.post(f"/interview/sessions/{sid}/end")).status_code, 410)
        fresh_graph = graph_build(InMemorySaver(), interview_agent=InterviewAgent(llm=self.llm))
        async with AsyncClient(transport=ASGITransport(app=create_app(Runtime(fresh_graph))), base_url="http://test") as restarted:
            self.assertEqual((await restarted.get(f"/interview/sessions/{sid}")).status_code, 404)
            self.assertEqual((await restarted.post("/interview/personal_information_config", json=configuration(sid))).status_code, 404)
            self.assertEqual(events(await restarted.post("/interview/stream", json=request_body(sid))), ["error"])
        self.assertFalse((await fresh_graph.aget_state(service.graph_config_build(UUID(sid)))).values)
        self.llm.ainvoke.assert_not_awaited()

    async def test_model_failure_retry_replaces_checkpointed_input(self):
        sid = await self.new()
        self.llm.ainvoke.side_effect = RuntimeError("model offline")
        self.assertEqual(events(await self.turn(sid, "first")), ["error"])
        self.assertEqual((await self.state(sid))["chat_round"], 0)
        self.llm.ainvoke.side_effect = lambda messages: AIMessage(content="recovered")
        self.assertEqual(events(await self.turn(sid, "retry")), ["message", "done"])
        state = await self.state(sid)
        self.assertEqual(state["chat_round"], 1)
        self.assertEqual([m["content"] for m in state["messages"]], ["retry", "recovered"])

    async def test_cancellation_releases_guard_and_retry_is_single_input(self):
        sid = await self.new()
        entered = asyncio.Event()

        async def blocked(messages):
            entered.set()
            await asyncio.Event().wait()

        self.llm.ainvoke.side_effect = blocked
        async def consume():
            return [chunk async for chunk in service.run_turn(self.graph, AgentRequest(**request_body(sid)))]
        task = asyncio.create_task(consume())
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.llm.ainvoke.side_effect = lambda messages: AIMessage(content="ok")
        self.assertEqual(events(await self.turn(sid)), ["message", "done"])
        self.assertEqual(len((await self.state(sid))["messages"]), 2)

    async def test_closing_after_an_update_releases_session(self):
        sid = await self.new()
        stream = service.run_turn(self.graph, AgentRequest(**request_body(sid)))
        await anext(stream)
        await stream.aclose()
        state = await self.state(sid)
        self.assertEqual(events(await self.turn(sid, "继续", state["chat_round"])), ["message", "done"])

    async def test_checkpoint_restore_uses_json_configs_without_custom_revivers(self):
        # 新 Graph 共用同一个真实 saver，验证反序列化及恢复后再次执行。
        with self.assertNoLogs("langgraph.checkpoint.serde.jsonplus", level=logging.WARNING):
            sid = await self.new()
            await self.turn(sid, "before")
            restored = graph_build(self.saver, interview_agent=InterviewAgent(llm=self.llm))
            snapshot = await restored.aget_state(service.graph_config_build(UUID(sid)))
            self.assertIsInstance(snapshot.values["candidate_config"], dict)
            self.assertIsInstance(snapshot.values["interviewer_config"], dict)
            self.assertIsInstance(snapshot.values["messages"][0], HumanMessage)
            chunks = [chunk async for chunk in service.run_turn(restored, AgentRequest(**request_body(sid, "after", 1)))]
            self.assertEqual(chunks[0]["InterviewAgent"]["chat_round"], 2)
            result = await restored.aget_state(service.graph_config_build(UUID(sid)))
            self.assertEqual(len(result.values["messages"]), 4)
            # 预设入口也必须只写普通字典。
            other = await self.client.get("/interview/begin")
            other_id = other.json()["session_id"]
            self.assertEqual((await self.client.post("/interview/load_preset?filename=岗位A.json", json=other_id)).status_code, 200)
            await self.turn(other_id)
            self.assertIsInstance((await self.graph.aget_state(service.graph_config_build(UUID(other_id)))).values["candidate_config"], dict)

    async def test_new_unconfigured_and_unknown_sessions(self):
        sid = (await self.client.get("/interview/begin")).json()["session_id"]
        state = await self.state(sid)
        self.assertEqual(state["messages"], [])
        self.assertIsNone(state["candidate_config"])
        self.assertEqual(events(await self.turn(sid)), ["error"])
        self.assertEqual((await self.client.get(f"/interview/sessions/{uuid4()}")).status_code, 404)
        self.assertEqual((await self.client.get("/interview/sessions/invalid")).status_code, 422)
        self.llm.ainvoke.assert_not_awaited()
