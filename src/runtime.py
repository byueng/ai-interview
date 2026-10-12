from dataclasses import dataclass
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from schemas import TaskState


@dataclass
class Runtime:
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState]

def run_time() -> FastAPI:
    # 在实际组装资源时加载 Agent，避免仅导入 HTTP 层就初始化模型配置。
    from interview_agent.graph_builder import graph_build
    from backend.cli import create_app

    checkpointer = InMemorySaver()
    graph = graph_build(checkpointer)
    runtime = Runtime(graph)
    return create_app(runtime)
