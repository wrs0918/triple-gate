"""新建书籍的初始状态模板。"""

from __future__ import annotations


def new_state(title: str, genre: str, platform: str) -> dict:
    """构造一个合法的 planning 阶段空状态。"""
    return {
        "schema_version": 1,
        "book": {
            "title": title,
            "genre": genre,
            "platform": platform,
            "north_star": {
                "positioning": "",
                "core_conflict": "",
                "power_cost": "",
                "differentiation": "",
                "city_industry": "",
            },
        },
        "progress": {"phase": "planning", "current_chapter": 1, "state_revision": 0},
        "chapters": {},
        "timeline": [],
        "foreshadowing": [],
        "hooks": [],
        "tropes": [],
        "characters": [],
        "anti_patterns": [],
        "style_baseline": {"paragraph": ""},
    }
