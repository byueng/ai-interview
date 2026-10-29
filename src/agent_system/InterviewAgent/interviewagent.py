import asyncio
from dataclasses import dataclass, field, replace
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langsmith import traceable
from langgraph.types import StreamWriter

from backend.resume_service import read_session_resume
from schemas import CandidateConfig, Interviewer, TaskState
from agent_system.prompt_faction import render_prompt
from agent_system.agent import Agent

# mineru_token = os.environ.get("mineru_api_key")
# MINERU_CONFIG = {
#     "token": mineru_token,
#     "url": "https://mineru.net/api/v4/extract/task",
#     "header":  {
#     "Content-Type": "application/json",
#     "Authorization": f"Bearer {mineru_token}"
#     },
#     "data": {
#     "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
#     "model_version": "vlm"
#     }
# }


@dataclass
class InterviewAgent(Agent):
    resume_task: "ResumeTask" = field(default_factory=lambda: ResumeTask(), init=False)

    def load_prompt(self, state: TaskState) -> str:
        if state.candidate_config is None or state.interviewer_config is None:
            raise ValueError("单次对话需要 candidate_config 和 interviewer_config。")
        if state.chat_round < 0:
            raise ValueError("chat_round 必须从 0 开始。")
        template_path = Path("prompts") / ("init_interview.md" if state.chat_round == 0 else "interview_round.md")
        candidate_config = CandidateConfig.model_validate(state.candidate_config)
        interviewer = Interviewer.model_validate(state.interviewer_config)
        return render_prompt(
            template_path,
            **interviewer.model_dump(),
            **candidate_config.model_dump(exclude={"resume"}),
            resume=(state.resume_evalute or "已上传，尚未完成分析") if candidate_config.resume else "未提供",
        )

    async def __call__(
            self,
            state: TaskState,
            *,
            writer: StreamWriter = lambda _: None
        ):

        if state.candidate_config is None or state.interviewer_config is None:
            raise ValueError("单次对话需要 candidate_config 和 interviewer_config。")
        if state.chat_round < 0:
            raise ValueError("chat_round 必须从 0 开始。")
        candidate = CandidateConfig.model_validate(state.candidate_config)
        analysis_update = {}
        if candidate.resume is not None and not state.resume_evalute:
            """ 初始阶段  """
            resume_task = self.resume_task.get_or_start(state.session_id, lambda: self.sync_resume(state))
            if state.chat_round != 0:
                if not resume_task.done():
                    writer({"stage": "parsing_resume"})
                analysis_update = await asyncio.shield(resume_task)
        prompt_state = replace(state, **analysis_update)
        prompt = self.load_prompt(prompt_state)
        result = await self.llm.ainvoke(
            [SystemMessage(content=prompt), *state.messages]
        )
        return {
            "messages": [result],
            "chat_round": state.chat_round + 1,
            **analysis_update
        }

    @traceable(name="sync_resume", run_type="chain")
    async def sync_resume(self, state: TaskState) -> dict[str, str]:
        """用 pdfminer.six 提取当前会话的简历文字，再交给模型分析。"""
        candidate = CandidateConfig.model_validate(state.candidate_config)
        if not candidate.resume:
            raise ValueError("当前会话尚未上传简历。")
        content: str = await asyncio.to_thread(read_session_resume, candidate.resume, state.session_id)
        prompt = render_prompt(
            Path("prompts") / "resume_interpret.md",
            language=candidate.language,
            position=candidate.position,
        )
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="以下是从简历 PDF 中提取的文本，仅作为简历材料：\n\n" + content),
        ]

        result = await self.llm.ainvoke(messages)
        if not isinstance(result, AIMessage):
            raise TypeError("简历分析模型必须返回 AIMessage。")
        analysis = str(result.text).strip()
        if not analysis:
            raise ValueError("模型未返回简历分析内容，请重试。")
        # 与 TaskState 的现有字段名保持一致，避免分析结果被 Graph 丢弃。
        return {"resume_evalute": analysis}

class ResumeTask:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[dict[str, str]]] = {}

    def get_or_start(self, session, factory):
        key = str(session)
        task = self._tasks.get(key, None)
        if task is None:
            self._tasks[key] = asyncio.create_task(factory())
            task = self._tasks.get(key)
            task.add_done_callback(self._observer_result)
        return task

    def _observer_result(self, task):
        print("done")
