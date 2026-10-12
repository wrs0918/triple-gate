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
        # 同样的话出现在章节开头不算章末升华（尾部窗口为文末 600 可见字）
        text = "这一天，属于他的时代才刚刚开始。\n\n" + "他坐下来吃饭。菜是凉的。\n" * 60
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

    def test_voice_contrast_blocks(self):
        # 实战漏网句式：音量铺垫 + 转折（真人语料 20 章 0 命中）
        report = run_lint("他的声音不大，第一句却压住了整个大厅。")
        assert "voice-contrast" in [v.rule_id for v in report.blocking]

    def test_reverse_not_is_blocks(self):
        # 「是A，不是B」——not-is 的反序变种（限 2 次，3 次超限）
        text = "那是真嗓子，不是修音修出来的。那是本能，不是练习。那是天赋，不是努力。他接着往前走。"
        report = run_lint(text)
        assert "reverse-not-is" in [v.rule_id for v in report.blocking]

    def test_reverse_not_is_excludes_conjunction_prefix(self):
        # 「还是/只是/但是」等合成词里的「是」不是肯定项系动词
        report = run_lint("他还是不说话，不是不想说。他还是走了。")
        assert "reverse-not-is" not in [v.rule_id for v in report.blocking]

    def test_reverse_not_is_excludes_rhetorical_tail(self):
        # 「……，不是吗」是反问尾巴，不是反序对比
        report = run_lint("他赢的很干净，不是吗？")
        assert "reverse-not-is" not in [v.rule_id for v in report.blocking]

    def test_negation_parade_meiyou_form(self):
        # 「没有X，没有Y」同句连排（否定排比的另一家族）
        report = run_lint("没有伴奏，没有和声，没有提词器，他唱完了整首歌。")
        assert "negation-parade" in [v.rule_id for v in report.advisory]

    def test_trailer_ending_new_phrases(self):
        report = run_lint("他合上笔记本，熄了灯。\n\n没人知道，这场较量才刚刚开始。")
        assert "trailer-ending" in [v.rule_id for v in report.blocking]

    def test_trailer_summary_new_phrases(self):
        report = run_lint("枪声停了。\n\n这一夜，注定无人入眠。")
        assert "trailer-summary" in [v.rule_id for v in report.advisory]


class TestNarrativeMasking:
    """引号外叙述扫描：台词内的句式是口语，不算叙述层 AI 痕迹。"""

    def test_not_is_inside_quotes_exempt(self):
        # 引号内 3 次句式本会超限，掩码后全免（台词里的辩解是自然口语）
        text = "「这不是愤怒，而是绝望。这不是逃避，而是抵抗。这不是结束，而是开始。」老周摆手走了。"
        report = run_lint(text)
        assert "not-is-comparison" not in [v.rule_id for v in report.blocking]

    def test_not_is_outside_quotes_still_hits(self):
        text = "这不是愤怒，而是绝望。这不是逃避，而是抵抗。老周说得很清楚。这不是结束，而是开始。"
        report = run_lint(text)
        assert "not-is-comparison" in [v.rule_id for v in report.blocking]

    def test_trailer_inside_dialogue_exempt(self):
        text = "她说：「没人知道我藏在哪。」\n" + "他低头继续洗牌，牌面朝下，一张一张码好。\n" * 3
        report = run_lint(text)
        assert "trailer-ending" not in [v.rule_id for v in report.blocking]

    def test_placeholder_and_ai_leak_scan_everything(self):
        # 占位符与 AI 自我泄漏不豁免引号（安全类规则扫全文）
        report = run_lint("他说：「【待补：这里】作为一个AI我无法继续。」")
        assert "placeholder" in [v.rule_id for v in report.blocking]
        assert "ai-self-leak" in [v.rule_id for v in report.blocking]


class TestDensityRules:
    """密度型规则：命中次数与每千字密度双门槛同时达标才列出（防短文本误报）。"""

    def test_cliche_density_lists_when_dense(self):
        text = (
            "他仿佛看到一丝光。眼中闪过暖意，嘴角勾起，缓缓开口，深吸一口气。"
            "心中涌起一股暖流。不容置疑。不知何时，天亮了。"
        )
        report = run_lint(text)
        assert "cliche-density" in [v.rule_id for v in report.advisory]

    def test_cliche_sparse_not_listed(self):
        # 单个套词是正常中文，不列
        report = run_lint("他仿佛看到了什么，转身走了出去，没有再回来，也没有说话。")
        assert "cliche-density" not in [v.rule_id for v in report.advisory]

    def test_metaphor_density_lists(self):
        text = "他像木头一样站着。风好像刀。光如同水。她仿佛猫。声音像针。夜像是网。心宛如铁。脸犹如纸。"
        report = run_lint(text)
        assert "metaphor-density" in [v.rule_id for v in report.advisory]

    def test_stock_reaction_lists(self):
        text = "他的指尖轻轻收紧。她的指节泛白。他喉结滚动了一下。她眼眶发红。他的声音放低了些。她的胸口像被撞了一下。"
        report = run_lint(text)
        assert "stock-reaction" in [v.rule_id for v in report.advisory]

    def test_micro_action_tic_lists(self):
        text = "他拍了两下桌子。他松了口气。她点了下头。他皱了下眉。他看了眼门外。她叹了声道。"
        report = run_lint(text)
        assert "micro-action-tic" in [v.rule_id for v in report.advisory]

    def test_abstract_summary_lists(self):
        text = "这一刻他终于明白了一切。从这一刻开始，命运齿轮转动。命运棋局早有安排。前所未有的勇气涌上心头。"
        report = run_lint(text)
        assert "abstract-summary" in [v.rule_id for v in report.advisory]


class TestNewAdvisoryRules:
    def test_negation_pair(self):
        text = "他没有停步，也没有回头。他没有说话，也没再看她。他没有拒绝，也没有答应。"
        report = run_lint(text)
        assert "negation-pair" in [v.rule_id for v in report.advisory]

    def test_pad_verb(self):
        # 双音节填充：进行讨论→讨论
        report = run_lint("他们进行了讨论，随后加以说明，最后予以处理。")
        assert "pad-verb" in [v.rule_id for v in report.advisory]

    def test_connective_chain(self):
        report = run_lint("此外，他补充了数据，然而没有人听。因此方案同时需要修改，并且很快执行。")
        assert "connective-chain" in [v.rule_id for v in report.advisory]

    def test_second_person_in_narration(self):
        report = run_lint("你会发现，这座城市的规则很简单。")
        assert "second-person" in [v.rule_id for v in report.advisory]


class TestSpecialRules:
    def test_period_stutter(self):
        # 连续 6 个 ≤5 字叙述短句（拆句过狠的电报体）
        report = run_lint("他进门。坐下。喝水。抬头。看天。叹气。然后才慢慢平静下来。")
        assert "period-stutter" in [h.rule_id for h in report.hits]

    def test_period_stutter_not_dialogue(self):
        # 纯对话短句是正常形态，豁免
        report = run_lint("「好。」「嗯。」「走。」「行。」「嗯。」「好。」")
        assert "period-stutter" not in [h.rule_id for h in report.hits]

    def test_long_paragraph(self):
        report = run_lint("他走了很久。" * 40)  # 单段 >200 字
        assert "long-paragraph" in [h.rule_id for h in report.hits]

    def test_action_list(self):
        # 监控摄像头式动作清单：同段 ≥5 个通用动作动词 + ≥4 个分隔符
        report = run_lint("他伸手，拿起，推开，转身，放下，一气呵成。")
        assert "action-list" in [h.rule_id for h in report.hits]


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

    def test_benign_narration_zero_false_positive(self):
        # 日常叙述 + 对话 + 单个比喻：全部规则零命中（真人语料校准的底线）
        text = (
            "老陈把茶碗放下：「你说咋办就咋办，我听你的。」\n"
            "雨停了，他像往常一样收摊，推车往巷口走。车链子响了两声，他没管。\n"
            "三十年了，这条街他走了不知多少遍，闭着眼都认得。\n"
        )
        report = run_lint(text)
        assert report.blocking == []
        assert report.advisory == []

    def test_report_to_dict_roundtrip(self):
        report = run_lint("他不由得停下了脚步。")
        d = report.to_dict()
        assert d["passed"] is True
        assert "advisory" in d and "density_grade" in d
