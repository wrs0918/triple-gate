"""模式 lint 引擎：规则执行、叙述掩码、尾部窗口、密度分档。

执行机制（移植自 oh-story check-ai-patterns 的实战设计）：
- 叙述掩码：narrative=True 的规则只扫引号外叙述——台词/系统播报里的
  「不是…而是」是自然口语，不算叙述层 AI 痕迹。掩码用等长「？」占位，
  保证命中偏移与原行对齐，摘录取自原文。
- 尾部窗口：tail 规则只扫文末 600 可见字（按行取整），正文中段的同类
  句式多为正常叙述，不误伤。
- 双门槛：密度型规则（per_kilo）须「章内次数 > limit 且每千字密度
  > per_kilo」同时成立才计入违例，防止短文本被单门槛误报。
- 密度分档：正文 ≥500 字按每千字密度分档（≤5 轻 / ≤15 中 / >15 重），
  短文本退回按次数分档（≤3 / ≤8 / >8）。
"""

from __future__ import annotations

import re
from collections import Counter

from scripts.core.textio import cjk_len, split_sentences
from scripts.lint.model import LintHit, LintReport, LintRule, LintViolation
from scripts.lint.patterns import ACTION_LIST_VERBS, ALL_RULES, RULE_TABLE

# 尾部窗口：文末 N 可见字（章末规则只扫这里）
_TAIL_WINDOW_CHARS = 600
# 密度分档：advisory 有效命中（长文本按每千字 / 短文本按次数）
_DENSITY_MIN_CHARS = 500
_DENSITY_PER_KILO_LIGHT = 5.0
_DENSITY_PER_KILO_MID = 15.0
_DENSITY_COUNT_LIGHT = 3
_DENSITY_COUNT_MID = 8
# 复读检测的最小句长
_DEGENERATION_MIN_LEN = 8
# 碎句号：连续 N 个 ≤M 可见字的叙述短句
_STUTTER_MIN_RUN = 6
_STUTTER_MAX_SENTENCE = 5
# 单段过长的字数线
_LONG_PARAGRAPH_CHARS = 200
# 监控摄像头式动作清单：同段动作动词与分隔符双门槛
_ACTION_LIST_MIN_HITS = 5
_ACTION_LIST_MIN_SEPARATORS = 4

_WHITESPACE_RE = re.compile(r"\s")
# 成对引号（台词/系统播报/术语）：一律不跨行，正文漏一个收引号很常见
_QUOTE_PAIRS = [("「", "」"), ("『", "』"), ("【", "】"), ("“", "”"), ("‘", "’"), ('"', '"')]
_QUOTE_SOURCES = [
    re.compile(rf"{re.escape(open_q)}[^{re.escape(close_q)}\n]*{re.escape(close_q)}")
    for open_q, close_q in _QUOTE_PAIRS
]
_SEPARATOR_RE = re.compile(r"[，、；,;]")


def _mask_quoted(line: str) -> str:
    """把引号片段等长替换为「？」占位：既豁免台词又保住偏移量。

    占位字符必须落在各规则否定类里（？与句号等效），但不能伪造句末断言符。
    """
    out = line
    for source in _QUOTE_SOURCES:
        out = source.sub(lambda m: "？" * len(m.group(0)), out)
    return out


def _strip_quoted(line: str) -> str:
    """整段去掉引号片段，只留叙述（碎句号/动作清单统计用）。"""
    out = line
    for source in _QUOTE_SOURCES:
        out = source.sub("", out)
    return out


def _visible_len(text: str) -> int:
    return len(_WHITESPACE_RE.sub("", text))


def _tail_line_numbers(lines: list[str]) -> set[int]:
    """文末窗口（0 起行号集合）：从末行往回收，累计可见字达到 600 为止，
    边界行整行计入。"""
    tail: set[int] = set()
    accumulated = 0
    for i in range(len(lines) - 1, -1, -1):
        if not lines[i].strip():
            continue
        tail.add(i)
        accumulated += _visible_len(lines[i])
        if accumulated >= _TAIL_WINDOW_CHARS:
            break
    return tail


def _regex_hits(rule: LintRule, lines: list[str], tail: set[int], whitelist: list[str]) -> list[LintHit]:
    hits: list[LintHit] = []
    for lineno, line in enumerate(lines, 1):
        if rule.scope == "tail" and (lineno - 1) not in tail:
            continue
        if any(term in line for term in whitelist):
            continue
        target = _mask_quoted(line) if rule.narrative else line
        for match in rule.pattern.finditer(target):
            snippet = line[match.start() : match.end()][:40]
            hits.append(LintHit(rule.id, lineno, snippet, rule.direction))
    return hits


def _degeneration_hits(text: str, whitelist: list[str]) -> list[LintHit]:
    """逐字复读检测：同一句（≥8 个可见字）出现两次以上。"""
    if any(term in text for term in whitelist):
        return []
    sentences = split_sentences(text)
    stripped = [re.sub(r"\s", "", s) for s in sentences]
    counts = Counter(s for s in stripped if len(s) >= _DEGENERATION_MIN_LEN)
    return [
        LintHit("degeneration", 0, f"「{sentence[:20]}」出现 {count} 次", "删除逐字重复的句子")
        for sentence, count in counts.items()
        if count >= 2
    ]


def _period_stutter_hits(lines: list[str], whitelist: list[str]) -> list[LintHit]:
    """碎句号：连续 ≥6 个 ≤5 字的引号外叙述短句；纯对话行重置计数。"""
    hits: list[LintHit] = []
    run_len = 0
    run_line = 0
    for lineno, line in enumerate(lines, 1):
        if any(term in line for term in whitelist):
            continue
        narrative = _strip_quoted(line)
        if not narrative.strip():
            run_len = 0
            continue
        for sentence in split_sentences(narrative):
            if _visible_len(sentence) <= _STUTTER_MAX_SENTENCE:
                if run_len == 0:
                    run_line = lineno
                run_len += 1
                if run_len == _STUTTER_MIN_RUN:
                    hits.append(
                        LintHit(
                            "period-stutter", run_line,
                            f"连续 {run_len} 个短句无呼吸",
                            "按节拍把碎句合并成中长句，补回画面与连接",
                        )
                    )
            else:
                run_len = 0
    return hits


def _long_paragraph_hits(lines: list[str], whitelist: list[str]) -> list[LintHit]:
    """单段过长：单行超过 200 字提示按镜头断段（手机阅读保守线）。"""
    return [
        LintHit("long-paragraph", lineno, f"段落 {len(line)} 字", "按镜头/新动作/新线索断段，别一段到底")
        for lineno, line in enumerate(lines, 1)
        if line.strip() and len(line) > _LONG_PARAGRAPH_CHARS
        and not any(term in line for term in whitelist)
    ]


def _action_list_hits(lines: list[str], whitelist: list[str]) -> list[LintHit]:
    """监控摄像头式动作清单：同段 ≥5 个通用动作动词且用 ≥4 个分隔符串成步骤表。"""
    hits: list[LintHit] = []
    for lineno, line in enumerate(lines, 1):
        if not line.strip() or any(term in line for term in whitelist):
            continue
        narrative = _strip_quoted(line)
        verbs = len(ACTION_LIST_VERBS.findall(narrative))
        if verbs < _ACTION_LIST_MIN_HITS:
            continue
        separators = len(_SEPARATOR_RE.findall(narrative))
        if separators < _ACTION_LIST_MIN_SEPARATORS:
            continue
        hits.append(
            LintHit(
                "action-list", lineno,
                f"同段动作动词 {verbs} 个、分隔符 {separators} 个",
                "合并琐碎步骤，只保留有情绪/情节功能的动作",
            )
        )
    return hits


def _density_grade(effective_hits: int, word_count: int) -> str:
    if word_count >= _DENSITY_MIN_CHARS:
        per_kilo = effective_hits / word_count * 1000
        if per_kilo <= _DENSITY_PER_KILO_LIGHT:
            return "轻"
        if per_kilo <= _DENSITY_PER_KILO_MID:
            return "中"
        return "重"
    if effective_hits <= _DENSITY_COUNT_LIGHT:
        return "轻"
    if effective_hits <= _DENSITY_COUNT_MID:
        return "中"
    return "重"


def run_lint(text: str, whitelist: list[str] | None = None) -> LintReport:
    """对一章文本执行全部 lint 规则。"""
    whitelist = whitelist or []
    lines = text.split("\n")
    tail = _tail_line_numbers(lines)

    hits: list[LintHit] = []
    hits.extend(_degeneration_hits(text, whitelist))
    hits.extend(_period_stutter_hits(lines, whitelist))
    hits.extend(_long_paragraph_hits(lines, whitelist))
    hits.extend(_action_list_hits(lines, whitelist))
    for rule in RULE_TABLE:
        hits.extend(_regex_hits(rule, lines, tail, whitelist))

    report = LintReport(word_count=cjk_len(text))
    counts_by_rule = Counter(h.rule_id for h in hits)
    effective_advisory_hits = 0
    for rule in ALL_RULES:
        count = counts_by_rule.get(rule.id, 0)
        if count == 0:
            continue
        if rule.severity == "blocking":
            if count > rule.limit:
                report.blocking.append(
                    LintViolation(rule.id, rule.severity, count, rule.limit, rule.description, rule.direction)
                )
            continue
        # advisory：密度型规则须「次数 + 每千字」双达标才列出（防短文本误报）
        listed = True
        if rule.per_kilo is not None:
            per_kilo = count / max(report.word_count, 1) * 1000
            listed = count > rule.limit and per_kilo > rule.per_kilo
        if listed:
            report.advisory.append(
                LintViolation(rule.id, rule.severity, count, rule.limit, rule.description, rule.direction)
            )
            effective_advisory_hits += count
    report.density_grade = _density_grade(effective_advisory_hits, report.word_count)
    report.hits = hits
    return report
