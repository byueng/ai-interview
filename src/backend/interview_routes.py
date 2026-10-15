import logging
import os

from argparse import ArgumentParser
from collections.abc import AsyncIterator
from pathlib import Path
from typing_extensions import Annotated, Dict, List
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.status import HTTP_200_OK, HTTP_501_NOT_IMPLEMENTED
from langgraph.graph import START

from backend import interview_service
from backend.interview_service import create_session, graph_config_build, save_interview_preset
from backend.file import read_json
from langgraph.graph.state import CompiledStateGraph
from schemas import AgentRequest, Candidate, Interviewer, TaskState


logger = logging.getLogger(__name__)

def create_interview_router(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState]
) -> APIRouter:
    router = APIRouter(prefix="/interview", tags=["interview"])

    @router.get("/begin", status_code=HTTP_200_OK)
    async def interview_begin():
        try:
            session_id = await create_session(graph)
            config = graph_config_build(session_id)
            await graph.aupdate_state(
                config=config,
                values={
                    "session_id": session_id
                }
            )
        except NotImplementedError as exc:
            raise HTTPException(HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
        return {"session_id": session_id}

    @router.post("/stream", status_code=HTTP_200_OK, response_class=EventSourceResponse)
    async def stream_turn(agent_request: AgentRequest, request: Request) -> AsyncIterator[ServerSentEvent]:
        try:
            async for chunk in interview_service.run_turn(graph, agent_request):
                yield ServerSentEvent(event="message", data=jsonable_encoder(chunk))
        
        except NotImplementedError as exc:
            # 流开始后不能再把 HTTP 状态改成 501，错误也通过 SSE 发送。
            yield ServerSentEvent(event="error", data={"detail": str(exc)})
            return
        except Exception:
            logger.exception("面试流处理失败，session_id=%s", agent_request.session_id)
            yield ServerSentEvent(event="error", data={"detail": "面试处理失败，请查看后端日志"})
            return
        yield ServerSentEvent(event="done", data={"session_id": str(agent_request.session_id)})

    @router.post("/personal_information_config", status_code=HTTP_200_OK)
    async def personal_information_config(session_id: Annotated[UUID, Body()], candidate: Candidate, interviewer: Interviewer, request: Request):
        try:
            config = graph_config_build(session_id)
            await graph.aupdate_state(
                config=config,
                values={
                    "candidate_config": candidate,
                    "interviewer_config": interviewer
                },
                as_node=START
            )
            await save_interview_preset(graph, session_id)
            return HTTP_200_OK 
        except NotImplementedError as exc:
            raise NotImplementedError(f"{exc}")

    @router.get("/read_preset")
    async def read_preset(request: Request, status_code=HTTP_200_OK) -> Dict[str, List[str]]:
        return {
            "files": os.listdir(Path(os.environ.get("data_dir")) / "interview_preset")
        }

    @router.post("/load_preset")
    async def load_preset(session_id: Annotated[UUID, Body()], filename: str, request: Request, status_code=HTTP_200_OK) -> Dict:
        try:
            root_path: Path = Path(os.environ.get("data_dir")) / "interview_preset" / f"{filename}"
            preset_config: Dict = read_json(root_path, filename)
            await graph.aupdate_state(
                config=graph_config_build(session_id=session_id),
                values={
                    "candidate_config": Candidate(**preset_config["candidate_config"]),
                    "interviewer_config": Interviewer(**preset_config["interviewer_config"])
                },
                as_node=START
            )
            return {
                "preset_config": preset_config
            }

        except NotImplementedError as exc:
            raise(f"{exc}")         

    @router.post("/del_preset")
    async def del_preset(filename: str, request: Request, status_code=HTTP_200_OK):
        return 

    @router.post("/upload_resume", status_code=HTTP_200_OK)
    async def upload_resume():
        pass

    return router
