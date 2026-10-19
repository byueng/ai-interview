import json

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.errors import (
    InvalidPresetError,
    InvalidPresetNameError,
    PresetNotFoundError,
    StorageError,
)
from backend.file import read_json, write_unique_json
from backend.storage import data_directory
from schemas import InterviewPreset


def preset_path(filename: str) -> Path:
    if (
        not filename.endswith(".json")
        or len(filename) <= 5
        or any(character in filename for character in ("/", "\\"))
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
    ):
        raise InvalidPresetNameError("预设文件名无效，请提供单个 JSON 文件名。")
    directory = data_directory("interview_preset")
    path = directory / filename
    try:
        if path.is_symlink() or path.resolve().parent != directory:
            raise InvalidPresetNameError("预设路径无效。")
    except (OSError, RuntimeError, ValueError) as exc:
        raise StorageError("预设路径检查失败，请查看后端日志。") from exc
    return path


def save_preset(preset: InterviewPreset) -> Path:
    path = preset_path(f"{preset.candidate_config.position}.json")
    try:
        return write_unique_json(path, preset.model_dump(mode="json"))
    except (OSError, TypeError, ValueError) as exc:
        raise StorageError("保存面试预设失败，请查看后端日志。") from exc


def list_presets() -> list[str]:
    directory = data_directory("interview_preset")
    try:
        return sorted(
            path.name
            for path in directory.iterdir()
            if path.suffix == ".json" and path.is_file() and not path.is_symlink()
        )
    except OSError as exc:
        raise StorageError("读取预设列表失败，请查看后端日志。") from exc


def read_preset(filename: str) -> InterviewPreset:
    path = preset_path(filename)
    try:
        payload: Any = read_json(path)
    except FileNotFoundError as exc:
        raise PresetNotFoundError("预设不存在，请刷新预设列表。") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidPresetError("预设文件无法解析，请检查 JSON 内容与 UTF-8 编码。") from exc
    except OSError as exc:
        raise StorageError("读取预设文件失败，请查看后端日志。") from exc
    try:
        return InterviewPreset.model_validate(payload)
    except ValidationError as exc:
        raise InvalidPresetError("预设配置缺少字段或类型错误，请检查预设文件。") from exc


def delete_preset(filename: str) -> None:
    path = preset_path(filename)
    try:
        path.unlink()
    except FileNotFoundError as exc:
        raise PresetNotFoundError("预设不存在，请刷新预设列表。") from exc
    except OSError as exc:
        raise StorageError("删除预设失败，请查看后端日志。") from exc
