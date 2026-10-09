"""lint 层测试：规则命中、白名单、密度分档、阻断判定。"""

from scripts.lint.rules import run_lint


class TestBlockingRules:
    def test_not_is_over_limit_blocks(self):
        text = (
            "这不是愤怒，而是绝望。这不是逃避，而是抵抗。"
            "这不是结束，而是开始。这不是偶然，而是必然。"
        )
        report = run_lint(text)
        assert not report.passed
        ids = [v.rule_id for v in report.blocking]
        assert "not-is-comparison" in ids

    def test_not_is_within_limit_passes(self):
        text = "这不是愤怒，而是绝望。他坐下了。"
        report = run_lint(text)
        assert "not-is-comparison" not in [v.rule_id for v in report.blocking]

    def test_trailer_ending_blocks(self):
        text = "他望向远方。\n\n这一天，属于他的时代才刚刚开始。"
        report = run_lint(text)
        assert "trailer-ending" in [v.rule_id for v in report.blocking]

    def test_trailer_ending_only_scans_tail(self):
        # 同样的话出现在章节开头不算章末升华
        text = "这一天，属于他的时代才刚刚开始。\n\n" + "他坐下来吃饭。菜是凉的。\n" * 30
        report = run_lint(text)
        assert "trailer-ending" not in [v.rule_id for v in report.blocking]

    def test_placeholder_blocks(self):
        report = run_lint("他走进房间，看到了【待补：具体物件】。")
        assert "placeholder" in [v.rule_id for v in report.blocking]

    def test_ai_self_leak_blocks(self):
        report = run_lint("作为一个AI助手，我无法继续这个剧情。")
        assert "ai-self-leak" in [v.rule_id for v in report.blocking]

    def test_degeneration_blocks(self):
        report = run_lint("他把杯子放在桌上转过身走出门外带上了门。\n" * 3)
        assert "degeneration" in [v.rule_id for v in report.blocking]


class TestAdvisoryRules:
    def test_micro_tic_advisory(self):
        report = run_lint("她的眼底闪过一丝寒意，瞳孔微缩。")
        assert "micro-tic" in [v.rule_id for v in report.advisory]

    def test_fossil_adverb_advisory(self):
        report = run_lint("他不由得停下了脚步。")
        assert "fossil-adverb" in [v.rule_id for v in report.advisory]

    def test_gongwen_advisory(self):
        report = run_lint("综上所述，值得注意的是，这一切早有预兆。")
        assert "gongwen" in [v.rule_id for v in report.advisory]

    def test_hits_carry_line_number(self):
        text = "第一行没事。\n他不由得停下了脚步。"
        report = run_lint(text)
        hit = [h for h in report.hits if h.rule_id == "fossil-adverb"][0]
        assert hit.line == 2

    def test_hit_snippet_is_bounded(self):
        report = run_lint("他不由得停下了脚步。" * 1)
        assert all(len(h.snippet) <= 40 for h in report.hits)


class TestWhitelist:
    def test_whitelisted_term_suppressed(self):
        # 世界观术语：某族瞳孔异能设定，白名单后不再误报
        text = "她的瞳孔微缩——那是不死者一族觉醒的标志。"
        without = run_lint(text)
        with_wl = run_lint(text, whitelist=["不死者一族"])
        assert len(with_wl.advisory) < len(without.advisory)


class TestDensity:
    def test_light_grade(self):
        report = run_lint("他不由得停下了脚步。")
        assert report.density_grade == "轻"

    def test_heavy_grade(self):
        lines = [
            "他不由得停步，眼底闪过一丝异色，缓缓地说道：「值得注意。」",
        ] * 30
        report = run_lint("\n".join(lines))
        assert report.density_grade == "重"


class TestCleanText:
    def test_varied_text_passes(self):
        from conftest import varied_text

        report = run_lint(varied_text())
        assert report.passed
        assert report.blocking == []
        assert report.density_grade in ("轻", "中")

    def test_report_to_dict_roundtrip(self):
        report = run_lint("他不由得停下了脚步。")
        d = report.to_dict()
        assert d["passed"] is True
        assert "advisory" in d and "density_grade" in d
