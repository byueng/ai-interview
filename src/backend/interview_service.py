import asyncio
import json
import os

from collections.abc import AsyncIterator
from pathlib import Path
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
    InvalidPresetNameError,
    PresetNotFoundError,
    SessionEndedError,
    SessionNotConfiguredError,
    SessionNotFoundError,
    StorageError,
)
from backend.file import read_json, write_json, write_unique_json
from schemas import AgentRequest, Candidate, Interviewer, InterviewPreset, TaskState


def graph_config_build(session_id: UUID) -> RunnableConfig:
    """每次按会话 ID 构造配置，不缓存完整 state 或历史 checkpoint_id。"""
    return {"configurable": {"thread_id": str(session_id)}}


def data_directory(name: str) -> Path:
    """所有文件流程共用同一数据根目录，并在首次写入前初始化父目录。"""
    root = os.environ.get("DATA_DIR") or os.environ.get("data_dir")
    # 默认随源码定位，避免因启动目录不同把数据写到不可预期的位置。
    root_path = Path(root).expanduser() if root and root.strip() else Path(__file__).resolve().parents[1] / "data"
    try:
        directory = root_path.resolve() / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    except (OSError, RuntimeError, ValueError) as exc:
        raise StorageError("数据目录初始化失败，请查看后端日志。") from exc


def preset_path(filename: str) -> Path:
    if (
        not filename.endswith(".json")
        or len(filename) <= 5
        or any(c in filename for c in ("/", "\\"))
        or any(ord(c) < 32 or ord(c) == 127 for c in filename)
    ):
        raise InvalidPresetNameError("预设文件名无效，请提供单个 JSON 文件名。")
    directory = data_directory("interview_preset")
    path = directory / filename
    try:
        if path.is_symlink() or path.resolve().parent != directory:
            raise InvalidPresetNameError("预设路径无效。")
    except (OSError, RuntimeError, ValueError) as exc:
        raise StorageError("预设路径检查失败，请查看后端日志。") from exc
    return path


async def session_snapshot(
    graph, session_id: UUID, *, configured: bool = False, allow_ended: bool = False
):
    try:
        snapshot = await graph.aget_state(graph_config_build(session_id))
    except Exception as exc:
        raise InterviewError("读取会话状态失败，请查看后端日志。") from exc
    if not snapshot.values or str(snapshot.values.get("session_id")) != str(session_id):
        raise SessionNotFoundError("会话不存在或已失效，请重新创建会话。")
    if not allow_ended and snapshot.values.get("session_status") == "ended":
        raise SessionEndedError("面试已结束，请创建新会话后继续。")
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
            config=graph_config_build(session_id),
            values={"session_id": session_id, "session_status": "active"},
        )
    except Exception as exc:
        raise InterviewError("创建会话失败，请查看后端日志。") from exc
    return session_id


async def end_session(graph, session_id: UUID) -> None:
    """结束当前进程内会话；InMemorySaver 重启后缺失的会话按失效处理。"""
    await session_snapshot(graph, session_id)
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id),
            values={"session_status": "ended"},
            as_node=START,
        )
    except Exception as exc:
        raise InterviewError("结束面试失败，请查看后端日志。") from exc


async def configure_session(graph, session_id: UUID, candidate: Candidate, interviewer: Interviewer):
    await session_snapshot(graph, session_id)
    # 保存时使用岗位命名；先校验名称，避免非法路径在状态写入后才失败。
    preset_path(f"{candidate.position}.json")
    try:
        await graph.aupdate_state(
            config=graph_config_build(session_id),
            values={"candidate_config": candidate, "interviewer_config": interviewer},
            as_node=START,
        )
    except Exception as exc:
        raise InterviewError("更新面试配置失败，请查看后端日志。") from exc
    try:
        await save_interview_preset(graph, session_id)
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


async def save_interview_preset(graph, session_id: UUID):
    snapshot = await session_snapshot(graph, session_id, configured=True)
    try:
        preset = InterviewPreset.model_validate(snapshot.values)
    except ValidationError as exc:
        raise InvalidPresetError("会话配置不符合预设格式，无法保存。") from exc
    path = preset_path(f"{preset.candidate_config.position}.json")
    try:
        await asyncio.to_thread(write_unique_json, path, jsonable_encoder(preset))
    except (OSError, TypeError, ValueError) as exc:
        raise StorageError("保存面试预设失败，请查看后端日志。") from exc


def list_interview_presets() -> list[str]:
    directory = data_directory("interview_preset")
    try:
        return sorted(
            path.name for path in directory.iterdir()
            if path.suffix == ".json" and path.is_file() and not path.is_symlink()
        )
    except OSError as exc:
        raise StorageError("读取预设列表失败，请查看后端日志。") from exc


async def load_interview_preset(graph, session_id: UUID, filename: str) -> dict[str, Any]:
    path = preset_path(filename)
    await session_snapshot(graph, session_id)
    try:
        payload = await asyncio.to_thread(read_json, path)
    except FileNotFoundError as exc:
        raise PresetNotFoundError("预设不存在，请刷新预设列表。") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidPresetError("预设文件无法解析，请检查 JSON 内容与 UTF-8 编码。") from exc
    except OSError as exc:
        raise StorageError("读取预设文件失败，请查看后端日志。") from exc
    try:
        preset = InterviewPreset.model_validate(payload)
    except ValidationError as exc:
        raise InvalidPresetError("预设配置缺少字段或类型错误，请检查预设文件。") from exc
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
    return payload


def delete_interview_preset(filename: str):
    path = preset_path(filename)
    try:
        path.unlink()
    except FileNotFoundError as exc:
        raise PresetNotFoundError("预设不存在，请刷新预设列表。") from exc
    except OSError as exc:
        raise StorageError("删除预设失败，请查看后端日志。") from exc
