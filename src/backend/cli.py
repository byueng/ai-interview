import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.errors import (
    InterviewError, InvalidPresetNameError, PresetNotFoundError,
    SessionNotConfiguredError, SessionNotFoundError,
    SessionConflictError, SessionGoneError,
)
from backend.interview_routes import create_interview_router
from runtime import Runtime


logger = logging.getLogger(__name__)


def create_app(runtime: Runtime) -> FastAPI:
    """组装 HTTP 应用；每场面试的状态由 checkpointer 管理。"""
    app = FastAPI()

    @app.exception_handler(InterviewError)
    async def handle_interview_error(request: Request, exc: InterviewError):
        if isinstance(exc, (SessionNotFoundError, PresetNotFoundError)):
            status_code = 404
        elif isinstance(exc, (SessionNotConfiguredError, SessionConflictError)):
            status_code = 409
        elif isinstance(exc, SessionGoneError):
            status_code = 410
        elif isinstance(exc, InvalidPresetNameError):
            status_code = 400
        else:
            status_code = 500
        if status_code >= 500:
            logger.error(
                "后端流程失败，method=%s path=%s session_id=%s filename=%r",
                request.method, request.url.path, getattr(request.state, "session_id", None),
                request.query_params.get("filename"),
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        else:
            logger.warning(
                "请求未完成，path=%s session_id=%s detail=%s",
                request.url.path, getattr(request.state, "session_id", None), exc,
            )
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.error(
            "未预期的后端异常，method=%s path=%s session_id=%s",
            request.method, request.url.path, getattr(request.state, "session_id", None),
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(status_code=500, content={"detail": "服务端处理失败，请查看后端日志。"})

    app.include_router(create_interview_router(runtime.graph))

    @app.get("/")
    async def greeting():
        return {"status": "ok"}

    return app
