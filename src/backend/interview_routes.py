import asyncio
import logging
from contextlib import aclosing

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.graph.state import CompiledStateGraph

from backend import interview_service
from backend.errors import InterviewError
from schemas import AgentRequest, Candidate, Interviewer, TaskState, SessionResponse, SessionStateResponse


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
        try:
            async with aclosing(interview_service.run_turn(graph, agent_request)) as stream:
                async for chunk in stream:
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

    @router.get("/read_preset", status_code=200)
    async def read_preset(request: Request) -> dict[str, list[str]]:
        files = await asyncio.to_thread(interview_service.list_interview_presets)
        return {"files": files}

    @router.post("/load_preset", status_code=200)
    async def load_preset(
        session_id: Annotated[UUID, Body()], filename: str, request: Request,
    ) -> dict:
        request.state.session_id = str(session_id)
        preset = await interview_service.load_interview_preset(graph, session_id, filename)
        return {"preset_config": preset}

    @router.post("/del_preset", status_code=200)
    async def del_preset(filename: str, request: Request):
        await asyncio.to_thread(interview_service.delete_interview_preset, filename)
        return 200

    @router.post("/upload_resume", status_code=200)
    async def upload_resume():
        raise HTTPException(status_code=501, detail="简历上传暂未实现。")

    return router
