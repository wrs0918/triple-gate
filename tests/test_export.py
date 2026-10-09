"""export 层测试：番茄平台导出。"""

from pathlib import Path

from scripts.export import export_fanqie


def _make_chapters(book_dir: Path) -> None:
    chapters = book_dir / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch001_final.md").write_text(
        "# 第1章 福尔马林\n\n**雨停了。**陈默蹲在台阶上。\n", encoding="utf-8"
    )
    (chapters / "ch002_final.md").write_text(
        "# 第2章 三号冷柜\n\n老周把登记本推过来。\n", encoding="utf-8"
    )
    (chapters / "ch001_draft.md").write_text("# 第1章 草稿不入导出\n\n", encoding="utf-8")


class TestExportFanqie:
    def test_exports_final_chapters_only(self, tmp_path):
        _make_chapters(tmp_path)
        files = export_fanqie(tmp_path)
        names = sorted(f.name for f in files)
        assert names == ["第001章.txt", "第002章.txt"]

    def test_output_location(self, tmp_path):
        _make_chapters(tmp_path)
        files = export_fanqie(tmp_path)
        assert all(f.parent == tmp_path / "exports" / "fanqie" for f in files)

    def test_content_has_title_line_and_strips_markdown(self, tmp_path):
        _make_chapters(tmp_path)
        files = export_fanqie(tmp_path)
        first = sorted(files)[0].read_text(encoding="utf-8")
        assert first.startswith("第1章 福尔马林")
        assert "**" not in first
        assert "陈默" in first

    def test_no_final_chapters_raises(self, tmp_path):
        (tmp_path / "chapters").mkdir()
        try:
            export_fanqie(tmp_path)
            raised = False
        except ValueError as exc:
            raised = "终稿" in str(exc)
        assert raised
