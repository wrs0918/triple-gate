"""书籍工作区的固定目录布局。

所有路径常量集中于此，CLI 与协议文档引用同一份来源。
"""

from __future__ import annotations

BOOK_JSON = "book.json"
STATE_FILE = "state/state.json"
OUTLINE_FILE = "outline/outline.md"
PROJECTIONS_DIR = "projections"
CHAPTERS_DIR = "chapters"
QA_DIR = "qa"
EXPORTS_DIR = "exports"
WHITELIST_FILE = ".gate/whitelist.txt"


def chapter_draft(chapter: int) -> str:
    return f"chapters/ch{chapter:03d}_draft.md"


def chapter_final(chapter: int) -> str:
    return f"chapters/ch{chapter:03d}_final.md"


def qa_gate(chapter: int) -> str:
    return f"qa/ch{chapter:03d}_gate.json"


def qa_rubric(chapter: int) -> str:
    return f"qa/ch{chapter:03d}_rubric.md"


def qa_changes(chapter: int) -> str:
    return f"qa/ch{chapter:03d}_changes.json"


def context_pack() -> str:
    return "projections/context.md"
