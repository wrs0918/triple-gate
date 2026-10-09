"""gate 层测试：第一层指标编排、三层门禁总装、写前阻断检查、上下文组装。"""

from conftest import uniform_text, varied_text

from scripts.context import build_context
from scripts.gate import prewrite_checks, run_gate, run_layer1


class TestRunLayer1:
    def test_uniform_text_fails(self):
        report = run_layer1(uniform_text())
        assert report["passed"] is False
        sigma = [v for v in report["verdicts"] if v["metric"] == "sigma2"][0]
        assert sigma["status"] == "red"

    def test_varied_text_passes(self):
        report = run_layer1(varied_text())
        assert report["passed"] is True
        assert all(v["status"] != "red" for v in report["verdicts"])

    def test_word_count_recorded(self):
        report = run_layer1(varied_text())
        assert report["word_count"] > 100

    def test_edit_fingerprint_delta_warns(self):
        previous = "钢刀劈开铁链。火星溅上房梁。瓦片碎了一地。"
        current = "他的心里是很乱的，是很闷的，是很坏的一种感觉，是很复杂的。"
        report = run_layer1(current, previous_text=previous)
        assert any("改稿指纹" in w for w in report["warnings"])

    def test_no_warning_without_previous(self):
        report = run_layer1(varied_text())
        assert report["warnings"] == []


class TestRunGate:
    def test_combined_fail_on_lint_bomb(self):
        from conftest import lint_bomb_text

        report = run_gate(lint_bomb_text())
        assert report["passed"] is False
        assert report["layer2"]["blocking"] != []

    def test_combined_pass_on_varied(self):
        report = run_gate(varied_text())
        assert report["passed"] is True

    def test_whitelist_forwarded(self):
        from conftest import lint_bomb_text

        plain = run_gate(lint_bomb_text())
        wl = run_gate(lint_bomb_text(), whitelist=[])
        assert plain["layer2"] == wl["layer2"]


class TestPrewriteChecks:
    def test_ok(self, sample_state):
        outline = "## 第1章 福尔马林\n\n- 冲突：第一单生意"
        assert prewrite_checks(sample_state, outline, 1) == []

    def test_chapter_mismatch(self, sample_state):
        issues = prewrite_checks(sample_state, "## 第1章 x", 3)
        assert any("章节号" in i for i in issues)

    def test_missing_outline_entry(self, sample_state):
        issues = prewrite_checks(sample_state, "## 第99章 不存在的章\n", 1)
        assert any("大纲" in i for i in issues)

    def test_previous_chapter_not_final(self, sample_state):
        sample_state["progress"]["current_chapter"] = 2
        sample_state["chapters"]["ch001"] = {
            "status": "drafting", "gate_layer1": "pending",
            "gate_layer2": "pending", "gate_layer3": "pending",
        }
        issues = prewrite_checks(sample_state, "## 第2章 x", 2)
        assert any("未终稿" in i for i in issues)


class TestBuildContext:
    def test_contains_key_sections(self, sample_state):
        ctx = build_context(sample_state, "## 第1章 福尔马林\n- 冲突：第一单")
        assert "书魂卡" in ctx
        assert "第1章" in ctx
        assert "陈默" in ctx
        assert len(ctx) <= 12000

    def test_reader_timeline_only_revealed(self, sample_state):
        sample_state["timeline"].append(
            {"chapter": 0, "objective_fact": "幕后黑手是养父",
             "reader_knowledge": "幕后黑手是养父", "reveal_status": "hidden"}
        )
        ctx = build_context(sample_state, "## 第1章 x")
        assert "通感能力" in ctx        # partial 的条目在
        assert "幕后黑手" not in ctx    # hidden 的条目不在

    def test_urgent_foreshadowing_first(self, sample_state):
        sample_state["foreshadowing"] = [
            {"id": "F-001", "content": "超期未回收的伏笔", "planted_ch": 1,
             "status": "planted", "due_ch": 5, "priority": "high"},
            {"id": "F-002", "content": "刚埋的伏笔", "planted_ch": 1,
             "status": "planted", "due_ch": 40, "priority": "low"},
        ]
        sample_state["progress"]["current_chapter"] = 10
        ctx = build_context(sample_state, "## 第10章 x")
        assert "超期" in ctx

    def test_budget_drops_low_priority_first(self, sample_state):
        sample_state["anti_patterns"] = [
            {"added_ch": 1, "source": "lint", "rule": f"rule-{i}", "note": "禁忌" * 20}
            for i in range(50)
        ]
        ctx = build_context(sample_state, "## 第1章 x", budget=2000)
        assert "书魂卡" in ctx
        assert len(ctx) <= 2000

    def test_impossible_budget_raises(self, sample_state):
        import pytest

        with pytest.raises(ValueError, match="预算"):
            build_context(sample_state, "## 第1章 x" + "长" * 500, budget=200)

    def test_recent_summaries_included(self, sample_state):
        sample_state["chapters"]["ch001"] = {
            "status": "final", "gate_layer1": "passed", "gate_layer2": "passed",
            "gate_layer3": "passed", "summary": "第一章发生了大事",
        }
        sample_state["progress"]["current_chapter"] = 2
        ctx = build_context(sample_state, "## 第2章 x")
        assert "第一章发生了大事" in ctx
