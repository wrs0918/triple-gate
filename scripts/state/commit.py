"""章提交：把一份通过校验的变更（LLM 产物）合并进状态真源。

不变量：
- 输入 state 绝不被修改（deepcopy 后返回新对象）
- 只有 layer1/layer2 门禁为 passed 的章才能提交
- state_revision 单调递增
"""

from __future__ import annotations

import copy
import re
from typing import Any

from scripts.state.schema import validate_changes, validate_state

_ID_PATTERN = re.compile(r"^([A-Z]+)-(\d+)$")
_DEFAULT_COOLDOWN = 10


def _ch_key(chapter: int) -> str:
    return f"ch{chapter:03d}"


def _next_id(entries: list[dict], prefix: str) -> str:
    max_seq = 0
    for entry in entries:
        match = _ID_PATTERN.match(str(entry.get("id", "")))
        if match and match.group(1) == prefix:
            max_seq = max(max_seq, int(match.group(2)))
    return f"{prefix}-{max_seq + 1:03d}"


def prepare_chapter(state: dict, chapter: int) -> dict:
    """为章创建 drafting 条目（幂等）。"""
    new = copy.deepcopy(state)
    key = _ch_key(chapter)
    if key not in new["chapters"]:
        new["chapters"][key] = {
            "status": "drafting",
            "gate_layer1": "pending",
            "gate_layer2": "pending",
            "gate_layer3": "pending",
        }
    return new


def record_gate(state: dict, chapter: int, layer: str, passed: bool) -> dict:
    """记录某一层门禁结果。layer 为 layer1/layer2/layer3。"""
    new = copy.deepcopy(state)
    key = _ch_key(chapter)
    if key not in new["chapters"]:
        new["chapters"][key] = {
            "status": "drafting",
            "gate_layer1": "pending",
            "gate_layer2": "pending",
            "gate_layer3": "pending",
        }
    new["chapters"][key][f"gate_{layer}"] = "passed" if passed else "failed"
    return new


def _merge_timeline(new: dict, changes: dict, chapter: int) -> None:
    for entry in changes.get("timeline_new") or []:
        item = dict(entry)
        item["chapter"] = chapter
        new["timeline"].append(item)


def _merge_foreshadowing(new: dict, changes: dict, chapter: int) -> None:
    for entry in changes.get("foreshadowing_planted") or []:
        new["foreshadowing"].append(
            {
                "id": _next_id(new["foreshadowing"], "F"),
                "content": entry["content"],
                "planted_ch": chapter,
                "status": "planted",
                "due_ch": entry.get("due_ch"),
                "priority": entry.get("priority", "mid"),
            }
        )
    for fid in changes.get("foreshadowing_paid") or []:
        target = [f for f in new["foreshadowing"] if f["id"] == fid]
        if not target:
            raise ValueError(f"伏笔 {fid} 不存在，无法标记回收")
        target[0]["status"] = "paid_off"


def _merge_hooks(new: dict, changes: dict, chapter: int) -> None:
    for entry in changes.get("hooks_new") or []:
        new["hooks"].append(
            {
                "id": _next_id(new["hooks"], "H"),
                "content": entry["content"],
                "deployed_ch": chapter,
                "status": "deployed",
            }
        )
    for hid in changes.get("hooks_rewarded") or []:
        target = [h for h in new["hooks"] if h["id"] == hid]
        if not target:
            raise ValueError(f"钩子 {hid} 不存在，无法标记回报")
        target[0]["status"] = "rewarded"


def _merge_tropes(new: dict, changes: dict, chapter: int) -> None:
    for name in changes.get("tropes_used") or []:
        target = [t for t in new["tropes"] if t["name"] == name]
        if target:
            if chapter not in target[0]["chapters"]:
                target[0]["chapters"].append(chapter)
        else:
            new["tropes"].append(
                {"name": name, "chapters": [chapter], "cooldown": _DEFAULT_COOLDOWN}
            )


def _merge_characters(new: dict, changes: dict) -> None:
    for update in changes.get("characters_update") or []:
        target = [c for c in new["characters"] if c["name"] == update["name"]]
        if not target:
            raise ValueError(f"角色「{update['name']}」不存在，请先在状态中登记")
        character = target[0]
        for key in ("emotion", "location"):
            if isinstance(update.get(key), str):
                character["state"][key] = update[key]
        for fact in update.get("known_facts_add") or []:
            if fact not in character["known_facts"]:
                character["known_facts"].append(fact)


def _merge_anti_patterns(new: dict, changes: dict, chapter: int) -> None:
    for entry in changes.get("anti_patterns_new") or []:
        new["anti_patterns"].append(
            {
                "added_ch": chapter,
                "source": entry["source"],
                "rule": entry["rule"],
                "note": entry.get("note", ""),
            }
        )


def apply_changes(state: dict, changes: dict) -> dict:
    """把章变更合并进状态，返回新状态（不修改输入）。

    Raises:
        ValueError: 变更非法 / 章号不匹配 / 门禁未通过 / 引用不存在的对象。
    """
    errors = validate_changes(changes)
    if errors:
        raise ValueError("章变更不合法：" + "；".join(errors))
    chapter = changes["chapter"]
    expected = state["progress"]["current_chapter"]
    if chapter != expected:
        raise ValueError(f"章节号不匹配：当前应提交第 {expected} 章，收到第 {chapter} 章")

    new = copy.deepcopy(state)
    key = _ch_key(chapter)
    entry: dict[str, Any] = new["chapters"].get(key)
    if entry is None:
        raise ValueError(f"第 {chapter} 章尚未 prewrite，无章条目可提交")

    for layer in ("gate_layer1", "gate_layer2"):
        if entry.get(layer) != "passed":
            raise ValueError(f"门禁未通过：{layer} 状态为 {entry.get(layer)}，禁止提交")

    entry["status"] = "final"
    entry["summary"] = changes["summary"]
    if "word_count" in changes:
        entry["word_count"] = changes["word_count"]

    _merge_timeline(new, changes, chapter)
    _merge_foreshadowing(new, changes, chapter)
    _merge_hooks(new, changes, chapter)
    _merge_tropes(new, changes, chapter)
    _merge_characters(new, changes)
    _merge_anti_patterns(new, changes, chapter)

    new["progress"]["current_chapter"] = chapter + 1
    new["progress"]["state_revision"] += 1

    errors = validate_state(new)
    if errors:
        raise ValueError("提交后状态不合法：" + "；".join(errors))
    return new
