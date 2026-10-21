
from langchain_core.messages import SystemMessage, AIMessage

from schemas import Candidate, Interviewer, TaskState
from agent_system.prompts.prompt_faction import render_prompt
from agent_system.agent import Agent, InterviewUpdate

class InterviewAgent(Agent):
    def load_prompt(self, state: TaskState) -> str:
        if state.candidate_config is None or state.interviewer_config is None:
            raise ValueError("单次对话需要 candidate_config 和 interviewer_config。")
        if state.chat_round < 0:
            raise ValueError("chat_round 必须从 0 开始。")
        template_path = "init_interview.md" if state.chat_round == 0 else "interview_round.md"
        candidate = Candidate.model_validate(state.candidate_config)
        interviewer = Interviewer.model_validate(state.interviewer_config)
        return render_prompt(
            template_path,
            **interviewer.model_dump(),
            **candidate.model_dump(exclude={"resume"}),
            # 此处只使用已有简历文本；不自动读取用户提供的文件路径。
            resume=str(candidate.resume or "未提供"),
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