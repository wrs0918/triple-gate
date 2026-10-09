"""band 区间判定：单一阈值来源。

设计原则（来自语料研究的两条硬约束）：
1. 人类区间是带（band）不是极值——过度矫正到反方向极端会制造新的 AI 指纹，
   因此 green 两侧都设有 red 上界（red_above）。
2. 依赖分词的指标（TTR）在降级模式（无 jieba）下只作参考，永不判红。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """一个指标的判定区间。

    green: 人类区间 (下界, 上界)
    red_below / red_above: 越界即红；None 表示该侧不设红界
    gate: False 表示参考指标，只展示不判定
    """

    key: str
    label: str
    green: tuple[float, float]
    red_below: float | None
    red_above: float | None
    gate: bool
    direction: str


@dataclass(frozen=True)
class Verdict:
    """单项指标判定结果。"""

    metric: str
    status: str  # "red" | "yellow" | "green" | "ref"
    label: str
    value: float
    direction: str

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "status": self.status,
            "label": self.label,
            "value": self.value,
            "direction": self.direction,
        }


BANDS: dict[str, Band] = {
    "sigma2": Band(
        "sigma2", "σ²(句长标准差)", (8, 35), 5, 50, True,
        "长短句交替：拆开超长句、合并碎短句，制造节奏起伏",
    ),
    "burst_cv": Band(
        "burst_cv", "BurstCV(句长变异系数)", (0.40, 1.20), 0.30, 1.50, True,
        "让句子长短突发：连续短句后接一个长句，避免均匀节奏",
    ),
    "para_cv": Band(
        "para_cv", "ParaCV(段长变异系数)", (0.30, 1.20), 0.20, 1.50, True,
        "段落长短交替：单行段与多行段穿插，避免豆腐块",
    ),
    "trigram_rep": Band(
        "trigram_rep", "3gram重复率", (0.0, 0.08), None, 0.10, True,
        "替换重复的固定表达，同一措辞一章内不要反复出现",
    ),
    "trigram_uniq": Band(
        "trigram_uniq", "3gram唯一率", (0.85, 1.0), 0.70, None, True,
        "增加用词多样性，避免句式复读",
    ),
    "ttr": Band(
        "ttr", "TTR(用词多样性)", (0.40, 0.75), 0.30, 0.90, True,
        "替换高频词为同义表达，加入角色习惯用语；不必堆生僻词",
    ),
    "dialogue_ratio": Band(
        "dialogue_ratio", "对话占比", (0.05, 0.65), 0.0, 0.75, False,
        "参考指标：对话与叙述按情节需要配比",
    ),
    "lexical_density": Band(
        "lexical_density", "内容词密度", (0.0, 1.0), None, None, False,
        "参考指标：监控改稿指纹，AI 改写会使内容词密度骤降",
    ),
}

_DEGRADED_METRICS = {"ttr"}


def classify(metric: str, value: float, degraded: bool = False) -> Verdict:
    """把指标值判为 red / yellow / green / ref。"""
    band = BANDS.get(metric)
    if band is None:
        return Verdict(metric, "ref", f"{metric}(未知指标)", value, "")
    if not band.gate:
        return Verdict(metric, "ref", band.label, value, band.direction)
    if degraded and metric in _DEGRADED_METRICS:
        return Verdict(metric, "ref", f"{band.label}·降级参考", value, band.direction)
    if band.red_below is not None and value < band.red_below:
        status = "red"
    elif band.red_above is not None and value > band.red_above:
        status = "red"
    elif value < band.green[0]:
        status = "yellow"
    elif value > band.green[1]:
        status = "yellow"
    else:
        status = "green"
    return Verdict(metric, status, band.label, value, band.direction)
