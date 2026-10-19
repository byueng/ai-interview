"""浏览器验收入口：真实 HTTP/Graph/checkpointer + 确定性模型，无外部凭据。"""
from unittest.mock import AsyncMock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from backend.cli import create_app
from interview_agent.agent import InterviewAgent
from interview_agent.graph_builder import graph_build
from runtime import Runtime


def make_app():
    llm = AsyncMock(spec=BaseChatModel)
    llm.ainvoke.side_effect = lambda messages: AIMessage(content="验收回复：" + messages[-1].content)
    return create_app(Runtime(graph_build(InMemorySaver(), interview_agent=InterviewAgent(llm=llm))))
