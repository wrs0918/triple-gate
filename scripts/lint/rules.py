"""模式 lint：确定性正则规则 + 退化检测。

规则分级：
- blocking —— 超限即门禁不通过（替换、章末升华、占位符、AI 自我泄漏、复读）
- advisory —— 计入密度分档（轻/中/重），决定修复策略但不单独拦截

白名单：世界观术语所在的行会被整行豁免（防止「瞳孔」类词误报）。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from scripts.core.textio import cjk_len, split_sentences

# 章末规则的扫描窗口：最后 N 个非空行
_TAIL_LINES = 15
# 密度分档阈值：advisory 总命中数
_DENSITY_LIGHT = 3
_DENSITY_MID = 8
# 复读检测的最小句长
_DEGENERATION_MIN_LEN = 8


@dataclass(frozen=True)
class LintRule:
    """一条 lint 规则。limit 为章内允许的最大命中数。"""

    id: str
    severity: str  # "blocking" | "advisory"
    pattern: re.Pattern
    scope: str  # "full" | "tail"
    limit: int
    description: str
    direction: str


@dataclass(frozen=True)
class LintHit:
    rule_id: str
    line: int
    snippet: str
    direction: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "line": self.line,
            "snippet": self.snippet,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class LintViolation:
    rule_id: str
    severity: str
    count: int
    limit: int
    description: str
    direction: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "count": self.count,
            "limit": self.limit,
            "description": self.description,
            "direction": self.direction,
        }


@dataclass
class LintReport:
    blocking: list[LintViolation] = field(default_factory=list)
    advisory: list[LintViolation] = field(default_factory=list)
    hits: list[LintHit] = field(default_factory=list)
    density_grade: str = "轻"
    word_count: int = 0

    @property
    def passed(self) -> bool:
        return not self.blocking

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "blocking": [v.to_dict() for v in self.blocking],
            "advisory": [v.to_dict() for v in self.advisory],
            "hits": [h.to_dict() for h in self.hits],
            "density_grade": self.density_grade,
            "word_count": self.word_count,
        }


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern)


_RULE_TABLE: list[LintRule] = [
    LintRule(
        "not-is-comparison", "blocking",
        _compile(r"不是[^，。！？\n]{1,12}[，,][^，。！？\n]{0,4}而是|不是[^，。！？\n]{1,8}而是"),
        "full", 2,
        "「不是X，而是Y」句式", "X/Y 为具体可感名词时保留口语感；抽象概念对举时改为直接陈述事实",
    ),
    LintRule(
        "trailer-ending", "blocking",
        _compile(r"这一天[，,]这|而这[^，。\n]{0,8}(?:仅仅|只是)[^，。\n]{0,4}开始|属于(?:他|她|他们)的(?:时代|传奇|故事)|命运(?:的)?齿轮|他知道[，,][^，。\n]{0,6}(?:未来|等待|前方)"),
        "tail", 0,
        "章末预告式升华", "章尾停在具体动作或对话上，删掉展望未来的总结句",
    ),
    LintRule(
        "trailer-summary", "advisory",
        _compile(r"(?:他|她)终于明白|(?:他|她)意识到[，,]|这一刻[，,](?:他|她)"),
        "tail", 1,
        "章末总结陈词", "让读者自己得出结论，删掉点题句",
    ),
    LintRule(
        "placeholder", "blocking",
        _compile(r"【[^】]{0,20}(?:待补|待写|TODO|FIXME)[^】]{0,20}】|TODO|FIXME|（待补充）"),
        "full", 0,
        "占位符", "补全内容，终稿不允许占位符",
    ),
    LintRule(
        "ai-self-leak", "blocking",
        _compile(r"作为一个AI|作为一个人工智能|人工智能助手|我无法(?:协助|继续|提供)|很抱歉[，,]我(?:无法|不能)"),
        "full", 0,
        "AI 自我泄漏", "删除模型口吻残留，此类文本不得进入终稿",
    ),
    LintRule(
        "micro-tic", "advisory",
        _compile(r"瞳孔(?:微缩|骤缩|一缩|猛地一缩)|(?:眸光|眸底|眼底)(?:闪过|掠过|浮现)一?丝?|嘴角(?:勾起|噙着|扬起|抽动)一?抹?"),
        "full", 3,
        "微表情套话", "改为具体的身体动作或环境反应，同一微表情一章内不重复",
    ),
    LintRule(
        "fossil-adverb", "advisory",
        _compile(r"不由得|下意识地|心中一(?:凛|惊|沉|紧)|说不出的|莫名(?:地|的)|缓缓地|微微地"),
        "full", 5,
        "万能副词与口水词", "直接删掉副词，用动作本身体现节奏",
    ),
    LintRule(
        "em-dash-abuse", "advisory",
        _compile(r"——"),
        "full", 20,
        "破折号滥用", "破折号一章不超过 20 个，改用句号或逗号重新组织",
    ),
    LintRule(
        "negation-parade", "advisory",
        _compile(r"不是[^。！？\n]{1,12}[，,]也不是[^。！？\n]{1,12}[，,](?:更|也)不是"),
        "full", 1,
        "否定排比", "三连否定改为一次正面陈述",
    ),
    LintRule(
        "parallel-triple", "advisory",
        _compile(r"([^，。；\n]{2,8}的[^，。；\n]{1,5})[，,]\1[，,](?:更|也)?\1"),
        "full", 1,
        "工整三连排比", "打破对称：保留两项，第三项换成变奏或删除",
    ),
    LintRule(
        "explain-chain", "advisory",
        _compile(r"这意味着|换句话说|这背后(?:是|是)|换言之"),
        "full", 2,
        "解释链", "删掉元话语，让事件自己说话",
    ),
    LintRule(
        "gongwen", "advisory",
        _compile(r"值得注意的是|综上所述|由此可见|不言而喻|毋庸置疑|可见一斑"),
        "full", 1,
        "公文腔", "改为具体的事实或细节",
    ),
    LintRule(
        "emote-label", "advisory",
        _compile(r"(?:感到|觉得)[^，。！？\n]{0,4}(?:恐惧|愤怒|悲伤|不安|寒意|温暖|烦躁|震惊|绝望|喜悦)"),
        "full", 3,
        "情绪贴标签", "把情绪词换成生理反应＋当下动作",
    ),
    LintRule(
        "dialogue-tag", "advisory",
        _compile(r"说道|开口道|沉声道|淡淡道|沉吟道"),
        "full", 8,
        "对话标签单调", "多数对话直接给内容，或用动作代替「说道」",
    ),
    LintRule(
        "adj-stack", "advisory",
        _compile(r"(?:[一-鿿]{1,3}的){3,}[一-鿿]{1,4}"),
        "full", 2,
        "形容词堆砌", "每个名词前最多一个形容词，其余信息改由动作/环境呈现",
    ),
]

SPECIAL_RULES: list[LintRule] = [
    LintRule(
        "degeneration", "blocking", _compile(r""),
        "full", 0,
        "逐字复读", "同一句完整复现：删除重复内容",
    ),
]

ALL_RULES = _RULE_TABLE + SPECIAL_RULES


def _tail_line_numbers(lines: list[str]) -> set[int]:
    """返回最后 N 个非空行（0 起）的行号集合。"""
    non_empty = [i for i, line in enumerate(lines) if line.strip()]
    return set(non_empty[-_TAIL_LINES:]) if non_empty else set()


def _regex_hits(rule: LintRule, lines: list[str], tail: set[int], whitelist: list[str]) -> list[LintHit]:
    hits: list[LintHit] = []
    for lineno, line in enumerate(lines, 1):
        if rule.scope == "tail" and (lineno - 1) not in tail:
            continue
        for match in rule.pattern.finditer(line):
            snippet = match.group(0)[:40]
            if any(term in snippet or term in line for term in whitelist):
                continue
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


def _density_grade(total_hits: int) -> str:
    if total_hits <= _DENSITY_LIGHT:
        return "轻"
    if total_hits <= _DENSITY_MID:
        return "中"
    return "重"


def run_lint(text: str, whitelist: list[str] | None = None) -> LintReport:
    """对一章文本执行全部 lint 规则。"""
    whitelist = whitelist or []
    lines = text.split("\n")
    tail = _tail_line_numbers(lines)

    hits: list[LintHit] = []
    hits.extend(_degeneration_hits(text, whitelist))
    for rule in _RULE_TABLE:
        hits.extend(_regex_hits(rule, lines, tail, whitelist))

    report = LintReport(word_count=cjk_len(text))
    counts_by_rule = Counter(h.rule_id for h in hits)
    for rule in ALL_RULES:
        count = counts_by_rule.get(rule.id, 0)
        if count == 0:
            continue
        if rule.severity == "blocking" and count > rule.limit:
            report.blocking.append(
                LintViolation(rule.id, rule.severity, count, rule.limit, rule.description, rule.direction)
            )
        elif rule.severity == "advisory":
            report.advisory.append(
                LintViolation(rule.id, rule.severity, count, rule.limit, rule.description, rule.direction)
            )
    advisory_hit_total = sum(
        counts_by_rule.get(rule.id, 0) for rule in ALL_RULES if rule.severity == "advisory"
    )
    report.density_grade = _density_grade(advisory_hit_total)
    report.hits = hits
    return report
