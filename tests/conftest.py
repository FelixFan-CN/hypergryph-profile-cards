"""测试共用的 fixture。"""

from __future__ import annotations

import json
import os
import shutil

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
BASELINE = os.path.join(HERE, "baseline")

# 生成像素基线时使用的字体，只有在这台机器上存在时才做逐像素比对
BASELINE_FONT = r"C:\Windows\Fonts\msyhbd.ttc"

# 与像素基线等价的配置（stat 项与顺序必须一致）
CONFIG_YAML = """\
version: 1
cards:
  - id: arknights
    title: 明日方舟
    uid: "1000000001"
    output: assets/arknights-card.png
    stats:
      - { field: register_days,   label: 入职天数 }
      - { field: operator_count,  label: 干员总数 }
      - { field: six_star_count,  label: 六星干员 }
      - { field: elite_two_count, label: 精英二 }
      - { field: skin_count,      label: 皮肤保有 }
  - id: endfield
    title: 明日方舟：终末地
    uid: "1000000002"
    output: assets/endfield-card.png
    stats:
      - { field: play_days,       label: 苏醒天数 }
      - { field: character_count, label: 干员总数 }
      - { field: weapon_count,    label: 武器总数 }
      - { field: doc_count,       label: 档案总数 }
      - { field: world_level,     label: 探索等级 }
"""


def load_values() -> dict:
    with open(os.path.join(FIXTURES, "values.json"), encoding="utf-8") as fp:
        return json.load(fp)


def values_for(card, raw: dict):
    """按卡片配置把固定输入值组装成渲染层需要的 CardValues。"""
    from hypergryph_profile_cards.model import CardValues

    stats = []
    for spec in card.stats:
        value = raw.get(spec.field) if spec.field else None
        if value is None or value == "":
            continue
        stats.append((spec.label, str(value)))
    return CardValues(
        nickname=raw["nickname"],
        level_text=str(raw["level"]),
        uid_text=str(raw["uid"]),
        stats=tuple(stats),
    )


@pytest.fixture
def workspace(tmp_path):
    """一个带底图与配置的临时仓库。"""
    assets = tmp_path / "assets"
    assets.mkdir()
    for game in ("arknights", "endfield"):
        shutil.copy2(
            os.path.join(FIXTURES, f"{game}-bg.png"), assets / f"{game}-bg.png"
        )
    (tmp_path / "profile-cards.yaml").write_text(CONFIG_YAML, encoding="utf-8")
    return tmp_path
