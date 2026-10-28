import asyncio
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile

from backend.errors import StorageError
from backend.storage import data_directory


MAX_RESUME_BYTES = 10 * 1024 * 1024


def read_session_resume(filename: str, session_id: UUID) -> bytes:
    """只读取当前会话上传的 PDF，供模型附件使用。"""
    path = Path(filename)
    expected = data_directory("swap") / str(session_id) / "简历.pdf"
    if path.is_symlink() or path.resolve() != expected.absolute():
        raise ValueError("简历路径不属于当前会话，请重新上传。")
    try:
        with path.open("rb") as source:
            content = source.read(MAX_RESUME_BYTES + 1)
    except OSError as exc:
        raise ValueError("无法读取已上传的简历，请重新上传。") from exc
    if len(content) > MAX_RESUME_BYTES or not content.startswith(b"%PDF-"):
        raise ValueError("简历不是有效的 PDF 或超过 10 MiB，请重新上传。")
    return content


def _write_resume(content: bytes, session_id: UUID | None) -> str:
    directory = data_directory("swap")
    if session_id is not None:
        directory = directory / str(session_id)
    path = directory / "简历.pdf"
    temporary = directory / f".{uuid4().hex}.tmp"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with temporary.open("xb") as destination:
            destination.write(content)
        # 写入完成后替换；同一会话再次上传时更新简历，失败则保留旧文件。
        temporary.replace(path)
    except OSError as exc:
        raise StorageError("保存简历失败，请查看后端日志。") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return str(path)

async def save_resume(file: UploadFile, session_id: UUID | None = None) -> str:
    """保存 PDF 原文件，返回绝对路径；不解析正文、不修改面试配置。"""
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="请选择 PDF 格式的简历。")
    content = await file.read(MAX_RESUME_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="简历文件不能为空。")
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="简历文件不能超过 10 MiB。")
    # 仅做文件头检查，完整 PDF 解析留给后续简历处理流程。
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="文件不是有效的 PDF 格式。")
    return await asyncio.to_thread(_write_resume, content, session_id)
