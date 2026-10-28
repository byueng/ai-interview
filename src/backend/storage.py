import os

from pathlib import Path

from backend.errors import StorageError


def data_directory(name: str) -> Path:
    """Return one configured child directory for persisted application data."""
    root = os.environ.get("DATA_DIR") or os.environ.get("data_dir")
    root_path = Path(root).expanduser() if root and root.strip() else Path(__file__).resolve().parents[1] / "data"
    try:
        directory = root_path.resolve() / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    except (OSError, RuntimeError, ValueError) as exc:
        raise StorageError("数据目录初始化失败，请查看后端日志。") from exc
