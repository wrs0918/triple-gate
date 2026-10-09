"""平台导出：番茄小说格式。"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.core.textio import read_text, strip_markdown

_TITLE_PATTERN = re.compile(r"^第\d+章\s*(.*)$")


def _chapter_title_and_body(raw: str) -> tuple[str, str]:
    lines = strip_markdown(raw).split("\n")
    if not lines:
        return "", ""
    match = _TITLE_PATTERN.match(lines[0].strip())
    if match:
        title = match.group(1).strip()
        body = "\n".join(lines[1:]).strip()
        return title, body
    return lines[0].strip(), "\n".join(lines[1:]).strip()


def export_fanqie(book_dir: str | Path, out_dir: str | Path | None = None) -> list[Path]:
    """把 chapters/ 下全部终稿导出为番茄格式 txt。

    Raises:
        ValueError: 没有任何终稿可导出。
    """
    chapters_dir = Path(book_dir) / "chapters"
    finals = sorted(chapters_dir.glob("ch*_final.md")) if chapters_dir.exists() else []
    if not finals:
        raise ValueError("没有可导出的终稿（chapters/ 下未找到 ch*_final.md）")

    out = Path(out_dir) if out_dir else Path(book_dir) / "exports" / "fanqie"
    out.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for source in finals:
        match = re.match(r"ch(\d+)_final\.md$", source.name)
        if not match:
            continue
        number = int(match.group(1))
        title, body = _chapter_title_and_body(read_text(source))
        header = f"第{number}章 {title}".rstrip()
        content = f"{header}\n\n{body}\n" if body else f"{header}\n"
        target = out / f"第{number:03d}章.txt"
        target.write_text(content, encoding="utf-8")
        written.append(target)
    if not written:
        raise ValueError("终稿文件名不符合 chNNN_final.md 规范，无法导出")
    return written
