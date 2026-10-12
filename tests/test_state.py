"""state 层测试：schema 校验、原子读写、章提交合并、投影渲染。"""

import json

import pytest

from scripts.state.commit import apply_changes, prepare_chapter, record_gate
from scripts.state.render import check_projections, render_projections
from scripts.state.schema import validate_changes, validate_state
from scripts.state.store import load_state, save_state


def _changes(**overrides):
    base = {
        "chapter": 1,
        "summary": "陈默接到第一单生意，死者开口说话。",
        "timeline_new": [
            {
                "objective_fact": "死者死于丈夫之手",
                "reader_knowledge": "读者已知死者死于他杀",
                "reveal_status": "hidden",
            }
        ],
        "foreshadowing_planted": [
            {"content": "死者手腕的旧疤", "due_ch": 10, "priority": "high"}
        ],
        "foreshadowing_paid": [],
        "hooks_new": [{"content": "「帮我找一个人」", "type": "章尾悬念"}],
        "hooks_rewarded": [],
        "tropes_used": ["冷开场"],
        "characters_update": [
            {"name": "陈默", "emotion": "警觉", "known_facts_add": ["死者会说话"]}
        ],
        "anti_patterns_new": [
            {"source": "lint", "rule": "micro-tic", "note": "眼底闪过一丝×2"}
        ],
    }
    base.update(overrides)
    return base


def _ready(state: dict, chapter: int = 1) -> dict:
    """prewrite + 双层门禁通过，可提交状态。"""
    state = prepare_chapter(state, chapter)
    state = record_gate(state, chapter, "layer1", True)
    state = record_gate(state, chapter, "layer2", True)
    return state


class TestSchemaState:
    def test_valid_state_passes(self, sample_state):
        assert validate_state(sample_state) == []

    def test_missing_north_star_field_fails(self, sample_state):
        del sample_state["book"]["north_star"]["core_conflict"]
        errors = validate_state(sample_state)
        assert any("core_conflict" in e for e in errors)

    def test_bad_phase_enum_fails(self, sample_state):
        sample_state["progress"]["phase"] = "跑路"
        assert any("phase" in e for e in validate_state(sample_state))

    def test_bad_reveal_status_fails(self, sample_state):
        sample_state["timeline"][0]["reveal_status"] = "maybe"
        assert any("reveal_status" in e for e in validate_state(sample_state))

    def test_state_foreshadowing_due_ch_must_be_int(self, sample_state):
        sample_state["foreshadowing"] = [
            {"id": "F-001", "content": "旧疤", "planted_ch": 1, "status": "planted",
             "due_ch": "10", "priority": "high"}
        ]
        assert any("due_ch" in e for e in validate_state(sample_state))

    def test_planning_phase_allows_empty_north_star(self, sample_state):
        sample_state["progress"]["phase"] = "planning"
        sample_state["book"]["north_star"] = {
            "positioning": "", "core_conflict": "", "power_cost": "",
            "differentiation": "", "city_industry": "",
        }
        assert validate_state(sample_state) == []


class TestSchemaChanges:
    def test_valid_changes_passes(self):
        assert validate_changes(_changes()) == []

    def test_missing_chapter_fails(self):
        errors = validate_changes({"summary": "缺章号"})
        assert any("chapter" in e for e in errors)

    def test_overlong_summary_fails(self):
        errors = validate_changes(_changes(summary="长" * 301))
        assert any("summary" in e for e in errors)

    def test_bad_timeline_enum_fails(self):
        bad = _changes(timeline_new=[{"objective_fact": "x", "reader_knowledge": "y", "reveal_status": "猜"}])
        assert any("reveal_status" in e for e in validate_changes(bad))

    def test_due_ch_must_be_int(self):
        # LLM 常把章号写成字符串；不拦住会在渲染时 TypeError 并污染已落盘状态
        bad = _changes(foreshadowing_planted=[{"content": "伏笔", "due_ch": "20", "priority": "high"}])
        assert any("due_ch" in e for e in validate_changes(bad))

    def test_due_ch_optional(self):
        changes = _changes(foreshadowing_planted=[{"content": "伏笔", "priority": "high"}])
        assert validate_changes(changes) == []

    def test_hooks_new_requires_content(self):
        bad = _changes(hooks_new=[{"type": "章尾悬念"}])
        assert any("content" in e for e in validate_changes(bad))

    def test_hooks_rewarded_must_be_str_list(self):
        bad = _changes(hooks_rewarded=[{"id": "H-001"}])
        assert any("hooks_rewarded" in e for e in validate_changes(bad))

    def test_known_facts_add_must_be_str_list(self):
        # 单字符串会被逐字拆开污染 known_facts，必须在schema层拦下
        bad = _changes(characters_update=[{"name": "陈默", "known_facts_add": "他知道凶手"}])
        assert any("known_facts_add" in e for e in validate_changes(bad))

    def test_foreshadowing_paid_must_be_str_list(self):
        bad = _changes(foreshadowing_paid=[{"id": "F-001"}])
        assert any("foreshadowing_paid" in e for e in validate_changes(bad))


class TestStore:
    def test_roundtrip(self, tmp_path, sample_state):
        f = tmp_path / "state.json"
        save_state(f, sample_state)
        assert load_state(f) == sample_state

    def test_load_missing_raises_friendly(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="不存在"):
            load_state(tmp_path / "nope.json")

    def test_load_invalid_raises_with_errors(self, tmp_path, sample_state):
        sample_state["progress"]["phase"] = "乱写"
        f = tmp_path / "state.json"
        # 直接落盘非法状态（save_state 会拒绝写非法数据，这里模拟外部篡改）
        f.write_text(json.dumps(sample_state, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError, match="phase"):
            load_state(f)

    def test_save_state_rejects_invalid(self, tmp_path, sample_state):
        sample_state["progress"]["phase"] = "乱写"
        with pytest.raises(ValueError, match="拒绝写入"):
            save_state(tmp_path / "state.json", sample_state)

    def test_save_atomic_overwrites(self, tmp_path, sample_state):
        f = tmp_path / "state.json"
        save_state(f, sample_state)
        modified = {**sample_state, "progress": {**sample_state["progress"], "current_chapter": 5}}
        save_state(f, modified)
        assert load_state(f)["progress"]["current_chapter"] == 5


class TestCommit:
    def test_prepare_and_gate_then_apply(self, sample_state):
        state = prepare_chapter(sample_state, 1)
        state = record_gate(state, 1, "layer1", True)
        state = record_gate(state, 1, "layer2", True)
        new = apply_changes(state, _changes())
        ch = new["chapters"]["ch001"]
        assert ch["status"] == "final"
        assert ch["gate_layer1"] == "passed"
        assert ch["gate_layer2"] == "passed"
        assert new["progress"]["current_chapter"] == 2
        assert new["progress"]["state_revision"] == sample_state["progress"]["state_revision"] + 1

    def test_planted_foreshadowing_gets_id(self, sample_state):
        state = _ready(sample_state)
        new = apply_changes(state, _changes())
        assert new["foreshadowing"][0]["id"] == "F-001"
        assert new["foreshadowing"][0]["planted_ch"] == 1

    def test_payoff_existing_foreshadowing(self, sample_state):
        sample_state["foreshadowing"] = [
            {"id": "F-001", "content": "旧疤", "planted_ch": 1, "status": "planted", "due_ch": 10, "priority": "high"}
        ]
        state = _ready(sample_state)
        new = apply_changes(state, _changes(foreshadowing_paid=["F-001"]))
        assert new["foreshadowing"][0]["status"] == "paid_off"

    def test_payoff_unknown_id_raises(self, sample_state):
        state = _ready(sample_state)
        with pytest.raises(ValueError, match="F-999"):
            apply_changes(state, _changes(foreshadowing_paid=["F-999"]))

    def test_chapter_mismatch_raises(self, sample_state):
        state = prepare_chapter(sample_state, 1)
        with pytest.raises(ValueError, match="当前应提交"):
            apply_changes(state, _changes(chapter=7))

    def test_input_state_not_mutated(self, sample_state):
        state = _ready(sample_state)
        # 原样拷贝一份用于对比
        frozen = json.loads(json.dumps(state))
        apply_changes(state, _changes())
        assert state == frozen

    def test_characters_update_merges(self, sample_state):
        state = _ready(sample_state)
        new = apply_changes(state, _changes())
        chen = [c for c in new["characters"] if c["name"] == "陈默"][0]
        assert chen["state"]["emotion"] == "警觉"
        assert "死者会说话" in chen["known_facts"]
        assert "养父失踪" in chen["known_facts"]  # 原有事实保留

    def test_gate_not_passed_blocks_commit(self, sample_state):
        state = prepare_chapter(sample_state, 1)
        state = record_gate(state, 1, "layer1", False)
        with pytest.raises(ValueError, match="门禁"):
            apply_changes(state, _changes())

    def test_string_due_ch_rejected_cleanly(self, sample_state):
        # 回归：字符串 due_ch 必须在合并前被 schema 拦下（曾导致渲染 TypeError）
        state = _ready(sample_state)
        with pytest.raises(ValueError, match="due_ch"):
            apply_changes(state, _changes(
                foreshadowing_planted=[{"content": "伏笔", "due_ch": "20", "priority": "high"}]
            ))


class TestRender:
    def test_render_and_check_consistent(self, tmp_path, sample_state):
        state = _ready(sample_state)
        state = apply_changes(state, _changes())
        render_projections(state, tmp_path)
        assert check_projections(state, tmp_path) == []

    def test_tampered_projection_detected(self, tmp_path, sample_state):
        state = _ready(sample_state)
        state = apply_changes(state, _changes())
        render_projections(state, tmp_path)
        target = tmp_path / "foreshadowing.md"
        target.write_text("手改的内容\n", encoding="utf-8")
        mismatches = check_projections(state, tmp_path)
        assert any("foreshadowing" in m for m in mismatches)

    def test_timeline_shows_dual_columns(self, tmp_path, sample_state):
        state = _ready(sample_state)
        state = apply_changes(state, _changes())
        render_projections(state, tmp_path)
        content = (tmp_path / "timeline.md").read_text(encoding="utf-8")
        assert "作者真相" in content and "读者已知" in content

    def test_render_escapes_pipe_in_cells(self, tmp_path, sample_state):
        # LLM 产出的内容含竖线会撑破 markdown 表格，渲染时必须转义
        sample_state["timeline"].append({
            "chapter": 1, "objective_fact": "A|B 两套计划",
            "reader_knowledge": "读者知道 A|B", "reveal_status": "revealed",
        })
        render_projections(sample_state, tmp_path)
        content = (tmp_path / "timeline.md").read_text(encoding="utf-8")
        assert "A\\|B" in content
        assert check_projections(sample_state, tmp_path) == []

    def test_overdue_foreshadowing_marked(self, tmp_path, sample_state):
        sample_state["foreshadowing"] = [
            {"id": "F-001", "content": "超期的伏笔", "planted_ch": 1, "status": "planted", "due_ch": 5, "priority": "high"}
        ]
        sample_state["progress"]["current_chapter"] = 10
        render_projections(sample_state, tmp_path)
        content = (tmp_path / "foreshadowing.md").read_text(encoding="utf-8")
        assert "超期" in content
