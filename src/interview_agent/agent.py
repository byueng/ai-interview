from abc import ABC, abstractmethod
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from typing import Any, TypedDict
from dataclasses import asdict, dataclass, field

from interview_agent.model_config import ModelConfig
from schemas import TaskState
from interview_agent.prompts.prompt_faction import render_prompt

def _create_llm() -> BaseChatModel:
    return ChatOpenAI(**asdict(ModelConfig.validate_dotfile()))


class InterviewUpdate(TypedDict):
    messages: list[AIMessage]
    chat_round: int


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

class InterviewAgent(Agent):
    def load_prompt(self, state: TaskState) -> str:
        if state.candidate_config is None or state.interviewer_config is None:
            raise ValueError("单次对话需要 candidate_config 和 interviewer_config。")
        if state.chat_round < 0:
            raise ValueError("chat_round 必须从 0 开始。")
        template_path = "init_interview.md" if state.chat_round == 0 else "interview_round.md"
        return render_prompt(
            template_path,
            **state.interviewer_config.model_dump(),
            **state.candidate_config.model_dump(exclude={"resume"}),
            # 此处只使用已有简历文本；不自动读取用户提供的文件路径。
            resume=str(state.candidate_config.resume or "未提供"),
        )

    async def __call__(self, state: TaskState) -> InterviewUpdate:
        # 模板、模型调用异常保留原始类型和堆栈，由流程层补充上下文。
        prompt = self.load_prompt(state)
        messages = [SystemMessage(content=prompt), *state.messages]
        result = await self.llm.ainvoke(messages)
        if not isinstance(result, AIMessage):
            raise TypeError("面试模型必须返回 AIMessage。")
        # 成功后才返回状态更新；失败不会推进轮次。
        return {"messages": [result], "chat_round": state.chat_round + 1}


class AssessAgent(Agent):
    pass

class EvaluateAgent(Agent):
    pass

class AssistantAgent(Agent):
    def load_prompt(self, *args: Any, **kwargs: Any) -> Any:
        return super().load_prompt(*args, **kwargs)
    
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        pass
