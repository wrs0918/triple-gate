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
            "## 第1章 叙事 rubric 报告\n\n- 三个 pass 均通过\n", encoding="utf-8"
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
