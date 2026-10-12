"""状态与章变更的 schema 校验：返回中文错误清单。

校验是流水线的「合同」：所有写入 state 的数据必须先通过这里。
书魂卡（north_star）在 planning 阶段允许为空，进入 writing 前必须五项齐备。
"""

from __future__ import annotations

PHASES = {"planning", "writing", "finished"}
REVEAL_STATUSES = {"hidden", "partial", "revealed"}
FORESHADOW_STATUSES = {"planted", "paid_off", "abandoned"}
HOOK_STATUSES = {"deployed", "rewarded", "abandoned"}
PRIORITIES = {"high", "mid", "low"}
CHAPTER_STATUSES = {"drafting", "final"}
GATE_STATUSES = {"pending", "passed", "failed"}
CHARACTER_ROLES = {"主角", "对手", "恋人", "配角"}
ANTI_PATTERN_SOURCES = {"lint", "metrics", "rubric"}
NORTH_STAR_FIELDS = (
    "positioning",
    "core_conflict",
    "power_cost",
    "differentiation",
    "city_industry",
)
CHANGES_KEYS = {
    "chapter",
    "summary",
    "word_count",
    "timeline_new",
    "foreshadowing_planted",
    "foreshadowing_paid",
    "hooks_new",
    "hooks_rewarded",
    "tropes_used",
    "characters_update",
    "anti_patterns_new",
}
SUMMARY_MAX_CHARS = 300


def _err(errors: list[str], where: str, message: str) -> None:
    errors.append(f"{where}: {message}")


def _require_str(obj: dict, key: str, where: str, errors: list[str], allow_empty: bool = False) -> None:
    value = obj.get(key)
    if not isinstance(value, str):
        _err(errors, where, f"{key} 应为字符串")
    elif not value.strip() and not allow_empty:
        _err(errors, where, f"{key} 不能为空")


def _require_int(obj: dict, key: str, where: str, errors: list[str], minimum: int | None = None) -> None:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        _err(errors, where, f"{key} 应为整数")
    elif minimum is not None and value < minimum:
        _err(errors, where, f"{key} 应不小于 {minimum}")


def _require_enum(value, allowed: set[str], where: str, errors: list[str]) -> None:
    if value not in allowed:
        allowed_text = "/".join(sorted(allowed))
        _err(errors, where, f"非法值「{value}」（允许：{allowed_text}）")


def _require_optional_int(obj: dict, key: str, where: str, errors: list[str], minimum: int | None = None) -> None:
    """key 存在时才校验（可选整数字段）。"""
    if key in obj and obj[key] is not None:
        _require_int(obj, key, where, errors, minimum=minimum)


def _require_str_list(value, where: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _err(errors, where, "应为字符串列表")


def _validate_timeline_entry(entry: dict, where: str, errors: list[str]) -> None:
    if not isinstance(entry, dict):
        _err(errors, where, "应为对象")
        return
    _require_int(entry, "chapter", where, errors, minimum=0)
    _require_str(entry, "objective_fact", where, errors)
    _require_str(entry, "reader_knowledge", where, errors)
    _require_enum(entry.get("reveal_status"), REVEAL_STATUSES, f"{where}.reveal_status", errors)


def _validate_state_top(state: dict, errors: list[str]) -> None:
    if state.get("schema_version") != 1:
        _err(errors, "schema_version", "必须为 1")
    for key in ("book", "progress", "chapters"):
        if not isinstance(state.get(key), dict):
            _err(errors, key, "应为对象")
    for key in ("timeline", "foreshadowing", "hooks", "tropes", "characters", "anti_patterns"):
        if not isinstance(state.get(key), list):
            _err(errors, key, "应为列表")
    if not isinstance(state.get("style_baseline"), dict):
        _err(errors, "style_baseline", "应为对象")


def _validate_book(book: dict, phase: str, errors: list[str]) -> None:
    _require_str(book, "title", "book", errors)
    _require_str(book, "genre", "book", errors)
    star = book.get("north_star")
    if not isinstance(star, dict):
        _err(errors, "book.north_star", "应为对象")
        return
    allow_empty = phase == "planning"
    for field in NORTH_STAR_FIELDS:
        _require_str(star, field, f"book.north_star.{field}", errors, allow_empty=allow_empty)


def _validate_progress(progress: dict, errors: list[str]) -> None:
    _require_enum(progress.get("phase"), PHASES, "progress.phase", errors)
    _require_int(progress, "current_chapter", "progress", errors, minimum=1)
    _require_int(progress, "state_revision", "progress", errors, minimum=0)


def _validate_chapters(chapters: dict, errors: list[str]) -> None:
    for key, entry in chapters.items():
        where = f"chapters.{key}"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_enum(entry.get("status"), CHAPTER_STATUSES, f"{where}.status", errors)
        for layer in ("gate_layer1", "gate_layer2", "gate_layer3"):
            _require_enum(entry.get(layer), GATE_STATUSES, f"{where}.{layer}", errors)


def _validate_collections(state: dict, errors: list[str]) -> None:
    for entry in state["timeline"]:
        _validate_timeline_entry(entry, "timeline", errors)
    for entry in state["foreshadowing"]:
        where = f"foreshadowing.{entry.get('id', '?')}"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "id", where, errors)
        _require_str(entry, "content", where, errors)
        _require_int(entry, "planted_ch", where, errors, minimum=1)
        _require_optional_int(entry, "due_ch", where, errors, minimum=1)
        _require_enum(entry.get("status"), FORESHADOW_STATUSES, f"{where}.status", errors)
        _require_enum(entry.get("priority"), PRIORITIES, f"{where}.priority", errors)
    for entry in state["hooks"]:
        where = f"hooks.{entry.get('id', '?')}"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "id", where, errors)
        _require_str(entry, "content", where, errors)
        _require_int(entry, "deployed_ch", where, errors, minimum=1)
        _require_enum(entry.get("status"), HOOK_STATUSES, f"{where}.status", errors)
    for entry in state["tropes"]:
        where = f"tropes.{entry.get('name', '?')}"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "name", where, errors)
        if not isinstance(entry.get("chapters"), list):
            _err(errors, where, "chapters 应为列表")
    for entry in state["characters"]:
        where = f"characters.{entry.get('name', '?')}"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "name", where, errors)
        _require_enum(entry.get("role"), CHARACTER_ROLES, f"{where}.role", errors)
        if not isinstance(entry.get("known_facts"), list):
            _err(errors, where, "known_facts 应为列表")
    for entry in state["anti_patterns"]:
        where = "anti_patterns"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_int(entry, "added_ch", where, errors, minimum=1)
        _require_enum(entry.get("source"), ANTI_PATTERN_SOURCES, f"{where}.source", errors)
        _require_str(entry, "rule", where, errors)


def validate_state(state: dict) -> list[str]:
    """校验书籍状态，返回错误清单（空列表即合法）。"""
    if not isinstance(state, dict):
        return ["state: 应为对象"]
    errors: list[str] = []
    _validate_state_top(state, errors)
    if errors:
        return errors
    phase = state["progress"].get("phase", "")
    _validate_book(state["book"], phase, errors)
    _validate_progress(state["progress"], errors)
    _validate_chapters(state["chapters"], errors)
    _validate_collections(state, errors)
    return errors


def _validate_changes_optional(changes: dict, errors: list[str]) -> None:
    for entry in changes.get("timeline_new", []) or []:
        where = "changes.timeline_new"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        # 变更中的时间线条目不带章号，章号由 changes.chapter 统一注入
        _require_str(entry, "objective_fact", where, errors)
        _require_str(entry, "reader_knowledge", where, errors)
        _require_enum(entry.get("reveal_status"), REVEAL_STATUSES, f"{where}.reveal_status", errors)
    for entry in changes.get("foreshadowing_planted", []) or []:
        where = "changes.foreshadowing_planted"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "content", where, errors)
        _require_optional_int(entry, "due_ch", where, errors, minimum=1)
        _require_enum(entry.get("priority"), PRIORITIES, f"{where}.priority", errors)
    if "foreshadowing_paid" in changes:
        _require_str_list(changes.get("foreshadowing_paid"), "changes.foreshadowing_paid", errors)
    for entry in changes.get("hooks_new", []) or []:
        where = "changes.hooks_new"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "content", where, errors)
    if "hooks_rewarded" in changes:
        _require_str_list(changes.get("hooks_rewarded"), "changes.hooks_rewarded", errors)
    for entry in changes.get("characters_update", []) or []:
        where = "changes.characters_update"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_str(entry, "name", where, errors)
        if "known_facts_add" in entry:
            _require_str_list(
                entry.get("known_facts_add"), f"{where}.known_facts_add", errors
            )
    for entry in changes.get("anti_patterns_new", []) or []:
        where = "changes.anti_patterns_new"
        if not isinstance(entry, dict):
            _err(errors, where, "应为对象")
            continue
        _require_enum(entry.get("source"), ANTI_PATTERN_SOURCES, f"{where}.source", errors)
        _require_str(entry, "rule", where, errors)


def validate_changes(changes: dict) -> list[str]:
    """校验一份章变更（LLM 产物），返回错误清单。"""
    if not isinstance(changes, dict):
        return ["changes: 应为对象"]
    errors: list[str] = []
    unknown = set(changes) - CHANGES_KEYS
    if unknown:
        _err(errors, "changes", f"未知字段：{', '.join(sorted(unknown))}")
    _require_int(changes, "chapter", "changes", errors, minimum=1)
    summary = changes.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        _err(errors, "changes", "summary 不能为空")
    elif len(summary) > SUMMARY_MAX_CHARS:
        _err(errors, "changes", f"summary 超过 {SUMMARY_MAX_CHARS} 字（当前 {len(summary)}）")
    if "word_count" in changes:
        _require_int(changes, "word_count", "changes", errors, minimum=0)
    _validate_changes_optional(changes, errors)
    return errors
