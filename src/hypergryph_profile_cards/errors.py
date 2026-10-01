"""异常类型。"""

from __future__ import annotations


class ProfileCardsError(RuntimeError):
    """本项目的通用异常基类。"""


class SklandError(ProfileCardsError):
    """森空岛接口调用失败。"""


class EnkaError(ProfileCardsError):
    """Enka.Network 接口调用失败。"""
