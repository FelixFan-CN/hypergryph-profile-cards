"""配置的加载、校验、深合并与旧格式迁移。

生效优先级（后者覆盖前者）：
    内置预设 → 顶层 theme → 每张卡的 theme_overrides → 命令行参数

约定：
  - 字典递归深合并；列表整体替换；显式 null 表示「删除该键，恢复默认」
  - 字符串叶子支持 ${VAR} 与 ${VAR:-默认值} 插值
"""

from __future__ import annotations

import copy
import difflib
import os
import re
from typing import Any

import yaml

from .model import (
    BackgroundSpec,
    BlurOverlay,
    CardSpec,
    FadeOverlay,
    FontPair,
    StatSpec,
    TextSlot,
    Theme,
    parse_color,
)

PRESET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme", "presets")

CONFIG_FILENAMES = (
    "profile-cards.yaml",
    "profile-cards.yml",
    "profile-cards.json",
    "config.json",
)

# 旧版 config.json 的迁移模板：等价于重构前 render.py 里写死的两张卡
LEGACY_CARDS: dict[str, dict[str, Any]] = {
    "arknights": {
        "title": "明日方舟",
        "output": "assets/arknights-card.png",
        "uid_env": "ARKNIGHTS_UID",
        "nickname_empty": "博士",
        "stats": [
            {"field": "register_days", "label": "入职天数"},
            {"field": "operator_count", "label": "干员总数"},
            {"field": "six_star_count", "label": "六星干员"},
            {"field": "elite_two_count", "label": "精英二"},
            {"field": "skin_count", "label": "皮肤保有"},
        ],
    },
    "endfield": {
        "title": "明日方舟：终末地",
        "output": "assets/endfield-card.png",
        "uid_env": "ENDFIELD_UID",
        "nickname_empty": "管理员",
        "stats": [
            {"field": "play_days", "label": "苏醒天数"},
            {"field": "character_count", "label": "干员总数"},
            {"field": "weapon_count", "label": "武器总数"},
            {"field": "doc_count", "label": "档案总数"},
            {"field": "world_level", "label": "探索等级"},
        ],
    },
}

_ROOT_KEYS = {"version", "theme", "cards"}
_THEME_KEYS = {
    "preset",
    "canvas",
    "text_color",
    "shadow",
    "fonts",
    "background",
    "slots",
    "overlays",
}
_SLOT_KEYS = {
    "x",
    "y",
    "size",
    "bold",
    "alpha",
    "prefix",
    "empty",
    "anchor",
    "gap",
    "dy",
    "column_width",
}
_STAT_KEYS = {
    "field",
    "template",
    "label",
    "prefix",
    "suffix",
    "format",
    "thousands",
    "hide_if_empty",
}
_CARD_KEYS = {
    "id",
    "title",
    "enabled",
    "uid",
    "output",
    "stats",
    "theme_overrides",
    "options",
}

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ConfigError(RuntimeError):
    """配置有问题，附带可直接照着改的提示。"""


# ---------- 基础工具 ----------


def deep_merge(base: Any, override: Any) -> Any:
    """递归深合并：字典合并、列表替换、null 表示删除该键。"""
    if override is None:
        return None
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            if value is None:
                merged.pop(key, None)
                continue
            merged[key] = deep_merge(merged.get(key), value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def interpolate(value: Any, env: dict[str, str] | None = None) -> Any:
    """对字符串叶子做 ${VAR} / ${VAR:-默认} 插值；其它类型原样返回。"""
    env = os.environ if env is None else env
    if isinstance(value, dict):
        return {k: interpolate(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate(v, env) for v in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match) -> str:
        name, default = match.group(1), match.group(2)
        if name in env:
            return env[name]
        return default if default is not None else ""

    return _VAR_PATTERN.sub(replace, value)


def _hex_to_rgb(value: Any, path: str) -> tuple[int, int, int]:
    try:
        return parse_color(value, path)
    except ValueError as error:
        raise ConfigError(str(error)) from error


def _check_keys(data: dict, allowed: set[str], path: str) -> None:
    unknown = [k for k in data if k not in allowed]
    for key in unknown:
        guess = difflib.get_close_matches(key, sorted(allowed), n=1)
        hint = f"，你是不是想写 {guess[0]}？" if guess else f"，可用的键：{sorted(allowed)}"
        raise ConfigError(f"{path} 里出现未知键 {key!r}{hint}")


def _build(cls, data: dict, path: str):
    """把模型解析时的类型错误包装成可照着改的配置提示。"""
    try:
        return cls.from_dict(data)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        raise ConfigError(f"{path} 配置有误：{error}") from error


# ---------- 预设 ----------


def load_preset(name: str) -> dict:
    path = os.path.join(PRESET_DIR, f"{name}.yaml")
    if not os.path.exists(path):
        available = sorted(
            os.path.splitext(f)[0] for f in os.listdir(PRESET_DIR) if f.endswith(".yaml")
        )
        raise ConfigError(f"找不到主题预设 {name!r}，可用预设：{available}")
    with open(path, encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


# ---------- 旧格式迁移 ----------


def is_legacy(data: dict) -> bool:
    """旧版 config.json：顶层直接是游戏名，且没有 cards 键。"""
    return "cards" not in data and any(key in LEGACY_CARDS for key in data)


def migrate_legacy(data: dict) -> dict:
    """把旧版 config.json 在内存里迁移成新结构。"""
    cards = []
    for game_id, template in LEGACY_CARDS.items():
        section = data.get(game_id)
        if section is None:
            continue
        uid = section.get("uid") or ""
        cards.append(
            {
                "id": game_id,
                "title": template["title"],
                "enabled": bool(section.get("enabled", True)),
                # 保留旧版「环境变量优先」的行为
                "uid": f"${{{template['uid_env']}:-{uid}}}",
                "output": template["output"],
                "stats": copy.deepcopy(template["stats"]),
                "theme_overrides": {
                    "slots": {"name": {"empty": template["nickname_empty"]}}
                },
            }
        )
    return {"version": 1, "theme": "hoyocard", "cards": cards}


# ---------- 载入 ----------


def find_config(root: str, explicit: str | None = None) -> str:
    if explicit:
        path = explicit if os.path.isabs(explicit) else os.path.join(root, explicit)
        if not os.path.exists(path):
            raise ConfigError(f"指定的配置文件不存在：{path}")
        return path
    for name in CONFIG_FILENAMES:
        path = os.path.join(root, name)
        if os.path.exists(path):
            return path
    raise ConfigError(
        f"在 {root} 下找不到配置文件，请创建 {CONFIG_FILENAMES[0]}，"
        "或运行 --init 生成一份起步配置"
    )


def load_raw(root: str, explicit: str | None = None) -> dict:
    path = find_config(root, explicit)
    with open(path, encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} 的顶层必须是字典")
    if is_legacy(data):
        data = migrate_legacy(data)
    return interpolate(data)


# ---------- 构建 ----------


def build_theme(theme_section: Any, card_overrides: dict | None = None) -> Theme:
    if theme_section is None:
        theme_section = "hoyocard"
    if isinstance(theme_section, str):
        theme_section = {"preset": theme_section}
    if not isinstance(theme_section, dict):
        raise ConfigError("theme 需要是预设名（字符串）或一个字典")
    _check_keys(theme_section, _THEME_KEYS, "theme")

    preset_name = theme_section.get("preset", "hoyocard")
    merged = deep_merge(load_preset(preset_name), theme_section)
    merged.pop("preset", None)
    if card_overrides:
        merged = deep_merge(merged, card_overrides)

    canvas = merged.get("canvas") or {}
    shadow = merged.get("shadow") or {}
    offset = shadow.get("offset") or (2, 2)
    overlays = merged.get("overlays") or {}

    slots = {}
    for name, raw in (merged.get("slots") or {}).items():
        _check_keys(raw, _SLOT_KEYS, f"slots.{name}")
        slots[name] = _build(TextSlot, raw, f"slots.{name}")

    background_raw = dict(merged.get("background") or {})
    background_raw["fallback_gradient"] = dict(
        (merged.get("background") or {}).get("fallback_gradient") or {}
    ) or {"top": [30, 34, 40], "bottom": [12, 16, 22]}

    return Theme(
        width=int(canvas.get("width", 1200)),
        height=int(canvas.get("height", 400)),
        text_color=_hex_to_rgb(merged.get("text_color", "#FFFFFF"), "text_color"),
        shadow_enabled=bool(shadow.get("enabled", True)),
        shadow_alpha=int(shadow.get("alpha", 200)),
        shadow_offset=(int(offset[0]), int(offset[1])),
        fonts=tuple(
            _build(FontPair, f, f"fonts.candidates[{i}]")
            for i, f in enumerate((merged.get("fonts") or {}).get("candidates", ()))
        ),
        font_dir=(merged.get("fonts") or {}).get("dir"),
        background=_build(BackgroundSpec, background_raw, "background"),
        slots=slots,
        left_fade=_build(FadeOverlay, overlays.get("left_fade") or {}, "overlays.left_fade"),
        bottom_fade=_build(
            FadeOverlay, overlays.get("bottom_fade") or {}, "overlays.bottom_fade"
        ),
        blur=_build(BlurOverlay, overlays.get("blur") or {}, "overlays.blur"),
    )


def build_cards(data: dict) -> list[CardSpec]:
    _check_keys(data, _ROOT_KEYS, "配置根")
    raw_cards = data.get("cards")
    if not raw_cards:
        raise ConfigError("配置里没有任何卡片，请在 cards: 下至少写一张卡")

    cards = []
    seen = set()
    for index, raw in enumerate(raw_cards):
        path = f"cards[{index}]"
        _check_keys(raw, _CARD_KEYS, path)
        card_id = raw.get("id")
        if not card_id:
            raise ConfigError(f"{path} 缺少必填的 id")
        if card_id in seen:
            raise ConfigError(f"{path} 的 id {card_id!r} 与前面的卡片重复")
        seen.add(card_id)

        stats = []
        for stat_index, stat_raw in enumerate(raw.get("stats") or ()):
            _check_keys(stat_raw, _STAT_KEYS, f"{path}.stats[{stat_index}]")
            stats.append(_build(StatSpec, stat_raw, f"{path}.stats[{stat_index}]"))

        cards.append(
            CardSpec(
                id=str(card_id),
                title=str(raw.get("title") or card_id),
                output=str(raw.get("output") or f"assets/{card_id}-card.png"),
                theme=build_theme(data.get("theme"), raw.get("theme_overrides")),
                enabled=bool(raw.get("enabled", True)),
                uid=str(raw.get("uid") or ""),
                stats=tuple(stats),
                options=dict(raw.get("options") or {}),
            )
        )
    return cards


def load_config(root: str, explicit: str | None = None) -> tuple[list[CardSpec], dict]:
    """返回（卡片列表，原始合并后配置）。"""
    data = load_raw(root, explicit)
    return build_cards(data), data


def dump_effective(cards: list[CardSpec]) -> str:
    """把生效后的完整配置打印出来，供使用者复制回去改任意一处。

    输出刻意使用与输入完全一致的键名（theme_overrides），
    因此打印结果本身就是一份可直接使用的配置。
    """
    payload = {
        "version": 1,
        "cards": [
            {
                "id": card.id,
                "title": card.title,
                "enabled": card.enabled,
                "uid": card.uid,
                "output": card.output,
                "stats": [
                    {
                        "label": s.label,
                        **({"field": s.field} if s.field else {}),
                        **({"template": s.template} if s.template else {}),
                        "format": s.format,
                    }
                    for s in card.stats
                ],
                "theme_overrides": _theme_to_dict(card.theme),
            }
            for card in cards
        ],
    }
    header = (
        "# 这是合并了预设之后的完整生效配置，可直接整份覆盖你的配置文件。\n"
        "# 只想改某几项时，不必保留全文，按需删减即可。\n"
    )
    return header + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def _theme_to_dict(theme: Theme) -> dict:
    red, green, blue = theme.text_color
    return {
        "canvas": {"width": theme.width, "height": theme.height},
        "text_color": f"#{red:02X}{green:02X}{blue:02X}",
        "shadow": {
            "enabled": theme.shadow_enabled,
            "alpha": theme.shadow_alpha,
            "offset": list(theme.shadow_offset),
        },
        "fonts": {
            "candidates": [{"bold": f.bold, "regular": f.regular} for f in theme.fonts],
        },
        "background": {
            "anchor": theme.background.anchor,
            "paths": list(theme.background.paths),
            "fallback_gradient": {
                "top": list(theme.background.fallback_top),
                "bottom": list(theme.background.fallback_bottom),
            },
        },
        "slots": {
            name: {
                k: v
                for k, v in {
                    "x": slot.x,
                    "y": slot.y,
                    "size": slot.size,
                    "bold": slot.bold,
                    "alpha": slot.alpha,
                    "prefix": slot.prefix,
                    "empty": slot.empty,
                    "anchor": slot.anchor,
                    "gap": slot.gap,
                    "dy": slot.dy,
                    "column_width": slot.column_width,
                }.items()
                if v not in (None, "")
            }
            for name, slot in theme.slots.items()
        },
        "overlays": {
            "left_fade": {
                "enabled": theme.left_fade.enabled,
                "color": list(theme.left_fade.color),
                "stops": [list(s) for s in theme.left_fade.stops],
            },
            "bottom_fade": {
                "enabled": theme.bottom_fade.enabled,
                "color": list(theme.bottom_fade.color),
                "stops": [list(s) for s in theme.bottom_fade.stops],
            },
            "blur": {
                "enabled": theme.blur.enabled,
                "radius": theme.blur.radius,
                "region": list(theme.blur.region),
            },
        },
    }


MINIMAL_CONFIG = """\
# 最小可用配置。只改 uid 就能跑起来，其余全部走内置的 hoyocard 预设。
# 想看完整可配置项：python -m hypergryph_profile_cards --print-config

version: 1

cards:
  - id: arknights
    uid: "${ARKNIGHTS_UID:-}"
    stats:
      - { field: register_days,  label: 入职天数 }
      - { field: operator_count, label: 干员总数 }

  - id: endfield
    uid: "${ENDFIELD_UID:-}"
    stats:
      - { field: play_days,       label: 苏醒天数 }
      - { field: character_count, label: 干员总数 }
"""
