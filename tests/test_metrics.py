"""metrics 层测试：指标计算 + band 区间判定（含降级策略）。"""

from scripts.metrics.bands import classify
from scripts.metrics.indicators import (
    burst_cv,
    clean_chars,
    connective_density,
    dialogue_ratio,
    equal_runs,
    lexical_density,
    paragraph_cv,
    particle_density,
    sentence_length_std,
    trigram_stats,
    ttr,
)


class TestSentenceStats:
    def test_uniform_sentences_low_std(self):
        sentences = ["他看了看窗外的风景。"] * 20
        assert sentence_length_std(sentences) < 5

    def test_varied_sentences_high_std(self):
        sentences = ["他走了。", "这句话到底能有多长呢长到让人窒息让人无法呼吸让人透不过气来。", "停。", "风把窗帘掀开了一角，露出外面灰蒙蒙的天。"]
        assert sentence_length_std(sentences) > 8

    def test_burst_cv_zero_when_uniform(self):
        assert burst_cv(["一样长的一二三。"] * 10) == 0.0

    def test_paragraph_cv(self):
        paras = ["短段。", "这是一个非常非常长的段落" * 10, "中段" * 3]
        assert paragraph_cv(paras) > 0.3


class TestTrigram:
    def test_repetitive_text_high_rep(self):
        text = "他感到一阵寒意他感到一阵寒意他感到一阵寒意他感到一阵寒意"
        rep, uniq = trigram_stats(text)
        assert rep > 0.10
        assert uniq < 0.85

    def test_varied_text_low_rep(self):
        text = "雨停了风起了灯灭了人走了茶凉了夜深了心冷了梦醒了"
        rep, uniq = trigram_stats(text)
        assert rep <= 0.08
        assert uniq >= 0.85


class TestTtr:
    def test_repetitive_text_low_ttr(self):
        ratio, degraded = ttr("一句话重复十遍一句话重复十遍一句话重复十遍一句话重复十遍")
        assert ratio < 0.40
        assert isinstance(degraded, bool)

    def test_varied_text_decent_ttr(self):
        text = "雨停了风起了灯灭了人走了茶凉了夜深了心冷了梦醒了天亮了街空了车来了客到了酒醒了债清了"
        ratio, _ = ttr(text)
        assert ratio > 0.4


class TestOthers:
    def test_dialogue_ratio(self):
        text = "他说：「这一句算对话内容。」旁白不算。"
        assert 0.2 < dialogue_ratio(text) < 0.6

    def test_dialogue_ratio_zero(self):
        assert dialogue_ratio("全是旁白没有任何引号。") == 0.0

    def test_lexical_density_returns_tuple(self):
        ratio, degraded = lexical_density("他快步走过长街，雨水打湿了肩膀。")
        assert 0.0 <= ratio <= 1.0
        assert isinstance(degraded, bool)

    def test_clean_chars_strips_symbols(self):
        assert "".join(clean_chars("你好，世界！abc 123")) == "你好世界abc123"


class TestEqualRuns:
    def test_uniform_sentences_all_triples(self):
        sentences = ["他看着眼前的景象，不由得感到一阵寒意。"] * 20
        # 20 个等长句 → 18 个相邻三元组全部近等长
        assert equal_runs(sentences) == 18

    def test_varied_sentences_zero(self):
        sentences = ["他走了。", "这句话到底能有多长呢长到让人窒息。", "停。", "风把窗帘掀开了一角。"]
        assert equal_runs(sentences) == 0

    def test_three_equal_count_one(self):
        assert equal_runs(["一样长短的句子。", "再写一样长短。", "三句完全等长。"]) == 1

    def test_empty_safe(self):
        assert equal_runs([]) == 0
        assert equal_runs(["只有一句。"]) == 0


class TestParticleDensity:
    def test_dialogue_rich_text_higher_than_narration(self):
        narration = "他走到门口，推开门，走进房间，坐下休息。"
        dialogue = "「走吧。」「你等等我啊。」「急什么呢，车还没来嘛。」"
        assert particle_density(dialogue) > particle_density(narration)

    def test_pure_narration_zero(self):
        assert particle_density("他推开门走进房间坐下打开了灯。") == 0.0


class TestConnectiveDensity:
    def test_chained_connectives_higher(self):
        chained = "然而因此此外同时所以但是然后并且"
        plain = "他吃完饭出门上班开会回家睡觉。"
        assert connective_density(chained) > connective_density(plain)

    def test_empty_text_zero(self):
        assert connective_density("") == 0.0


class TestBands:
    def test_sigma2_green_in_band(self):
        assert classify("sigma2", 15).status == "green"

    def test_sigma2_red_below(self):
        assert classify("sigma2", 3).status == "red"

    def test_sigma2_yellow_between(self):
        assert classify("sigma2", 6).status == "yellow"

    def test_sigma2_red_above_overcorrection(self):
        # 过度矫正：σ² 高到反常同样是红旗（sepia 的 band 原则）
        assert classify("sigma2", 60).status == "red"

    def test_trigram_rep_red_above(self):
        assert classify("trigram_rep", 0.12).status == "red"

    def test_trigram_rep_green(self):
        assert classify("trigram_rep", 0.05).status == "green"

    def test_ttr_degraded_forced_reference(self):
        # 无 jieba 时 TTR 降级为参考指标，永不判红
        assert classify("ttr", 0.1, degraded=True).status == "ref"

    def test_ttr_normal_gates(self):
        assert classify("ttr", 0.2, degraded=False).status == "red"

    def test_dialogue_ratio_is_reference_only(self):
        assert classify("dialogue_ratio", 0.0).status == "ref"

    def test_unknown_metric_is_reference(self):
        verdict = classify("nope", 1.0)
        assert verdict.status == "ref"
        assert "未知" in verdict.label

    def test_verdict_carries_direction(self):
        assert classify("sigma2", 3).direction != ""

    def test_equal_run_green(self):
        assert classify("equal_run", 2).status == "green"

    def test_equal_run_yellow(self):
        assert classify("equal_run", 8).status == "yellow"

    def test_equal_run_red_above(self):
        # 句长平坦：等长句连串爆表（人类语料中位约每百句 2 串）
        assert classify("equal_run", 20).status == "red"

    def test_burst_cv_demoted_to_reference(self):
        # OPACE-2026 实测句长 CV 阈值无鉴别力（AUROC≈0.52），降级为参考指标
        assert classify("burst_cv", 0.05).status == "ref"
        assert classify("burst_cv", 5.0).status == "ref"

    def test_particle_density_reference(self):
        assert classify("particle_density", 0.0).status == "ref"

    def test_connective_density_reference(self):
        assert classify("connective_density", 0.5).status == "ref"
