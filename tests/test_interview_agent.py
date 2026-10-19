import asyncio
import time
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend.interview_service import run_turn
from interview_agent.agent import InterviewAgent
from interview_agent.graph_builder import graph_build
from interview_agent.model_config import ModelConfig, ModelConfigError
from schemas import AgentRequest, Candidate, Interviewer, TaskState


def make_state(position="后端工程师", chat_round=0):
    return TaskState(
        session_id=uuid4(),
        messages=[HumanMessage(content="你好，准备开始。")],
        chat_round=chat_round,
        candidate_config=Candidate(
            language="中文", education="本科", position=position, resume=None
        ),
        interviewer_config=Interviewer(
            role_identity="技术面试官", role_responsibilities="进行技术面试"
        ),
    )


class InterviewAgentTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.llm = AsyncMock(spec=BaseChatModel)
        self.llm.ainvoke.return_value = AIMessage(content="你好，我们开始面试。")
        self.agent = InterviewAgent(llm=self.llm)

    async def test_opening_binds_config_and_passes_messages_without_mutation(self):
        state = make_state()
        update = await self.agent(state)
        self.llm.ainvoke.assert_awaited_once()
        messages = self.llm.ainvoke.call_args.args[0]
        self.assertIsInstance(messages[0], SystemMessage)
        for text in ("技术面试官", "进行技术面试", "中文", "本科", "后端工程师", "未提供"):
            self.assertIn(text, messages[0].content)
        self.assertIn("开场白", messages[0].content)
        self.assertEqual(messages[1:], state.messages)
        self.assertEqual(update["messages"], [self.llm.ainvoke.return_value])
        self.assertEqual(update["chat_round"], 1)
        self.assertEqual(len(state.messages), 1)
        self.assertEqual(state.chat_round, 0)

    async def test_regular_reply_includes_history(self):
        state = make_state(chat_round=1)
        state.messages.extend([AIMessage(content="请介绍项目。"), HumanMessage(content="我写了 FastAPI 项目。")])
        update = await self.agent(state)
        messages = self.llm.ainvoke.call_args.args[0]
        self.assertIn("最新一条消息", messages[0].content)
        self.assertEqual(messages[1:], state.messages)
        self.assertEqual(update["chat_round"], 2)

    async def test_missing_config_fails_before_model_call(self):
        state = make_state()
        for name in ("candidate_config", "interviewer_config"):
            with self.subTest(field=name):
                state = make_state()
                setattr(state, name, None)
                with self.assertRaisesRegex(ValueError, "candidate_config"):
                    await self.agent(state)
        self.llm.ainvoke.assert_not_awaited()

    async def test_negative_round_fails_before_model_call(self):
        with self.assertRaisesRegex(ValueError, "chat_round"):
            await self.agent(make_state(chat_round=-1))
        self.llm.ainvoke.assert_not_awaited()

    async def test_shared_agent_does_not_store_request_state(self):
        first, second = make_state("岗位A"), make_state("岗位B")
        await asyncio.gather(self.agent(first), self.agent(second))
        prompts = [call.args[0][0].content for call in self.llm.ainvoke.call_args_list]
        self.assertIn("岗位A", prompts[0])
        self.assertNotIn("岗位B", prompts[0])
        self.assertIn("岗位B", prompts[1])
        self.assertNotIn("岗位A", prompts[1])
        self.assertEqual(set(vars(self.agent)), {"llm"})

    async def test_model_error_propagates_without_updating_state(self):
        self.llm.ainvoke.side_effect = RuntimeError("model unavailable")
        state = make_state()
        with self.assertRaisesRegex(RuntimeError, "model unavailable"):
            await self.agent(state)
        self.assertEqual(state.chat_round, 0)
        self.assertEqual(len(state.messages), 1)

    async def test_graph_runs_only_interview_node_then_ends(self):
        state = make_state()
        state.candidate_config = state.candidate_config.model_dump(mode="json")
        state.interviewer_config = state.interviewer_config.model_dump(mode="json")
        graph = graph_build(InMemorySaver(), interview_agent=self.agent)
        config = {"configurable": {"thread_id": str(state.session_id)}}
        chunks = [chunk async for chunk in graph.astream(state, config, stream_mode="updates")]
        self.assertEqual(len(chunks), 1)
        self.assertEqual(set(chunks[0]), {"InterviewAgent"})
        snapshot = await graph.aget_state(config)
        self.assertEqual(snapshot.next, ())
        self.assertEqual(snapshot.values["chat_round"], 1)
        self.assertEqual(len(snapshot.values["messages"]), 2)
        self.llm.ainvoke.assert_awaited_once()

    async def test_existing_service_can_consume_single_node_updates(self):
        # 测试夹具写入配置，不代表 /begin 或个人信息接口已经实现该逻辑。
        state = make_state()
        graph = graph_build(InMemorySaver(), interview_agent=self.agent)
        config = {"configurable": {"thread_id": str(state.session_id)}}
        await graph.aupdate_state(config, {
            "session_id": state.session_id,
            "candidate_config": state.candidate_config.model_dump(mode="json"),
            "interviewer_config": state.interviewer_config.model_dump(mode="json"),
            "last_activity": time.time(),
            "chat_round": 0,
        })
        request = AgentRequest(
            session_id=state.session_id, message="你好", chat_round=0,
        )
        with TemporaryDirectory() as data_root, patch.dict("os.environ", {"data_dir": data_root}):
            chunks = [chunk async for chunk in run_turn(graph, request)]
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["InterviewAgent"]["chat_round"], 1)
        self.assertEqual(self.llm.ainvoke.call_args.args[0][-1].content, "你好")


class DefaultsAndConfigTests(TestCase):
    def test_message_defaults_are_independent(self):
        first, second = TaskState(uuid4()), TaskState(uuid4())
        first.messages.append(HumanMessage(content="A"))
        self.assertEqual(second.messages, [])

    def test_config_reads_environment_and_numeric_temperature(self):
        # .env 由 main 加载，模型配置只读取进程环境变量。
        with patch.dict(
            "os.environ", {"API_KEY": "test", "BASE_URL": "https://example.invalid/v1", "MODEL_NAME": "fake", "TEMPERATURE": "0.6"}, clear=True
        ):
            config = ModelConfig.validate_dotfile()
        self.assertEqual(config.api_key, "test")
        self.assertEqual(config.temperature, 0.6)

    def test_missing_key_raises_configuration_error(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ModelConfigError):
                ModelConfig.validate_dotfile()

    def test_invalid_temperature_raises_configuration_error(self):
        with patch.dict("os.environ", {"TEMPERATURE": "bad"}, clear=True):
            with self.assertRaisesRegex(ModelConfigError, "TEMPERATURE"):
                ModelConfig.validate_dotfile()
