import json

from typing_extensions import Any
from pathlib import Path

def write_json(path: Path, data: Any) -> None:
    with open(path, mode="w+", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False
        )