import logging
from contextlib import aclosing

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import Json
from fastapi.encoders import jsonable_encoder
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.graph.state import CompiledStateGraph

from backend import interview_service
from backend.errors import InterviewError
from schemas import AgentRequest, InterviewPreset, TaskState, SessionResponse, SessionStateResponse


logger = logging.getLogger(__name__)


def create_interview_router(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState]
) -> APIRouter:
    router = APIRouter(prefix="/interview", tags=["interview"])

    @router.get("/begin", status_code=200, response_model=SessionResponse)
    async def interview_begin():
        session_id = await interview_service.create_session(graph)
        return {"session_id": session_id}

    @router.get("/sessions/{session_id}", response_model=SessionStateResponse)
    async def continue_session(session_id: UUID):
        return await interview_service.read_session(graph, session_id)

    @router.post("/sessions/{session_id}/end")
    async def end_session(session_id: UUID):
        return await interview_service.end_session(graph, session_id)

    @router.post("/stream", status_code=200, response_class=EventSourceResponse)
    async def stream_turn(agent_request: AgentRequest, request: Request) -> AsyncIterator[ServerSentEvent]:
        request.state.session_id = str(agent_request.session_id)
        try:
            async with aclosing(interview_service.run_turn(graph, agent_request, include_progress=True)) as stream:
                async for chunk in stream:
                    if "__progress__" in chunk:
                        yield ServerSentEvent(event="progress", data={
                            "session_id": str(agent_request.session_id), **chunk["__progress__"],
                        })
                    else:
                        yield ServerSentEvent(event="message", data=jsonable_encoder(chunk))
        except InterviewError as exc:
            logger.warning("面试流未完成，session_id=%s detail=%s", agent_request.session_id, exc,
                           exc_info=(type(exc), exc, exc.__traceback__))
            yield ServerSentEvent(event="error", data={"detail": str(exc)})
            return
        except Exception:
            logger.exception("面试流发生未预期异常，session_id=%s", agent_request.session_id)
            yield ServerSentEvent(event="error", data={"detail": "面试处理失败，请查看后端日志。"})
            return
        yield ServerSentEvent(event="done", data={"session_id": str(agent_request.session_id)})

    @router.post("/personal_information_config", status_code=200)
    async def personal_information_config(
        request: Request,
        session_id: Annotated[UUID, Form()],
        config: Annotated[Json[InterviewPreset], Form()],
        file: Annotated[UploadFile | None, File()] = None,
    ):
        request.state.session_id = str(session_id)
        resume = await interview_service.configure_session(
            graph, session_id, config.candidate_config, config.interviewer_config, file=file,
        )
        return {"session_id": str(session_id), "resume": resume}

    return router
