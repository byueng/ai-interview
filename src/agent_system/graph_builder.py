from typing_extensions import List

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from agent_system.InterviewAgent.interviewagent import InterviewAgent
from agent_system.agent import Agent
# need move
from agent_system.agent import AssistantAgent, EvaluateAgent, AssessAgent, interview_router
from agent_system.InterviewAgent.interviewagent import InterviewAgent

from schemas import TaskState

AGENTS: List[Agent] = [
    InterviewAgent,
    AssistantAgent,
    # AssessAgent,
    # EvaluateAgent
]

def node_build(graph, _cls):
    agent = _cls()
    graph.add_node(
        _cls.__name__,
        agent.__call__
    )

def graph_build(
    checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph[TaskState, None, TaskState, TaskState]:
    """当前只执行一次面试回复；评估与循环调度待后续接入。"""
    graph = StateGraph[TaskState, None, TaskState, TaskState](TaskState)
    
    for _cls in AGENTS:
        node_build(graph, _cls)

    graph.add_edge(START, "InterviewAgent")
    # graph.add_edge("InterviewAgent", "AssistantAgent")
    # graph.add_edge("AssistantAgent", "InterviewAgent")
    graph.add_edge("InterviewAgent", END)
    # graph.add_conditional_edges("InterviewAgent", interview_router, {"True": END, "False": END})
    return graph.compile(checkpointer=checkpointer)

def studio_graph():
    """ using in langgraph.json """
    return graph_build()