"""面向用户的可读错误。"""

from __future__ import annotations


class GateError(Exception):
    """门禁工具错误：消息直接面向用户，应原样呈现。"""
