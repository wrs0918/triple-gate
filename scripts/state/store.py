"""状态读写：唯一真源文件的原子落盘与校验加载。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.core.errors import GateError
from scripts.state.schema import validate_state


def load_state(path: str | Path) -> dict:
    """读取并校验状态文件。

    Raises:
        FileNotFoundError: 文件不存在。
        GateError: JSON 解析失败。
        ValueError: schema 校验失败（消息含全部错误）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"状态文件不存在：{p}（请先运行 tg init）")
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"状态文件损坏，无法解析：{p}：{exc}") from exc
    errors = validate_state(obj)
    if errors:
        raise ValueError("状态不合法：" + "；".join(errors))
    return obj


def save_state(path: str | Path, state: dict) -> None:
    """校验后原子写入状态文件（临时文件 + 替换）。"""
    errors = validate_state(state)
    if errors:
        raise ValueError("拒绝写入非法状态：" + "；".join(errors))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)
