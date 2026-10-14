from argparse import ArgumentParser
from fastapi import FastAPI

from backend.interview_routes import create_interview_router
from runtime import Runtime


def create_app(runtime: Runtime) -> FastAPI:
    """组装 HTTP 应用；每场面试的状态由 checkpointer 管理。"""
    app = FastAPI()
    app.include_router(create_interview_router(runtime.graph))

    @app.get("/")
    async def greeting():
        return {"status": "ok"}

    return app