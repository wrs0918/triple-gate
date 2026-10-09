"""三层门禁编排：第一层（量化指标）＋第二层（模式 lint）＋写前阻断检查。

设计要点：
- 一、二层零 token：全部本地计算，LLM 只看结论
- 内容词密度跨版本对比监控「改稿指纹」（AI 改写会使内容词密度骤降）
- 写前阻断：动笔前先过检查，问题在生成前暴露
"""

from __future__ import annotations

import re

from scripts.core.textio import cjk_len, split_paragraphs, split_sentences, strip_markdown
from scripts.lint.rules import run_lint
from scripts.metrics.bands import classify
from scripts.metrics.indicators import (
    burst_cv,
    dialogue_ratio,
    lexical_density,
    paragraph_cv,
    sentence_length_std,
    trigram_stats,
    ttr,
)

_EDIT_FINGERPRINT_DELTA = -0.05


def run_layer1(text: str, previous_text: str | None = None) -> dict:
    """第一层：量化指标（band 区间判定）。"""
    prose = strip_markdown(text)
    sentences = split_sentences(prose)
    paragraphs = split_paragraphs(prose)
    rep, uniq = trigram_stats(prose)
    ttr_value, ttr_degraded = ttr(prose)
    density, density_degraded = lexical_density(prose)
    dial = dialogue_ratio(prose)

    values = {
        "sigma2": sentence_length_std(sentences),
        "burst_cv": burst_cv(sentences),
        "para_cv": paragraph_cv(paragraphs),
        "trigram_rep": rep,
        "trigram_uniq": uniq,
        "ttr": ttr_value,
        "dialogue_ratio": dial,
        "lexical_density": density,
    }
    degraded = {"ttr": ttr_degraded, "lexical_density": density_degraded}
    verdicts = [
        classify(metric, value, degraded=degraded.get(metric, False))
        for metric, value in values.items()
    ]
    warnings: list[str] = []
    if previous_text:
        prev_density, _ = lexical_density(strip_markdown(previous_text))
        delta = density - prev_density
        if delta < _EDIT_FINGERPRINT_DELTA:
            warnings.append(
                f"改稿指纹警告：内容词密度骤降 {delta:+.2f}"
                "（AI 改写的典型痕迹，保住名词与动词，删修饰不改内容）"
            )
    return {
        "word_count": cjk_len(prose),
        "passed": all(v.status != "red" for v in verdicts),
        "verdicts": [v.to_dict() for v in verdicts],
        "warnings": warnings,
        "jieba_degraded": ttr_degraded,
    }


def run_gate(text: str, whitelist: list[str] | None = None, previous_text: str | None = None) -> dict:
    """第一层＋第二层总装：机器门禁结果（第三层 rubric 由 LLM 按协议执行）。"""
    layer1 = run_layer1(text, previous_text=previous_text)
    lint_report = run_lint(strip_markdown(text), whitelist)
    return {
        "word_count": layer1["word_count"],
        "passed": layer1["passed"] and lint_report.passed,
        "layer1": layer1,
        "layer2": lint_report.to_dict(),
    }


def prewrite_checks(state: dict, outline_text: str, chapter: int) -> list[str]:
    """写前阻断检查：任何一条不过都不应开始写作。"""
    issues: list[str] = []
    progress = state["progress"]
    if progress["phase"] != "writing":
        issues.append(f"阶段不对：当前为 {progress['phase']}，需先通过 start 进入 writing")
    if chapter != progress["current_chapter"]:
        issues.append(
            f"章节号不匹配：当前应写第 {progress['current_chapter']} 章，收到第 {chapter} 章"
        )
    if not re.search(rf"^#+\s*第{chapter}章", outline_text, re.MULTILINE):
        issues.append(f"大纲缺少第 {chapter} 章条目（outline/outline.md 中需有「## 第{chapter}章」）")
    if chapter > 1:
        prev = state["chapters"].get(f"ch{chapter - 1:03d}")
        if prev is None or prev.get("status") != "final":
            issues.append(f"上一章（第 {chapter - 1} 章）未终稿，禁止跳章写作")
    return issues


def extract_outline_entry(outline_text: str, chapter: int) -> str:
    """从大纲中抽出本章条目（从本章标题到下一个章标题）。"""
    lines = outline_text.split("\n")
    collected: list[str] = []
    capturing = False
    for line in lines:
        if re.match(rf"^#+\s*第{chapter}章", line):
            capturing = True
            collected.append(line)
            continue
        if capturing and re.match(r"^#+\s*第\d+章", line):
            break
        if capturing:
            collected.append(line)
    return "\n".join(collected).strip()
