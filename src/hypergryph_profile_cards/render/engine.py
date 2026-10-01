"""渲染引擎：把「卡片定义 + 数据」画成 PNG。

本模块不读配置文件、不联网、不依赖全局常量，所有外观都来自 CardSpec.theme。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

from ..model import CardSpec, CardValues, Theme
from .canvas import apply_blur, apply_fades, build_canvas, find_background
from .text import load_font, put_text


def _draw_header(
    draw: ImageDraw.ImageDraw, theme: Theme, spec: CardSpec, values: CardValues
) -> None:
    name_slot = theme.slot("name")
    name_text = values.nickname or name_slot.empty or "未知"
    font_name = load_font(theme, name_slot.size, name_slot.bold)
    put_text(draw, theme, name_slot.x, name_slot.y, name_text, font_name, name_slot.alpha)

    if values.level_text:
        level_slot = theme.slot("level")
        font_level = load_font(theme, level_slot.size, level_slot.bold)
        if level_slot.anchor == "name_right":
            name_width = draw.textlength(name_text, font=font_name)
            level_x = int(name_slot.x + name_width + level_slot.gap)
            level_y = name_slot.y + level_slot.dy
        else:
            level_x, level_y = level_slot.x, level_slot.y
        put_text(
            draw,
            theme,
            level_x,
            level_y,
            level_slot.prefix + values.level_text,
            font_level,
            level_slot.alpha,
        )

    if values.uid_text:
        uid_slot = theme.slot("uid")
        font_uid = load_font(theme, uid_slot.size, uid_slot.bold)
        put_text(
            draw,
            theme,
            uid_slot.x,
            uid_slot.y,
            uid_slot.prefix + values.uid_text,
            font_uid,
            uid_slot.alpha,
        )


def _draw_stats(
    draw: ImageDraw.ImageDraw, theme: Theme, values: CardValues
) -> None:
    if not values.stats:
        return
    value_slot = theme.slot("stat_value")
    label_slot = theme.slot("stat_label")
    font_value = load_font(theme, value_slot.size, value_slot.bold)
    font_label = load_font(theme, label_slot.size, label_slot.bold)
    column_width = value_slot.column_width or label_slot.column_width or 0

    for index, (label, value) in enumerate(values.stats):
        x = int(value_slot.x + index * column_width)
        put_text(draw, theme, x, value_slot.y, value, font_value, value_slot.alpha)
        put_text(draw, theme, x, label_slot.y, label, font_label, label_slot.alpha)


def render_card(
    spec: CardSpec,
    values: CardValues,
    assets_root: str,
    out_path: str,
) -> str:
    """渲染一张卡并返回输出路径。

    assets_root 是底图所在目录，theme.background.paths 中的模式相对它解析。
    """
    theme = spec.theme
    size = (theme.width, theme.height)

    patterns = tuple(p.replace("{id}", spec.id) for p in theme.background.paths)
    bg_path = find_background(patterns, assets_root)
    if not bg_path:
        print(
            f"[{spec.title}] 未找到底图（{assets_root} 下的 {', '.join(patterns)}），"
            "暂用深色渐变代替"
        )

    canvas = build_canvas(theme.background, size, bg_path)
    canvas = apply_blur(canvas, theme.blur)
    canvas = apply_fades(canvas, theme.left_fade, theme.bottom_fade)

    # 文字先画到独立图层再整体合成，这样半透明与投影才能正确混合
    text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    _draw_header(draw, theme, spec, values)
    _draw_stats(draw, theme, values)
    canvas.alpha_composite(text_layer)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path
