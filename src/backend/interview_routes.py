import logging

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.graph.state import CompiledStateGraph

from backend import interview_service
from backend.errors import InterviewError
from schemas import AgentRequest, Candidate, Interviewer, TaskState


logger = logging.getLogger(__name__)


def create_interview_router(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState]
) -> APIRouter:
    router = APIRouter(prefix="/interview", tags=["interview"])

    @router.get("/begin", status_code=200)
    async def interview_begin():
        session_id = await interview_service.create_session(graph)
        return {"session_id": session_id}

    @router.post("/stream", status_code=200, response_class=EventSourceResponse)
    async def stream_turn(agent_request: AgentRequest, request: Request) -> AsyncIterator[ServerSentEvent]:
        try:
            async for chunk in interview_service.run_turn(graph, agent_request):
                yield ServerSentEvent(event="message", data=jsonable_encoder(chunk))
        except InterviewError as exc:
            logger.exception("面试流处理失败，session_id=%s", agent_request.session_id)
            yield ServerSentEvent(event="error", data={"detail": str(exc)})
            return
        except Exception:
            logger.exception("面试流发生未预期异常，session_id=%s", agent_request.session_id)
            yield ServerSentEvent(event="error", data={"detail": "面试处理失败，请查看后端日志。"})
            return
        yield ServerSentEvent(event="done", data={"session_id": str(agent_request.session_id)})

    @router.post("/personal_information_config", status_code=200)
    async def personal_information_config(
        session_id: Annotated[UUID, Body()], candidate: Candidate,
        interviewer: Interviewer, request: Request,
    ):
        request.state.session_id = str(session_id)
        await interview_service.configure_session(graph, session_id, candidate, interviewer)
        return 200

    @router.post("/upload_resume", status_code=200)
    async def upload_resume():
        raise HTTPException(status_code=501, detail="简历上传暂未实现。")

    return router
