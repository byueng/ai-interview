import asyncio
import time

from contextlib import aclosing, asynccontextmanager
from functools import wraps
from weakref import WeakKeyDictionary

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
    SessionConflictError,
    SessionGoneError,
    StorageError,
)
from backend.file import write_json
from backend import preset_service
from backend.storage import data_directory
from schemas import AgentRequest, Candidate, Interviewer, InterviewPreset, TaskState


SESSION_TTL_SECONDS = 24 * 60 * 60
# 单进程、单事件循环内 check-and-add 无 await；不同 Graph/会话互不阻塞。
_busy_sessions: WeakKeyDictionary = WeakKeyDictionary()


@asynccontextmanager
async def session_operation(graph, session_id: UUID):
    busy = _busy_sessions.setdefault(graph, set())
    key = str(session_id)
    if key in busy:
        raise SessionConflictError("该会话正在处理请求，请等待完成后再继续。")
    busy.add(key)
    try:
        yield
    finally:
        busy.remove(key)


def exclusive_session(function):
    @wraps(function)
    async def wrapped(graph, session_id, *args, **kwargs):
        async with session_operation(graph, session_id):
            return await function(graph, session_id, *args, **kwargs)
    return wrapped


def graph_config_build(session_id: UUID) -> RunnableConfig:
    """每次按会话 ID 构造配置，不缓存完整 state 或历史 checkpoint_id。"""
    return {"configurable": {"thread_id": str(session_id)}}


async def session_snapshot(graph, session_id: UUID, *, configured: bool = False, allow_ended: bool = False):
    try:
        snapshot = await graph.aget_state(graph_config_build(session_id))
    except Exception as exc:
        raise InterviewError("读取会话状态失败，请查看后端日志。") from exc
    if not snapshot.values or str(snapshot.values.get("session_id")) != str(session_id):
        raise SessionNotFoundError("会话不存在或已失效，请重新创建会话。")
    if snapshot.values.get("status", "active") == "ended":
        if not allow_ended:
            raise SessionGoneError("会话已结束，请主动新建会话。")
    elif time.time() >= snapshot.values.get("last_activity", 0) + SESSION_TTL_SECONDS:
            raise SessionGoneError("会话已过期，请主动新建会话。")
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
            config=graph_config_build(session_id), values={
                "session_id": str(session_id), "status": "active",
                "last_activity": time.time(), "chat_round": 0, "messages": [],
            }, as_node=START,
        )
    except Exception as exc:
        raise InterviewError("创建会话失败，请查看后端日志。") from exc
    return session_id


@exclusive_session
async def configure_session(graph, session_id: UUID, candidate: Candidate, interviewer: Interviewer):
    await session_snapshot(graph, session_id)
    # 保存时使用岗位命名；先校验名称，避免非法路径在状态写入后才失败。
    preset_service.preset_path(f"{candidate.position}.json")
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id),
            values={"candidate_config": candidate.model_dump(mode="json"),
                    "interviewer_config": interviewer.model_dump(mode="json"),
                    "last_activity": time.time()},
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
    async with session_operation(graph, request.session_id):
        snapshot = await session_snapshot(graph, request.session_id, configured=True)
        if request.chat_round != snapshot.values.get("chat_round", 0):
            raise SessionConflictError("轮次已变化或请求已提交，请继续会话以同步最新历史。")
        await save_state_snapshot(graph, request.session_id)
        state_update = {
            "session_id": str(request.session_id),
            # 失败重试替换同一轮的输入，避免 LangGraph 已保存的输入重复追加。
            "messages": [HumanMessage(content=request.message, id=f"{request.session_id}:human:{request.chat_round}")],
            "last_activity": time.time(),
        }
        try:
            async with aclosing(graph.astream(
                state_update, graph_config_build(request.session_id), stream_mode="updates"
            )) as stream:
                async for chunk in stream:
                    yield chunk
            await graph.aupdate_state(graph_config_build(request.session_id), {"last_activity": time.time()})
        except Exception as exc:
            # CancelledError 继续向上传播；finally 会释放会话占用。
            raise InterviewError(f"面试执行失败，请查看后端日志， detail: {exc}。") from exc


@exclusive_session
async def read_session(graph, session_id: UUID) -> dict[str, Any]:
    snapshot = await session_snapshot(graph, session_id)
    values = snapshot.values
    return {
        "session_id": str(session_id), "status": values.get("status", "active"),
        "chat_round": values.get("chat_round", 0),
        "expires_at": values["last_activity"] + SESSION_TTL_SECONDS,
        "candidate_config": values.get("candidate_config"),
        "interviewer_config": values.get("interviewer_config"),
        "messages": jsonable_encoder(values.get("messages", [])),
    }


@exclusive_session
async def end_session(graph, session_id: UUID):
    snapshot = await session_snapshot(graph, session_id, allow_ended=True)
    if snapshot.values.get("status") != "ended":
        await graph.aupdate_state(graph_config_build(session_id), {"status": "ended"}, as_node=START)
    return {"session_id": str(session_id), "status": "ended"}


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


@exclusive_session
async def load_preset_into_session(graph, session_id: UUID, filename: str) -> dict[str, Any]:
    await session_snapshot(graph, session_id)
    preset = await asyncio.to_thread(preset_service.read_preset, filename)
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id),
            values={
                "candidate_config": preset.candidate_config.model_dump(mode="json"),
                "interviewer_config": preset.interviewer_config.model_dump(mode="json"),
                "last_activity": time.time(),
            },
            as_node=START,
        )
    except Exception as exc:
        raise InterviewError("将预设写入会话失败，请查看后端日志。") from exc
    return preset.model_dump(mode="json")
