from abc import ABC, abstractmethod
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from typing import Any, TypedDict
from dataclasses import asdict, dataclass, field

from agent_system.model_config import ModelConfig
from schemas import Candidate, Interviewer, TaskState
from agent_system.prompts.prompt_faction import render_prompt

def _create_llm() -> BaseChatModel:
    return ChatOpenAI(**asdict(ModelConfig.validate_dotfile()))

def interview_router(state) -> bool:
    return False

@dataclass
class Agent(ABC):
    # 创建 Agent 时才加载客户端；允许测试注入模型，不在对象上保存会话状态。
    llm: BaseChatModel = field(default_factory=_create_llm)

    @abstractmethod
    def load_prompt(self, *args: Any, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    async def __call__(self, *args: Any, **kwds: Any) -> Any:
        ...

class AssessAgent(Agent):
    pass

class EvaluateAgent(Agent):
    pass

class AssistantAgent(Agent):
    def load_prompt(self, *args: Any, **kwargs: Any) -> Any:
        return super().load_prompt(*args, **kwargs)
    
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        pass
