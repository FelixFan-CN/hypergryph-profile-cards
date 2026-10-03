"""明日方舟：把森空岛返回的原始响应整理成扁平的字段字典。

扁平字典里的键就是配置中 stats[].field 可以引用的名字。
"""

from __future__ import annotations

import time

# 默认判定阈值，可用配置里的 card.options 覆盖
DEFAULT_SIX_STAR_RARITY_INDEX = 5  # charInfoMap 的 rarity 为 0 起始索引
DEFAULT_ELITE_TWO_PHASE = 2

# 理智自然回复节奏：每 6 分钟 +1
AP_RECOVER_SECONDS = 360


def _pick(mapping, *keys, default=None):
    for key in keys:
        value = mapping.get(key) if isinstance(mapping, dict) else None
        if value not in (None, "", [], {}):
            return value
    return default


def _days_since(timestamp):
    if not timestamp:
        return None
    return max(0, int((time.time() - int(timestamp)) // 86400))


def _ratio_text(source):
    """把 {current, total} 组装成 "已完成 / 总数"。"""
    if not isinstance(source, dict):
        return None
    current, total = source.get("current"), source.get("total")
    if current is None or not total:
        return None
    return f"{current} / {total}"


def _current_ap(ap) -> tuple[int | None, int | None]:
    """算出此刻的真实理智。

    接口返回的 current 是 lastApAddTime 那一刻的值，不含之后自然回复的部分，
    所以要按「每 6 分钟 +1」往后推。三种情形：
      - current 已达到或超过上限：理智恢复药、源石会把理智顶到上限之上，
        此时自然回复不生效，原样返回，绝不能压回上限，否则溢出的部分会算丢；
      - current 低于上限：往后推算，回满即封顶不再增长；
      - 拿不到 lastApAddTime：退化为直接用 current。
    """
    if not isinstance(ap, dict):
        return None, None
    current, maximum = ap.get("current"), ap.get("max")
    if current is None or maximum is None:
        return None, None

    current, maximum = int(current), int(maximum)
    if current >= maximum:
        return current, maximum

    last_add = ap.get("lastApAddTime")
    if last_add:
        elapsed = max(0, int(time.time()) - int(last_add))
        current = min(maximum, current + elapsed // AP_RECOVER_SECONDS)
    return current, maximum


def summarize(payload: dict, options: dict | None = None) -> dict:
    """整理成扁平字段。

    options 可覆盖：
      six_star_rarity_index  星级不低于该索引即计入（默认 5，即 rarity 5 = 六星）
      elite_two_phase        精英二所需的 evolvePhase（默认 2）
    """
    options = options or {}
    six_star_index = int(options.get("six_star_rarity_index", DEFAULT_SIX_STAR_RARITY_INDEX))
    elite_two_phase = int(options.get("elite_two_phase", DEFAULT_ELITE_TWO_PHASE))

    status = payload.get("status") or {}
    chars = payload.get("chars") or []
    # chars 里每条只带养成立项，星级等静态信息在 charInfoMap 中
    char_info = payload.get("charInfoMap") or {}
    routine = payload.get("routine") or {}

    six_star = 0
    elite_two = 0
    for char in chars:
        if not isinstance(char, dict):
            continue
        info = char_info.get(char.get("charId")) or {}
        rarity = info.get("rarity")
        if isinstance(rarity, int) and rarity >= six_star_index:
            six_star += 1
        if (char.get("evolvePhase") or 0) >= elite_two_phase:
            elite_two += 1

    ap = status.get("ap") or {}
    ap_current, ap_max = _current_ap(ap)

    return {
        "nickname": _pick(status, "name", default="博士"),
        "level": _pick(status, "level", default=""),
        "uid": _pick(status, "uid", default=""),
        "register_days": _days_since(status.get("registerTs")),
        "main_stage": _pick(status, "mainStageProgress", default=""),
        "ap_current": ap_current,
        "ap_max": ap_max,
        "ap": f"{ap_current} / {ap_max}" if ap_current is not None and ap_max else None,
        "operator_count": len(chars) or status.get("charCnt"),
        "six_star_count": six_star or None,
        "elite_two_count": elite_two or None,
        "skin_count": _pick(status, "skinCnt", default=None),
        "daily": _ratio_text(routine.get("daily")),
        "weekly": _ratio_text(routine.get("weekly")),
        "furniture_count": status.get("furnitureCnt"),
    }
