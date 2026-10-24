from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.types import UUID
from typing_extensions import Annotated, List


class SessionResponse(BaseModel):
    session_id: UUID


class SessionStateResponse(SessionResponse):
    status: str
    chat_round: int
    expires_at: float
    candidate_config: Candidate | None = None
    interviewer_config: Interviewer | None = None
    messages: list[dict[str, Any]]


class AgentRequest(BaseModel):
    """候选人单轮回答；轮次是并发/重复提交控制的一部分。"""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    message: str
    chat_round: int

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message 不能为空。")
        return value

    @field_validator("chat_round")
    @classmethod
    def validate_chat_round(cls, value: int) -> int:
        if value < 0:
            raise ValueError("chat_round 必须是非负整数。")
        return value


class AgentResponse(BaseModel):
    role: str
    message: str
    chat_round: int
    dtime: datetime
    score: float
    chat_status: bool


class Candidate(BaseModel):
    language: str
    education: str
    position: str
    resume: Path | None = None


class Interviewer(BaseModel):
    role_identity: str
    role_responsibilities: str | None


class InterviewPreset(BaseModel):
    candidate_config: Candidate
    interviewer_config: Interviewer


@dataclass
class TaskState:
    session_id: UUID
    messages: Annotated[List[AnyMessage], add_messages] = field(default_factory=list)
    chat_round: int = 0
    # 检查点写入 JSON 字典；Agent 在使用边界重新执行 Pydantic 校验。
    candidate_config: dict[str, Any] | Candidate | None = None
    interviewer_config: dict[str, Any] | Interviewer | None = None
    status: str = "active"
    last_activity: float = 0
    dtime: datetime = field(default_factory=datetime.now)

@dataclass
class Runtime:
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState]