"""core.textio 测试：读取、markdown 剥离、切分。"""

import pytest

from scripts.core.textio import (
    cjk_len,
    read_text,
    split_paragraphs,
    split_sentences,
    strip_markdown,
)


class TestReadText:
    def test_reads_utf8_and_strips_bom(self, tmp_path):
        f = tmp_path / "ch.md"
        f.write_bytes("第一章\n\n正文。".encode("utf-8-sig"))
        assert read_text(f) == "第一章\n\n正文。"

    def test_missing_file_raises_friendly(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="不存在"):
            read_text(tmp_path / "nope.md")

    def test_empty_file_raises(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="为空"):
            read_text(f)


class TestStripMarkdown:
    def test_removes_heading_bold_quote(self):
        raw = "# 标题\n\n> 引用\n\n**加粗**的*斜体*正文，`代码`。"
        assert strip_markdown(raw) == "标题\n引用\n加粗的斜体正文，代码。"

    def test_keeps_chinese_punctuation(self):
        assert strip_markdown("他说：「走。」") == "他说：「走。」"


class TestSplitSentences:
    def test_splits_on_cjk_terminal(self):
        assert split_sentences("雨停了。风起了！") == ["雨停了。", "风起了！"]

    def test_splits_on_ellipsis_and_semicolon(self):
        assert split_sentences("他走了……；她哭了；") == ["他走了……", "她哭了；"]

    def test_drops_empty(self):
        assert split_sentences("。。。！！") == []


class TestSplitParagraphs:
    def test_splits_blank_lines(self):
        assert split_paragraphs("第一段。\n\n第二段。") == ["第一段。", "第二段。"]

    def test_splits_single_newline(self):
        assert split_paragraphs("第一行。\n第二行。") == ["第一行。", "第二行。"]


class TestCjkLen:
    def test_counts_only_cjk(self):
        assert cjk_len("abc你好世界123") == 4

    def test_empty(self):
        assert cjk_len("") == 0
