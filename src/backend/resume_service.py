import asyncio
import re
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pypdf
from fastapi import HTTPException, UploadFile
from pdfminer.high_level import extract_text
from pdfminer.psparser import PSException

from backend.errors import StorageError
from backend.storage import data_directory


MAX_RESUME_BYTES = 10 * 1024 * 1024

def read_session_resume(filename: str, session_id: UUID) -> str:
    """校验当前会话的 PDF 原始字节，再提取文字；不识别扫描图片。"""
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
    try:
        reader = pypdf.PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise ValueError("简历 PDF 已加密，请解除密码后重新上传。")
        # CID fonts may omit ToUnicode; pdfminer uses predefined CJK maps.
        extracted = extract_text(BytesIO(content))
        pages = [page.strip() for page in extracted.split("\f")]
    except (pypdf.errors.PyPdfError, PSException) as exc:
        raise ValueError("无法解析简历 PDF，请重新导出后上传。") from exc
    text = "\n\n".join(page for page in pages if page)
    if not text:
        raise ValueError("简历 PDF 中没有可提取的文字，请上传包含文字层的 PDF；扫描件需先进行 OCR。")
    if re.search(r"\(cid:\d+\)", text):
        raise ValueError("简历 PDF 的部分字体无法映射为文字，请重新导出包含 Unicode 映射的 PDF，或先进行 OCR。")
    return text

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
