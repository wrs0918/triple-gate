"""文本读取与切分：统一 UTF-8、剥离 markdown、中文切分。"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.core.errors import GateError

_SENTENCE_TERMINALS = re.compile(r"([。！？；]|…+)")
_CJK = re.compile(r"[一-鿿]")


def read_text(path: str | Path) -> str:
    """读取 UTF-8 文本（兼容 BOM）。

    Raises:
        FileNotFoundError: 文件不存在。
        GateError: 读取失败。
        ValueError: 文件为空。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise GateError(f"无法读取 {p}：{exc}") from exc
    if not text.strip():
        raise ValueError(f"文件为空：{p}")
    return text


def strip_markdown(text: str) -> str:
    """剥离 markdown 标记，保留正文文字。"""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`\n]*)`", r"\1", text)
    text = re.sub(r"^[\-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>\n]+>", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip("\n")


def split_sentences(text: str) -> list[str]:
    """按中文句终符切分，终符保留在句尾；丢弃纯标点句。"""
    parts = _SENTENCE_TERMINALS.split(text)
    sentences: list[str] = []
    buffer = ""
    for part in parts:
        buffer += part
        if _SENTENCE_TERMINALS.fullmatch(part):
            if re.sub(r"[。！？…；\s]", "", buffer):
                sentences.append(buffer.strip())
            buffer = ""
    if re.sub(r"[。！？…；\s]", "", buffer):
        sentences.append(buffer.strip())
    return sentences


def split_paragraphs(text: str) -> list[str]:
    """按换行切分段落（网文惯例：一行一段）。"""
    return [p.strip() for p in text.split("\n") if p.strip()]


def cjk_len(text: str) -> int:
    """统计中日韩统一表意文字数量（不含标点与字母数字）。"""
    return len(_CJK.findall(text))
