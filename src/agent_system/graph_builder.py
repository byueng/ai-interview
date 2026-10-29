from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent_system.InterviewAgent.interviewagent import InterviewAgent
from schemas import TaskState


def graph_build(
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    interview_agent: InterviewAgent | None = None,
) -> CompiledStateGraph[TaskState, None, TaskState, TaskState]:
    """Build the current single-turn path; allow model injection for tests."""
    graph = StateGraph[TaskState, None, TaskState, TaskState](TaskState)
    agent = interview_agent if interview_agent is not None else InterviewAgent()
    graph.add_node("InterviewAgent", agent.__call__)
    graph.add_edge(START, "InterviewAgent")
    graph.add_edge("InterviewAgent", END)
    return graph.compile(checkpointer=checkpointer)


def studio_graph():
    """Factory referenced by langgraph.json."""
    return graph_build()
