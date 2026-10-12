"""量化指标计算：全部为纯函数，无副作用。

指标口径基于字符（CJK）而非分词，保证无第三方依赖时仍可计算；
jieba 可用时分词类指标（TTR、内容词密度）自动提升精度。
"""

from __future__ import annotations

import re
from collections import Counter

try:  # 可选依赖：未安装时走降级路径
    import jieba  # type: ignore
    import jieba.posseg  # type: ignore

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

_WHITESPACE = re.compile(r"\s")
_CJK_OR_ALNUM = re.compile(r"[一-鿿A-Za-z0-9]")
_QUOTED = re.compile(r"「[^」]*」|『[^』]*』|“[^”]*”")

# 降级路径下按字符近似内容词密度时，剔除的汉语功能字
_FUNCTION_CHARS = set("的了着过是在和与跟同也很都还又就把被让使对从向于为以及等地得")

# 语气词：HC3-zh 实测人类 0.016 vs ChatGPT 0.003（全部特征中差距最大，约 5 倍）
_PARTICLE_CHARS = set("啊吧呢嘛喔啦耶哟喽诶")
# 连词：HC3-zh 实测人类 0.013 vs ChatGPT 0.036（约 3 倍）；只收无歧义的多字连词
_CONNECTIVE_WORDS = ("以及", "并且", "同时", "此外", "因此", "然而", "但是", "所以", "然后", "不过", "于是")

# 等长句连串：人类语料中位约每百句 2 串；近等长容差取窗口最长句的 25%
_EQUAL_RUN_TOLERANCE = 0.25


def _visual_len(text: str) -> int:
    """可见长度：去空白后的字符数（含标点）。"""
    return len(_WHITESPACE.sub("", text))


def sentence_length_std(sentences: list[str]) -> float:
    """σ²：句长标准差（总体标准差）。句长均匀是典型的 AI 生成痕迹。"""
    lengths = [_visual_len(s) for s in sentences]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return round(variance ** 0.5, 2)


def burst_cv(sentences: list[str]) -> float:
    """BurstCV：句长变异系数（标准差/均值），句长的突发性。"""
    lengths = [_visual_len(s) for s in sentences]
    if not lengths:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return round((variance ** 0.5) / mean, 3)


def paragraph_cv(paragraphs: list[str]) -> float:
    """ParaCV：段长变异系数，段落长短交替程度。"""
    lengths = [_visual_len(p) for p in paragraphs]
    if not lengths:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return round((variance ** 0.5) / mean, 3)


def clean_chars(text: str) -> list[str]:
    """去标点空白后的字符序列（用于 n-gram）。"""
    return _CJK_OR_ALNUM.findall(text)


def trigram_stats(text: str) -> tuple[float, float]:
    """三元字组统计：返回 (重复率, 唯一率)。

    重复率 = 出现多于一次的额外次数 / 总数；唯一率 = 不同三元组数 / 总数。
    """
    chars = clean_chars(text)
    if len(chars) < 3:
        return 0.0, 1.0
    trigrams = ["".join(chars[i : i + 3]) for i in range(len(chars) - 2)]
    counts = Counter(trigrams)
    total = len(trigrams)
    extra = sum(c - 1 for c in counts.values() if c > 1)
    return round(extra / total, 4), round(len(counts) / total, 4)


def ttr(text: str) -> tuple[float, bool]:
    """TTR：用词多样性。返回 (比率, 是否降级)。

    jieba 可用时按词计算；否则按字符近似并标记降级。
    """
    chars = clean_chars(text)
    if not chars:
        return 0.0, not HAS_JIEBA
    if HAS_JIEBA:
        tokens = [w for w in jieba.lcut("".join(chars)) if w.strip()]
    else:
        tokens = chars
    if not tokens:
        return 0.0, not HAS_JIEBA
    return round(len(set(tokens)) / len(tokens), 4), not HAS_JIEBA


def lexical_density(text: str) -> tuple[float, bool]:
    """内容词密度：监控改稿指纹（AI 改稿会使其骤降）。返回 (比率, 是否降级)。"""
    chars = clean_chars(text)
    if not chars:
        return 0.0, not HAS_JIEBA
    if HAS_JIEBA:
        words = [w for w, _flag in jieba.posseg.lcut("".join(chars))]
        content = [
            w
            for w, flag in jieba.posseg.lcut("".join(chars))
            if flag.startswith(("n", "v", "a", "r", "m", "q"))
        ]
        return round(len(content) / len(words), 4), False if words else True
    content = [c for c in chars if c not in _FUNCTION_CHARS]
    return round(len(content) / len(chars), 4), True


def dialogue_ratio(text: str) -> float:
    """对话占比：引号内 CJK 字数 / 全文 CJK 字数。"""
    from scripts.core.textio import cjk_len

    total = cjk_len(text)
    if total == 0:
        return 0.0
    quoted = sum(cjk_len(seg) for seg in _QUOTED.findall(text))
    return round(quoted / total, 4)


def _window_near_equal(window: list[int]) -> bool:
    """窗口内各句长是否近等长（最长句的 25% 容差内）。"""
    longest = max(window)
    if longest == 0:
        return True
    return longest - min(window) <= _EQUAL_RUN_TOLERANCE * longest


def equal_runs(sentences: list[str]) -> int:
    """等长句连串数：相邻三元组内三句近等长的组数（滑动窗口，可重叠）。

    句长离散度是全部研究中方向唯一稳健的人机差异（人类 SD 更大）；
    人类语料中位约每百句 2 串，AI 生成文本句长平坦、连串显著偏多。
    """
    lengths = [_visual_len(s) for s in sentences]
    return sum(
        1
        for i in range(len(lengths) - 2)
        if _window_near_equal(lengths[i : i + 3])
    )


def particle_density(text: str) -> float:
    """语气词密度：啊/吧/呢/嘛/喔/啦/耶 等占可见字符比。

    口径为字符级（语料研究为词级，同方向不同量纲）；人类文本约为模型的 5 倍，
    密度过低（叙述通篇无语气词）是 AI 指纹，修法是对话与独白里自然撒入。
    """
    chars = clean_chars(text)
    if not chars:
        return 0.0
    hits = sum(1 for c in chars if c in _PARTICLE_CHARS)
    return round(hits / len(chars), 4)


def connective_density(text: str) -> float:
    """连词密度：以及/并且/同时/因此/然而 等占可见字符比。

    模型文本连词密度约为人类的 3 倍；连词串接是机器痕迹，
    修法是删掉连词、让并置（意合）承担衔接。
    """
    joined = "".join(clean_chars(text))
    if not joined:
        return 0.0
    hits = sum(joined.count(word) for word in _CONNECTIVE_WORDS)
    return round(hits / len(joined), 4)
