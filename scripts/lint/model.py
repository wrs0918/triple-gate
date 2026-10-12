"""lint 层数据模型：规则、命中、违例、报告。

规则字段：
- severity   blocking（超限即门禁不通过）/ advisory（计入密度分档）
- scope      full（整章扫描）/ tail（只扫文末窗口）
- narrative  True 表示只扫引号外叙述（台词/系统播报里的句式是口语，豁免）
- limit      章内允许的最大命中数
- per_kilo   每千字密度门槛：设置后须「次数与密度双达标」才计入违例（防短文本误报）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


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
    narrative: bool = False
    per_kilo: float | None = None


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
