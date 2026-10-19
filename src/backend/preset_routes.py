import asyncio

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Request
from langgraph.graph.state import CompiledStateGraph

from backend import interview_service, preset_service
from schemas import TaskState


def create_preset_router(
    graph: CompiledStateGraph[TaskState, None, TaskState, TaskState],
) -> APIRouter:
    """Expose the existing preset operations without changing their public URLs."""
    router = APIRouter(prefix="/interview", tags=["preset"])

    @router.get("/read_preset", status_code=200)
    async def read_preset() -> dict[str, list[str]]:
        files = await asyncio.to_thread(preset_service.list_presets)
        return {"files": files}

    @router.post("/load_preset", status_code=200)
    async def load_preset(
        session_id: Annotated[UUID, Body()], filename: str, request: Request,
    ) -> dict:
        request.state.session_id = str(session_id)
        preset = await interview_service.load_preset_into_session(graph, session_id, filename)
        return {"preset_config": preset}

    @router.post("/del_preset", status_code=200)
    async def delete_preset(filename: str):
        await asyncio.to_thread(preset_service.delete_preset, filename)
        return 200

    return router
