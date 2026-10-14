import asyncio, os

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Coroutine
from uu import Error
from uuid import UUID, uuid4
from fastapi.encoders import jsonable_encoder

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from schemas import AgentRequest, TaskState
from backend.file import write_json, write_unique_json


def graph_config_build(session_id: UUID) -> RunnableConfig:
    """ 每次按会话 ID 构造配置，不缓存完整 state 或历史 checkpoint_id。"""
    return {"configurable": {"thread_id": str(session_id)}}

async def create_session(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
) -> UUID:
    """创建会话的业务入口；初始状态保存留待实现。"""
    session_id = uuid4()
    return session_id

async def run_turn(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
    request: AgentRequest,
) -> AsyncIterator[dict[str, Any]]:
    """逐条产出节点状态更新；HTTP 层负责包装成 SSE 事件。"""
    config = graph_config_build(request.session_id)
    await save_state_snapshot(graph, request.session_id)
    # 只提交本次输入，历史状态由 checkpointer 按 thread_id 加载。
    state_update = {
        "session_id": request.session_id,
        "messages": [HumanMessage(content=request.message)],
    }
    async for chunk in graph.astream(state_update, config, stream_mode="updates"):
        yield chunk

async def save_state_snapshot(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
    session_id: UUID,
):
    """ 将一次session id标注的graph执行前的checkpoint保存到session id文件中 """
    try: 
        root_path: Path = Path(os.environ.get("data_dir")) / "state_status"
        config = graph_config_build(session_id=session_id)
        snapshot = await graph.aget_state(config=config)
        path: Path = root_path / Path(f"{session_id}.json")
        await asyncio.to_thread(write_json, path, jsonable_encoder(snapshot._asdict()))
    except Error as exc:
        raise()
    
async def save_interview_preset(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
    session_id: UUID
):  
    """ 保存用户使用的面试信息，便于复用和测试 """
    try:
        root_path: Path = Path(os.environ.get("data_dir")) / "interview_preset"
        config = graph_config_build(session_id=session_id)
        snapshot = await graph.aget_state(config=config)
        preset = snapshot._asdict().get("values", ValueError)
        path: Path = root_path / Path(f"{preset["candidate_config"].position}.json")
        jsonable_preset = jsonable_encoder(preset)
        await asyncio.to_thread(
            write_unique_json,
            path,
            {key: jsonable_preset[key] for key in jsonable_preset.keys() if key in ["candidate_config", "interviewer_config"]}
        )

    except ValueError as exc:
        raise(f"{exc}")