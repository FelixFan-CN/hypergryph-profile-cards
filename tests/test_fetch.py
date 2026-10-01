"""数据整理层：用脱敏的手工 payload 锁定扁平字段名与边界行为。"""

from __future__ import annotations

from hypergryph_profile_cards.fetch import summarize_arknights, summarize_endfield


def _arknights_payload():
    return {
        "status": {
            "uid": "1000000001",
            "name": "测试博士",
            "level": 105,
            "registerTs": 1652353487,
            "mainStageProgress": "main_09-12",
            "ap": {"current": 8, "max": 207},
            "charCnt": 3,
            "skinCnt": 89,
            "furnitureCnt": 12,
        },
        "chars": [
            {"charId": "char_a", "evolvePhase": 2},
            {"charId": "char_b", "evolvePhase": 0},
            {"charId": "char_c", "evolvePhase": 2},
        ],
        "charInfoMap": {
            "char_a": {"name": "甲", "rarity": 5},
            "char_b": {"name": "乙", "rarity": 4},
            "char_c": {"name": "丙", "rarity": 5},
        },
        "routine": {
            "daily": {"current": 0, "total": 10},
            "weekly": {"current": 13, "total": 13},
        },
    }


def test_arknights_core_fields():
    flat = summarize_arknights(_arknights_payload())
    assert flat["nickname"] == "测试博士"
    assert flat["level"] == 105
    assert flat["uid"] == "1000000001"
    assert flat["operator_count"] == 3
    assert flat["skin_count"] == 89
    assert flat["furniture_count"] == 12
    assert flat["ap"] == "8 / 207"
    assert flat["ap_current"] == 8
    assert flat["main_stage"] == "main_09-12"


def test_arknights_rarity_comes_from_char_info_map():
    """chars 里每条都不带 rarity，星级必须从 charInfoMap 取。"""
    flat = summarize_arknights(_arknights_payload())
    assert flat["six_star_count"] == 2
    assert flat["elite_two_count"] == 2


def test_arknights_options_override_thresholds():
    flat = summarize_arknights(
        _arknights_payload(), {"six_star_rarity_index": 4, "elite_two_phase": 1}
    )
    assert flat["six_star_count"] == 3  # 阈值放宽到 rarity >= 4 后，三个都算
    assert flat["elite_two_count"] == 2


def test_arknights_routine_text():
    flat = summarize_arknights(_arknights_payload())
    assert flat["daily"] == "0 / 10"
    assert flat["weekly"] == "13 / 13"


def test_arknights_empty_payload_is_safe():
    flat = summarize_arknights({})
    assert flat["nickname"] == "博士"
    assert flat["operator_count"] is None
    assert flat["six_star_count"] is None
    assert flat["register_days"] is None
    assert flat["daily"] is None


def test_arknights_zero_counts_become_none():
    """计数为 0 时视为「没有数据」而隐藏，避免卡片上出现无意义的 0。"""
    payload = _arknights_payload()
    payload["chars"] = []
    payload["charInfoMap"] = {}
    flat = summarize_arknights(payload)
    assert flat["six_star_count"] is None
    assert flat["elite_two_count"] is None


def _endfield_payload():
    return {
        "playerInfo": {
            "businessCard": {
                "name": "测试管理员",
                "signature": "签名",
                "adventureLevel": 60,
                "worldLevel": 7,
                "shortId": "9853",
                "platformRoleId": "1000000002",
                "createTime": 1769051226,
                "mainMissionId": "e11m8",
                "statistic": {"charNum": 31, "weaponNum": 61, "docNum": 294},
                "achievement": {"display": [{"key": 1}] * 10, "infoList": []},
                "charList": [{"templateId": "a"}, {"templateId": "b"}],
            }
        },
        "uid": "1000000002",
    }


def test_endfield_core_fields():
    flat = summarize_endfield(_endfield_payload())
    assert flat["nickname"] == "测试管理员"
    assert flat["level"] == 60
    assert flat["world_level"] == 7
    assert flat["short_id"] == "9853"
    assert flat["uid"] == "1000000002"
    assert flat["character_count"] == 31
    assert flat["weapon_count"] == 61
    assert flat["doc_count"] == 294
    assert flat["achievement"] == 10
    assert flat["showcase_count"] == 2


def test_endfield_empty_payload_is_safe():
    flat = summarize_endfield({})
    assert flat["nickname"] == "管理员"
    assert flat["character_count"] is None
    assert flat["play_days"] is None
