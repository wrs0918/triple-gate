"""写前上下文包组装：固定栏位 + 硬预算。

预算原则（借鉴头部项目的做法）：
- 书魂卡与本章大纲永不裁剪（北极星不可打折）
- 超预算时按优先级从低到高整段丢弃：禁忌 → 文风基准 → 读者已知 → 角色 → 伏笔 → 摘要
- 固定部分自身超预算则直接报错（说明大纲条目该精简了）
"""

from __future__ import annotations

DEFAULT_BUDGET = 12000
_SUMMARY_WINDOW = 3
_SUMMARY_MAX_CHARS = 300
_ANTI_PATTERN_WINDOW = 10
_FORESHADOW_LINE_MAX = 80

# 超预算时从低到高丢弃的顺序
_SHRINK_ORDER = ("anti_patterns", "style", "reader_knowledge", "characters", "foreshadowing", "summaries")


def _render_north_star(state: dict) -> str:
    star = state["book"]["north_star"]
    lines = ["## 书魂卡（北极星，不可偏离）", ""]
    labels = {
        "positioning": "题材定位",
        "core_conflict": "核心矛盾",
        "power_cost": "能力与代价",
        "differentiation": "差异化",
        "city_industry": "城市/行业",
    }
    for field, label in labels.items():
        lines.append(f"- {label}：{star.get(field, '')}")
    return "\n".join(lines)


def _render_summaries(state: dict) -> str:
    current = state["progress"]["current_chapter"]
    done = [
        (int(key[2:5]), entry["summary"])
        for key, entry in state["chapters"].items()
        if entry.get("status") == "final" and "summary" in entry
    ]
    done = [(num, s) for num, s in done if num < current]
    done.sort()
    if not done:
        return ""
    lines = ["## 最近章摘要", ""]
    for num, summary in done[-_SUMMARY_WINDOW:]:
        text = summary[:_SUMMARY_MAX_CHARS]
        lines.append(f"- [第{num}章] {text}")
    return "\n".join(lines)


def _render_foreshadowing(state: dict) -> str:
    current = state["progress"]["current_chapter"]
    active = [f for f in state["foreshadowing"] if f["status"] == "planted"]
    if not active:
        return ""

    def _urgency(f: dict) -> tuple[int, int]:
        due = f.get("due_ch")
        overdue = 1 if (due is not None and due < current) else 0
        priority = {"high": 0, "mid": 1, "low": 2}.get(f["priority"], 3)
        return (-overdue, priority)

    lines = ["## 活跃伏笔", ""]
    for f in sorted(active, key=_urgency):
        due = f.get("due_ch")
        flag = " ⚠超期" if (due is not None and due < current) else ""
        text = f"[{f['id']}]{flag} {f['content']}（埋于第{f['planted_ch']}章"
        if due is not None:
            text += f"，到期第{due}章"
        text += "）"
        lines.append(f"- {text[:_FORESHADOW_LINE_MAX]}")
    return "\n".join(lines)


def _render_characters(state: dict) -> str:
    if not state["characters"]:
        return ""
    lines = ["## 出场角色状态", ""]
    for c in state["characters"]:
        state_text = "、".join(f"{k}:{v}" for k, v in c["state"].items())
        lines.append(f"- {c['name']}（{c['role']}）｜{state_text}｜已知：{'；'.join(c['known_facts']) or '—'}")
    return "\n".join(lines)


def _render_reader_knowledge(state: dict) -> str:
    visible = [t for t in state["timeline"] if t["reveal_status"] != "hidden"]
    if not visible:
        return ""
    lines = ["## 读者已知（正文表述不得超出此栏）", ""]
    for t in visible:
        lines.append(f"- {t['reader_knowledge']}")
    return "\n".join(lines)


def _render_anti_patterns(state: dict) -> str:
    recent = state["anti_patterns"][-_ANTI_PATTERN_WINDOW:]
    if not recent:
        return ""
    lines = ["## 本章禁忌（历次质检反哺，写作时必须避开）", ""]
    for a in recent:
        lines.append(f"- [{a['source']}/{a['rule']}] {a.get('note', '')}")
    return "\n".join(lines)


def _render_style(state: dict) -> str:
    paragraph = state.get("style_baseline", {}).get("paragraph", "")
    if not paragraph:
        return ""
    return f"## 文风基准段\n\n{paragraph}"


def _assemble(north: str, outline: str, sections: dict[str, str]) -> str:
    parts = ["# 写前上下文包", "", north, ""]
    outline_entry = outline.strip()
    if outline_entry:
        parts += ["## 本章大纲", "", outline_entry, ""]
    for key in ("summaries", "foreshadowing", "characters", "reader_knowledge", "style", "anti_patterns"):
        text = sections.get(key, "")
        if text:
            parts += [text, ""]
    return "\n".join(parts).rstrip() + "\n"


def build_context(state: dict, outline_entry: str, budget: int = DEFAULT_BUDGET) -> str:
    """组装不超过 budget 字符的写前上下文包。

    Raises:
        ValueError: 固定部分（书魂卡＋大纲）自身超出预算。
    """
    sections = {
        "summaries": _render_summaries(state),
        "foreshadowing": _render_foreshadowing(state),
        "characters": _render_characters(state),
        "reader_knowledge": _render_reader_knowledge(state),
        "style": _render_style(state),
        "anti_patterns": _render_anti_patterns(state),
    }
    north = _render_north_star(state)
    while True:
        text = _assemble(north, outline_entry, sections)
        if len(text) <= budget:
            return text
        for key in _SHRINK_ORDER:
            if sections.get(key):
                del sections[key]
                break
        else:
            fixed = len(_assemble(north, outline_entry, {}))
            raise ValueError(
                f"上下文超出预算：固定部分（书魂卡＋大纲）已占 {fixed} 字符，超过预算 {budget}"
            )
