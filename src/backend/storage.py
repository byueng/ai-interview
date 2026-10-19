import os

from pathlib import Path

from backend.errors import StorageError


def data_directory(name: str) -> Path:
    """Return one configured child directory for auxiliary JSON data."""
    root = os.environ.get("data_dir")
    if root is None or not root.strip():
        raise StorageError("未配置 data_dir，请检查后端存储配置。")
    try:
        directory = Path(root).expanduser().resolve() / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    except (OSError, RuntimeError, ValueError) as exc:
        raise StorageError("数据目录初始化失败，请查看后端日志。") from exc
