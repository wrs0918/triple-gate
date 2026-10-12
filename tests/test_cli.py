"""CLI 端到端测试：init → start → prewrite → gate → commit → check → export。"""

import json

import pytest

from conftest import varied_text, write_text
from scripts.tg import main


def _run(*argv):
    return main(list(argv))


class TestInit:
    def test_init_creates_structure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code = _run("init", "--title", "测试之书", "--genre", "都市异能")
        assert code == 0
        assert (tmp_path / "book.json").exists()
        assert (tmp_path / "state" / "state.json").exists()
        assert (tmp_path / "outline" / "outline.md").exists()

    def test_status_after_init(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        code = _run("status")
        assert code == 0

    def test_start_requires_north_star(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        assert _run("start") == 1
        state_file = tmp_path / "state" / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["book"]["north_star"] = {
            "positioning": "都市异能，男频", "core_conflict": "主角 vs 垄断者",
            "power_cost": "读心但遗忘", "differentiation": "对比某爆款有代价",
            "city_industry": "滨江市/殡葬业",
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        assert _run("start") == 0
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["progress"]["phase"] == "writing"


class TestChapterLoop:
    def test_full_happy_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        state_file = tmp_path / "state" / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["book"]["north_star"] = {
            "positioning": "都市异能，男频", "core_conflict": "主角 vs 垄断者",
            "power_cost": "读心但遗忘", "differentiation": "对比某爆款有代价",
            "city_industry": "滨江市/殡葬业",
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        _run("start")
        outline = tmp_path / "outline" / "outline.md"
        outline.write_text("# 大纲\n\n## 第1章 福尔马林\n\n- 冲突：第一单生意\n", encoding="utf-8")

        assert _run("prewrite", "--chapter", "1") == 0
        assert (tmp_path / "projections" / "context.md").exists()

        write_text(tmp_path / "chapters" / "ch001_draft.md", varied_text())
        assert _run("gate", "--file", "chapters/ch001_draft.md", "--chapter", "1") == 0
        gate_json = json.loads((tmp_path / "qa" / "ch001_gate.json").read_text(encoding="utf-8"))
        assert gate_json["passed"] is True

        changes = {
            "chapter": 1,
            "summary": "陈默接到第一单生意。",
            "timeline_new": [],
            "foreshadowing_planted": [],
            "foreshadowing_paid": [],
            "hooks_new": [],
            "hooks_rewarded": [],
            "tropes_used": [],
            "characters_update": [],
            "anti_patterns_new": [],
        }
        changes_file = tmp_path / "qa" / "ch001_changes.json"
        changes_file.write_text(json.dumps(changes, ensure_ascii=False), encoding="utf-8")
        (tmp_path / "qa" / "ch001_rubric.md").write_text(
            "# 第1章 rubric 报告\n\n- 三个 pass 均通过\n\n## 结论\n阻断级发现 0 条\n",
            encoding="utf-8",
        )
        (tmp_path / "chapters" / "ch001_final.md").write_text(
            "# 第1章 福尔马林\n\n" + varied_text(), encoding="utf-8"
        )
        assert _run("commit", "--chapter", "1", "--changes", str(changes_file)) == 0

        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["progress"]["current_chapter"] == 2
        assert (tmp_path / "projections" / "timeline.md").exists()

        assert _run("check") == 0

    def test_gate_failure_marks_state(self, tmp_path, monkeypatch):
        from conftest import uniform_text

        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        state_file = tmp_path / "state" / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["book"]["north_star"] = {
            "positioning": "都市异能，男频", "core_conflict": "主角 vs 垄断者",
            "power_cost": "读心但遗忘", "differentiation": "对比某爆款有代价",
            "city_industry": "滨江市/殡葬业",
        }
        state["progress"]["phase"] = "writing"
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        write_text(tmp_path / "chapters" / "ch001_draft.md", uniform_text())
        assert _run("gate", "--file", "chapters/ch001_draft.md", "--chapter", "1") == 1
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["chapters"]["ch001"]["gate_layer1"] == "failed"

    def test_check_detects_tamper(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        target = tmp_path / "projections" / "timeline.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("手改\n", encoding="utf-8")
        assert _run("check") == 1


class TestExportCli:
    def test_export_creates_fanqie_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        chapters = tmp_path / "chapters"
        chapters.mkdir(exist_ok=True)
        (chapters / "ch001_final.md").write_text("# 第1章 福尔马林\n\n雨停了。\n", encoding="utf-8")
        assert _run("export") == 0
        assert (tmp_path / "exports" / "fanqie" / "第001章.txt").exists()


def _prepare_committable(tmp_path, monkeypatch):
    """走完 init→start→prewrite→gate，备好 commit 前置产物，返回 (state_file, changes_file)。"""
    monkeypatch.chdir(tmp_path)
    _run("init", "--title", "测试之书", "--genre", "都市异能")
    state_file = tmp_path / "state" / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["book"]["north_star"] = {
        "positioning": "都市异能，男频", "core_conflict": "主角 vs 垄断者",
        "power_cost": "读心但遗忘", "differentiation": "对比某爆款有代价",
        "city_industry": "滨江市/殡葬业",
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    _run("start")
    (tmp_path / "outline" / "outline.md").write_text(
        "# 大纲\n\n## 第1章 福尔马林\n\n- 冲突：第一单生意\n", encoding="utf-8"
    )
    assert _run("prewrite", "--chapter", "1") == 0
    write_text(tmp_path / "chapters" / "ch001_draft.md", varied_text())
    assert _run("gate", "--file", "chapters/ch001_draft.md", "--chapter", "1") == 0
    changes_file = tmp_path / "qa" / "ch001_changes.json"
    changes_file.write_text(
        json.dumps({"chapter": 1, "summary": "陈默接到第一单生意。"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "qa" / "ch001_rubric.md").write_text(
        "# 第1章 rubric 报告\n\n## 结论\n阻断级发现 0 条\n", encoding="utf-8"
    )
    write_text(tmp_path / "chapters" / "ch001_final.md", "# 第1章 福尔马林\n\n" + varied_text())
    return state_file, changes_file


class TestCommitHardening:
    """commit 的代码强制：章号交叉核对、rubric 有效性、终稿重跑机器门禁。"""

    def test_rejects_chapter_mismatch(self, tmp_path, monkeypatch, capsys):
        state_file, changes_file = _prepare_committable(tmp_path, monkeypatch)
        code = _run("commit", "--chapter", "2", "--changes", str(changes_file))
        assert code == 2
        assert "章号" in capsys.readouterr().err
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["progress"]["current_chapter"] == 1

    def test_regates_final_and_blocks_lint_bomb(self, tmp_path, monkeypatch):
        from conftest import lint_bomb_text

        state_file, changes_file = _prepare_committable(tmp_path, monkeypatch)
        # rubric 修复引入的新硬伤：草稿过了门禁，但终稿不过 → 必须拒绝提交
        write_text(tmp_path / "chapters" / "ch001_final.md", lint_bomb_text())
        assert _run("commit", "--chapter", "1", "--changes", str(changes_file)) == 1
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["progress"]["current_chapter"] == 1
        assert state["chapters"]["ch001"]["status"] == "drafting"
        report = json.loads((tmp_path / "qa" / "ch001_gate.json").read_text(encoding="utf-8"))
        assert report["passed"] is False

    def test_rejects_empty_rubric(self, tmp_path, monkeypatch):
        state_file, changes_file = _prepare_committable(tmp_path, monkeypatch)
        (tmp_path / "qa" / "ch001_rubric.md").write_text("", encoding="utf-8")
        assert _run("commit", "--chapter", "1", "--changes", str(changes_file)) == 1
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["progress"]["current_chapter"] == 1

    def test_rejects_rubric_without_conclusion(self, tmp_path, monkeypatch):
        state_file, changes_file = _prepare_committable(tmp_path, monkeypatch)
        (tmp_path / "qa" / "ch001_rubric.md").write_text("# 只有标题\n", encoding="utf-8")
        assert _run("commit", "--chapter", "1", "--changes", str(changes_file)) == 1
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["progress"]["current_chapter"] == 1

    def test_happy_path_records_layer3(self, tmp_path, monkeypatch):
        state_file, changes_file = _prepare_committable(tmp_path, monkeypatch)
        assert _run("commit", "--chapter", "1", "--changes", str(changes_file)) == 0
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["chapters"]["ch001"]["gate_layer3"] == "passed"
        assert state["progress"]["current_chapter"] == 2


class TestErrors:
    def test_gate_missing_file_friendly(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        code = _run("gate", "--file", "chapters/nope.md", "--chapter", "1")
        assert code == 2
        out = capsys.readouterr().err
        assert "不存在" in out

    def test_commit_with_bad_changes_json(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _run("init", "--title", "测试之书", "--genre", "都市异能")
        bad = tmp_path / "qa" / "bad.json"
        bad.parent.mkdir(exist_ok=True)
        bad.write_text("{not json", encoding="utf-8")
        code = _run("commit", "--chapter", "1", "--changes", str(bad))
        assert code == 2
