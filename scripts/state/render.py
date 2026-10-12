"""投影渲染：从状态真源确定性地生成人可读的 markdown 视图。

派生文件由工具整份重渲染，手改会被 check_projections 检出。
"""

from __future__ import annotations

from pathlib import Path

PROJECTION_FILES = ("timeline.md", "foreshadowing.md", "characters.md", "status.md")


def _cell(value) -> str:
    """markdown 表格单元格转义：竖线会撑破表格，换行会破坏行结构。"""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_timeline(state: dict) -> str:
    lines = [
        "# 双时间线",
        "",
        "| 章 | 客观事实（作者真相） | 读者已知 | 揭示状态 |",
        "|---|---|---|---|",
    ]
    for entry in state["timeline"]:
        lines.append(
            f"| {entry['chapter']} | {_cell(entry['objective_fact'])} "
            f"| {_cell(entry['reader_knowledge'])} | {entry['reveal_status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_foreshadowing(state: dict) -> str:
    current = state["progress"]["current_chapter"]
    lines = ["# 伏笔台账", ""]
    if not state["foreshadowing"]:
        lines.append("（暂无伏笔）")
        return "\n".join(lines) + "\n"
    lines += ["| ID | 内容 | 埋设章 | 状态 | 到期章 | 优先级 |", "|---|---|---|---|---|---|"]
    for f in state["foreshadowing"]:
        status = f["status"]
        due = f.get("due_ch")
        if status == "planted" and due is not None and due < current:
            status += " ⚠超期"
        lines.append(
            f"| {f['id']} | {_cell(f['content'])} | {f['planted_ch']} | {status} "
            f"| {due if due is not None else '—'} | {f['priority']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_characters(state: dict) -> str:
    lines = ["# 角色状态", ""]
    if not state["characters"]:
        lines.append("（暂无角色）")
        return "\n".join(lines) + "\n"
    for c in state["characters"]:
        state_text = "、".join(f"{k}:{v}" for k, v in c["state"].items())
        known = "；".join(c["known_facts"]) or "—"
        lines.append(f"## {c['name']}（{c['role']}）")
        lines.append("")
        lines.append(f"- 状态：{state_text}")
        lines.append(f"- 已知事实：{known}")
        lines.append(f"- 语言指纹：{c.get('speech_print', '—')}")
        lines.append("")
    return "\n".join(lines)


def _render_status(state: dict) -> str:
    progress = state["progress"]
    finals = sum(1 for c in state["chapters"].values() if c["status"] == "final")
    lines = [
        "# 进度快照",
        "",
        f"- 书名：{state['book']['title']}",
        f"- 阶段：{progress['phase']}",
        f"- 当前章：第 {progress['current_chapter']} 章",
        f"- 已终稿：{finals} 章",
        f"- 状态版本：{progress['state_revision']}",
        "",
    ]
    return "\n".join(lines)


_RENDERERS = {
    "timeline.md": _render_timeline,
    "foreshadowing.md": _render_foreshadowing,
    "characters.md": _render_characters,
    "status.md": _render_status,
}


def render_projections(state: dict, outdir: str | Path) -> list[Path]:
    """把状态渲染为全部投影文件，返回写入的文件清单。"""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, render in _RENDERERS.items():
        target = out / name
        target.write_text(render(state), encoding="utf-8")
        written.append(target)
    return written


def check_projections(state: dict, outdir: str | Path) -> list[str]:
    """比对投影文件与重渲染结果，返回不一致清单（空即一致）。"""
    out = Path(outdir)
    mismatches = []
    for name, render in _RENDERERS.items():
        target = out / name
        if not target.exists():
            mismatches.append(f"projections/{name}: 缺失（从未渲染或被删除）")
            continue
        if target.read_text(encoding="utf-8") != render(state):
            mismatches.append(f"projections/{name}: 与状态不一致（疑似手改，请勿直接编辑派生文件）")
    return mismatches
