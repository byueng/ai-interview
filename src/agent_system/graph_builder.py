from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from agent_system.InterviewAgent.interviewagent import InterviewAgent
from schemas import TaskState


def graph_build(
    checkpointer: BaseCheckpointSaver,
    *,
    interview_agent: InterviewAgent | None = None,
) -> CompiledStateGraph[TaskState, None, TaskState, TaskState]:
    """当前只执行一次面试回复；评估与循环调度待后续接入。"""
    agent = interview_agent if interview_agent is not None else InterviewAgent()
    graph = StateGraph[TaskState, None, TaskState, TaskState](TaskState)
    graph.add_node("InterviewAgent", agent.__call__)
    graph.add_edge(START, "InterviewAgent")
    graph.add_edge("InterviewAgent", END)
    return graph.compile(checkpointer=checkpointer)