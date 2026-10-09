"""测试夹具：构造已知统计特征的中文样本文本。"""

import json
from pathlib import Path

import pytest

STATE_TEMPLATE = {
    "schema_version": 1,
    "book": {
        "title": "测试之书",
        "genre": "都市异能",
        "platform": "fanqie",
        "north_star": {
            "positioning": "都市异能，目标读者：男频 18-30",
            "core_conflict": "主角 vs 行业垄断者，赌注是全城人的记忆",
            "power_cost": "读取记忆的能力，每次使用遗忘自己一段记忆",
            "differentiation": "对比《大王饶命》：金手指有代价而非无敌",
            "city_industry": "滨江市/殡葬业，殡葬业决定死者记忆归属",
        },
    },
    "progress": {"phase": "writing", "current_chapter": 1, "state_revision": 0},
    "chapters": {},
    "timeline": [
        {
            "chapter": 0,
            "objective_fact": "主角能读取死者记忆（作者真相）",
            "reader_knowledge": "读者已知主角有通感能力，细节未知",
            "reveal_status": "partial",
        }
    ],
    "foreshadowing": [],
    "hooks": [],
    "tropes": [],
    "characters": [
        {
            "name": "陈默",
            "role": "主角",
            "state": {"emotion": "压抑", "location": "殡仪馆"},
            "known_facts": ["养父失踪"],
            "speech_print": "短句，几乎不用语气词",
        }
    ],
    "anti_patterns": [],
    "style_baseline": {"paragraph": "雨下了一夜。老式排气扇在头顶嗡嗡转，把福尔马林的气味搅成一团。"},
}


@pytest.fixture
def sample_state():
    return json.loads(json.dumps(STATE_TEMPLATE))


@pytest.fixture
def book_dir(tmp_path):
    """构造一个最小可用的书籍工作区。"""
    (tmp_path / "state").mkdir()
    state = json.loads(json.dumps(STATE_TEMPLATE))
    (tmp_path / "state" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (tmp_path / "outline").mkdir()
    (tmp_path / "outline" / "outline.md").write_text(
        "# 大纲\n\n## 第1章 福尔马林\n\n- 冲突：第一单生意上门\n- 五问：可见伤害=死者颈部勒痕；物理对抗=与劫尸者扭打；爽点=读忆锁定嫌疑人；结尾档位=炸；前300字=命案现场\n",
        encoding="utf-8",
    )
    (tmp_path / "chapters").mkdir()
    (tmp_path / "qa").mkdir()
    (tmp_path / "projections").mkdir()
    (tmp_path / ".gate").mkdir()
    return tmp_path


def uniform_text(chapter_len: int = 1200) -> str:
    """AI 味样本：句长均匀、无对话、大量模式命中。"""
    sentence = "他看着眼前的景象，不由得感到一阵莫名的寒意。"
    parts = []
    total = 0
    while total < chapter_len:
        parts.append(sentence)
        total += len(sentence)
    return "\n".join("".join(parts[i : i + 2]) for i in range(0, len(parts), 2))


def varied_text() -> str:
    """人类味样本：句长起伏大、有对话、段落长短交替、无 lint 命中。"""
    paragraphs = [
        "雨停了。陈默蹲在台阶上抽烟，烟灰落在皮鞋面，他没弹。",
        "「三号冷柜，下午到的。」老周把登记本推过来，纸页潮得发软，一角卷着黑。「家属没来。你自己看着办。」他说完就走了，走廊灯管嗡嗡响了两声，灭了。陈默站在原地听了会儿，才掏出钥匙往里去。",
        "冷柜的门很沉。",
        "拉开的一瞬间，那股味道涌出来。不是福尔马林。是烂在泥里的花，混着铁锈。他想起小时候在外婆家后院埋过的那只猫——土翻开的时候，也是这个味。十七年了，他居然还记得。有些东西埋得再深，翻出来还是那个味。",
        "「你终于来了。」",
        "陈默的手停在半空。冷柜里躺着的女人，嘴唇在动。他退后一步，撞上解剖台，托盘里的器械哗啦散了一地。他没有回头。他盯着那个女人的脸，看了足足十秒。",
        "她死了。脖子上一圈勒痕，紫黑色，勒进肉里。法医的报告就压在登记本下面，白纸黑字。可她刚才说话了。声音很轻，像从水底浮上来的气泡，破在他耳朵边上。",
        "「帮我找一个人。」她又说。",
        "这一次，陈默听清了。",
    ]
    return "\n".join(paragraphs)


def lint_bomb_text() -> str:
    """定向触发多条 lint 规则的样本。"""
    lines = [
        "他不由得感到一阵莫名的恐惧，下意识地后退了半步。",
        "这不是愤怒，而是深入骨髓的绝望。这不是逃避，而是本能的抵抗。这不是结束，而是全新的开始。",
        "她的眼底闪过一丝复杂的光芒，嘴角勾起一抹意味深长的笑容。",
        "这意味着，一切都变了。这背后的真相，由此可见一斑。",
        "综上所述，值得注意的是，他的眼神深邃而坚定。",
        "他缓缓地说道：「瞳孔微缩，说明你在说谎。」她淡淡道：「你很聪明。」",
        "他终于明白了，这一天，属于他的时代，才刚刚开始。",
    ]
    return "\n".join(lines)


def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path
