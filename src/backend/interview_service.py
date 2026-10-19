import asyncio

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from backend.errors import (
    InterviewError,
    InvalidPresetError,
    SessionNotConfiguredError,
    SessionNotFoundError,
    StorageError,
)
from backend.file import write_json
from backend import preset_service
from backend.storage import data_directory
from schemas import AgentRequest, Candidate, Interviewer, InterviewPreset, TaskState


def graph_config_build(session_id: UUID) -> RunnableConfig:
    """每次按会话 ID 构造配置，不缓存完整 state 或历史 checkpoint_id。"""
    return {"configurable": {"thread_id": str(session_id)}}


async def session_snapshot(graph, session_id: UUID, *, configured: bool = False):
    try:
        snapshot = await graph.aget_state(graph_config_build(session_id))
    except Exception as exc:
        raise InterviewError("读取会话状态失败，请查看后端日志。") from exc
    if not snapshot.values or str(snapshot.values.get("session_id")) != str(session_id):
        raise SessionNotFoundError("会话不存在或已失效，请重新创建会话。")
    if configured and (
        snapshot.values.get("candidate_config") is None
        or snapshot.values.get("interviewer_config") is None
    ):
        raise SessionNotConfiguredError("请先提交面试配置或加载预设。")
    return snapshot


async def create_session(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
) -> UUID:
    session_id = uuid4()
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id), values={"session_id": session_id}
        )
    except Exception as exc:
        raise InterviewError("创建会话失败，请查看后端日志。") from exc
    return session_id


async def configure_session(graph, session_id: UUID, candidate: Candidate, interviewer: Interviewer):
    await session_snapshot(graph, session_id)
    # 保存时使用岗位命名；先校验名称，避免非法路径在状态写入后才失败。
    preset_service.preset_path(f"{candidate.position}.json")
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id),
            values={"candidate_config": candidate, "interviewer_config": interviewer},
            as_node=START,
        )
    except Exception as exc:
        raise InterviewError("更新面试配置失败，请查看后端日志。") from exc
    try:
        await save_preset_from_session(graph, session_id)
    except InterviewError as exc:
        # 状态更新与文件保存不是事务，明确告知已发生的部分成功。
        raise InterviewError("会话配置已更新，但预设保存失败，请查看后端日志。") from exc


async def run_turn(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
    request: AgentRequest,
) -> AsyncIterator[dict[str, Any]]:
    """逐条产出节点更新；流式错误由 HTTP 层包装成 SSE error。"""
    await session_snapshot(graph, request.session_id, configured=True)
    await save_state_snapshot(graph, request.session_id)
    state_update = {
        "session_id": request.session_id,
        "messages": [HumanMessage(content=request.message)],
    }
    try:
        async for chunk in graph.astream(
            state_update, graph_config_build(request.session_id), stream_mode="updates"
        ):
            yield chunk
    except Exception as exc:
        # CancelledError 不属于 Exception，客户端取消会继续向上传播。
        raise InterviewError("面试执行失败，请查看后端日志。") from exc


async def save_state_snapshot(graph, session_id: UUID):
    """保存执行前快照；导出失败时本轮不继续执行模型。"""
    snapshot = await session_snapshot(graph, session_id)
    path = data_directory("state_status") / f"{session_id}.json"
    try:
        await asyncio.to_thread(write_json, path, jsonable_encoder(snapshot._asdict()))
    except (OSError, TypeError, ValueError) as exc:
        raise StorageError("保存会话快照失败，请查看后端日志。") from exc


async def save_preset_from_session(graph, session_id: UUID):
    snapshot = await session_snapshot(graph, session_id, configured=True)
    try:
        preset = InterviewPreset.model_validate(snapshot.values)
    except ValidationError as exc:
        raise InvalidPresetError("会话配置不符合预设格式，无法保存。") from exc
    await asyncio.to_thread(preset_service.save_preset, preset)


async def load_preset_into_session(graph, session_id: UUID, filename: str) -> dict[str, Any]:
    await session_snapshot(graph, session_id)
    preset = await asyncio.to_thread(preset_service.read_preset, filename)
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id),
            values={
                "candidate_config": preset.candidate_config,
                "interviewer_config": preset.interviewer_config,
            },
            as_node=START,
        )
    except Exception as exc:
        raise InterviewError("将预设写入会话失败，请查看后端日志。") from exc
    return preset.model_dump(mode="json")
