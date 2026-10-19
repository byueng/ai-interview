from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from langchain_core.messages import AnyMessage
from typing import Literal
from typing_extensions import Annotated, List
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.types import UUID
from langgraph.graph.message import add_messages

class SessionResponse(BaseModel):
    session_id: UUID # 标识


class EndSessionRequest(BaseModel):
    session_id: UUID


class AgentRequest(BaseModel):
    """一次候选人回答的最小请求体。

    会话轮次和时间由 Graph 状态与服务端生成，消息角色固定为候选人回答，
    因而不接受客户端传入的 role、chat_round、dtime。
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message 不能为空。")
        return value

class AgentResponse(BaseModel):
    role: str # 标注Human或者System
    message: str # 对话历史
    chat_round: int # 对话轮数，一轮对话为Response返回
    dtime: datetime # response创建时间
    score: float # 得分
    chat_status: bool # 面试进程

    @field_validator("chat_status")
    @classmethod
    def validate_chat_status(cls, value: bool) -> bool:
        if value not in [True, False]:
            raise ValueError("Response chat_status must be True or False")
        return value

class Candidate(BaseModel):
    language: str # 使用语言
    education: str # 学历
    position: str # 面试岗位
    resume: Path | None = None


class Interviewer(BaseModel):
    role_identity: str # 面试官身份
    role_responsibilities: str | None # 面试官的偏好设置


class InterviewPreset(BaseModel):
    candidate_config: Candidate
    interviewer_config: Interviewer

@dataclass
class TaskState:
    session_id: UUID # 对话标识
    messages: Annotated[List[AnyMessage], add_messages] = field(default_factory=list) # 信息
    # 已完成的 Agent 回复次数：0 使用开场模板，每次成功回复后加 1。
    chat_round: int = 0 
    candidate_config: Candidate | None = None # 候选人信息
    interviewer_config: Interviewer | None = None # 面试官信息
    dtime: datetime = field(default_factory=datetime.now) # 会话创建时间
    session_status: Literal["active", "ended"] = "active"
