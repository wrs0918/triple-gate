"""写前上下文包组装：固定栏位 + 硬预算。

预算原则（借鉴头部项目的做法）：
- 书魂卡与本章大纲永不裁剪（北极星不可打折）
- 读者已知最后裁剪：它是硬规则「正文不得超出读者已知」的唯一执行依据
- 超预算时按优先级从低到高整段丢弃（顺序见 _SHRINK_ORDER）
- 固定部分自身超预算则直接报错（说明大纲条目该精简了）
"""

from __future__ import annotations

DEFAULT_BUDGET = 12000
_SUMMARY_WINDOW = 3
_SUMMARY_MAX_CHARS = 300
_ANTI_PATTERN_WINDOW = 10
_HOOK_WINDOW = 10
_FORESHADOW_LINE_MAX = 80
# 与 scripts.state.commit._DEFAULT_COOLDOWN 同值：冷却期只读不写，手改状态缺该字段时兜底
_DEFAULT_TROPE_COOLDOWN = 10

# 超预算时从低到高整段丢弃的顺序（越靠后越晚被丢）
_SHRINK_ORDER = (
    "anti_patterns",   # 质检反哺：丢了质量回退，但不伤连续性
    "tropes_cooling",  # 冷却套路：建议性约束
    "style",           # 文风基准：语感参考
    "hooks",           # 未回报钩子：兑现提醒
    "foreshadowing",   # 活跃伏笔：埋设/回收提醒
    "characters",      # 角色状态：连续性
    "summaries",       # 最近章摘要：剧情连续性
    "reader_knowledge",# 读者已知：防剧透泄漏（硬规则），最后裁剪
)


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


def _render_hooks(state: dict) -> str:
    """未回报钩子：部署后尚未兑现的承诺，写作时需要有兑现意识。"""
    active = [h for h in state["hooks"] if h["status"] == "deployed"]
    if not active:
        return ""
    lines = ["## 未回报钩子（读者在等兑现，近期章节应有进展）", ""]
    for h in active[-_HOOK_WINDOW:]:
        lines.append(f"- [{h['id']}] {h['content']}（第{h['deployed_ch']}章部署）")
    return "\n".join(lines)


def _render_tropes_cooling(state: dict) -> str:
    """冷却中的套路：近期已用过的套路本章避免复用（同质化防线）。"""
    current = state["progress"]["current_chapter"]
    cooling: list[tuple[int, str, int]] = []
    for trope in state["tropes"]:
        cooldown = trope.get("cooldown", _DEFAULT_TROPE_COOLDOWN)
        recent = [c for c in trope.get("chapters", []) if 0 <= current - c <= cooldown]
        if recent:
            cooling.append((max(recent), trope["name"], cooldown))
    if not cooling:
        return ""
    lines = ["## 冷却中的套路（近期已用，本章避免复用）", ""]
    for last_used, name, cooldown in sorted(cooling, reverse=True):
        lines.append(f"- {name}（第{last_used}章用过，冷却 {cooldown} 章）")
    return "\n".join(lines)


def _render_characters(state: dict) -> str:
    if not state["characters"]:
        return ""
    lines = ["## 出场角色状态", ""]
    for c in state["characters"]:
        state_text = "、".join(f"{k}:{v}" for k, v in c["state"].items())
        line = f"- {c['name']}（{c['role']}）｜{state_text}｜已知：{'；'.join(c['known_facts']) or '—'}"
        if c.get("speech_print"):
            line += f"｜语言指纹：{c['speech_print']}"
        lines.append(line)
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
    for key in (
        "summaries", "foreshadowing", "hooks", "characters",
        "reader_knowledge", "style", "anti_patterns", "tropes_cooling",
    ):
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
        "hooks": _render_hooks(state),
        "characters": _render_characters(state),
        "reader_knowledge": _render_reader_knowledge(state),
        "style": _render_style(state),
        "anti_patterns": _render_anti_patterns(state),
        "tropes_cooling": _render_tropes_cooling(state),
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
