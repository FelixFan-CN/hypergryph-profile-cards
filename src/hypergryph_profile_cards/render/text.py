"""字体加载与文字绘制。"""

from __future__ import annotations

import os

from PIL import ImageDraw, ImageFont

from ..model import Theme

FONT_DIR_ENV = "PROFILE_CARDS_FONT_DIR"

FONT_HINT = (
    "找不到可用的中文字体。请任选一种方式解决：\n"
    "  1) 下载思源黑体到 fonts/ 目录（与 workflow 一致）：\n"
    "     base=https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC\n"
    "     curl -fsSL -o fonts/NotoSansSC-Bold.otf    $base/NotoSansSC-Bold.otf\n"
    "     curl -fsSL -o fonts/NotoSansSC-Regular.otf $base/NotoSansSC-Regular.otf\n"
    "  2) 在本机安装思源黑体或微软雅黑；\n"
    "  3) 在配置的 theme.fonts.candidates 里写上你自己的字体路径。"
)


def _candidates(theme: Theme, bold: bool):
    """产出待探测的字体路径：先按配置原样，再尝试注入的字体目录。"""
    font_dir = theme.font_dir or os.environ.get(FONT_DIR_ENV)
    for pair in theme.fonts:
        path = pair.bold if bold else pair.regular
        yield path
        if font_dir and not os.path.isabs(path):
            yield os.path.join(font_dir, path)


def load_font(theme: Theme, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in _candidates(theme, bold):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    raise RuntimeError(FONT_HINT)


def put_text(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    x: float,
    y: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    alpha: int,
) -> None:
    """画一段文字，可选地先画一层黑色投影保证在亮底图上也清晰。"""
    if theme.shadow_enabled:
        offset_x, offset_y = theme.shadow_offset
        shadow = (0, 0, 0, int(alpha * theme.shadow_alpha / 255))
        draw.text((x + offset_x, y + offset_y), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=(*theme.text_color, alpha))
