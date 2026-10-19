import json
import re

from typing import Any
from pathlib import Path

def read_json(path: Path, data: Any = None) -> Any:
    """只读 JSON；保留原始 I/O、解码异常，交由调用流程解释。"""
    with open(path, mode="r", encoding="utf-8") as file:
        return json.load(file)

def write_json(path: Path, data: Any) -> None:
    """ 简单写入json文件 """
    # 先序列化，避免数据不支持 JSON 时先清空旧快照。
    content = json.dumps(data, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode="w", encoding="utf-8") as file:
        file.write(content)

def write_unique_json(path: Path, data: Any) -> Path:
    """保留已有文件，按同名文件的最大编号递增保存，并返回实际路径。"""
    content = json.dumps(data, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(
        rf"{re.escape(path.stem)}(?:\(([0-9]+)\))?{re.escape(path.suffix)}"
    )
    max_number = -1
    for entry in path.parent.iterdir():
        match = pattern.fullmatch(entry.name)
        if match:
            # 同名目录也占用路径；无编号的原名按 0 处理。
            max_number = max(max_number, int(match.group(1) or 0))

    number = max_number + 1
    while True:
        candidate = (
            path if number == 0
            else path.with_name(f"{path.stem}({number}){path.suffix}")
        )
        try:
            # x 为独占创建；即使并发请求撞名，也不会清空已有文件。
            file = candidate.open("x", encoding="utf-8")
        except FileExistsError:
            number += 1
            continue
        with file:
            file.write(content)
        return candidate
