"""画板构建：底图探测、缩放裁切、兜底渐变、渐隐遮罩、可选毛玻璃。

这里的每个算法都逐项对齐了重构前的实现，默认参数下产出逐像素一致。
"""

from __future__ import annotations

import os

from PIL import Image, ImageFilter

from ..model import BackgroundSpec, BlurOverlay, FadeOverlay


def lerp_stops(stops, ratio: float) -> float:
    """在 [(位置比例, 值)] 之间做线性插值。"""
    if not stops:
        return 0.0
    if ratio <= stops[0][0]:
        return stops[0][1]
    for (p0, v0), (p1, v1) in zip(stops, stops[1:], strict=False):
        if ratio <= p1:
            span = p1 - p0
            t = 0.0 if span == 0 else (ratio - p0) / span
            return v0 + (v1 - v0) * t
    return stops[-1][1]


def find_background(paths, root: str) -> str | None:
    """按候选顺序探测第一个存在的底图文件。"""
    for relative in paths:
        path = relative if os.path.isabs(relative) else os.path.join(root, relative)
        if os.path.exists(path):
            return path
    return None


def cover(image: Image.Image, size: tuple[int, int], anchor: str = "right") -> Image.Image:
    """等比缩放后裁切填满目标尺寸。

    anchor 决定横向从哪里裁：right 保住右侧主体（左侧会被渐隐压暗），
    center 居中，left 从左侧起裁。
    """
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    resized = image.resize((new_w, new_h), Image.LANCZOS)

    if anchor == "right":
        left = new_w - target_w
    elif anchor == "left":
        left = 0
    else:
        left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def horizontal_fade(width: int, height: int, overlay: FadeOverlay) -> Image.Image:
    """从左到右的渐隐遮罩。"""
    color = overlay.color
    row = Image.new("RGBA", (width, 1))
    pixels = row.load()
    for x in range(width):
        alpha = int(255 * lerp_stops(overlay.stops, x / max(1, width - 1)))
        pixels[x, 0] = (*color, max(0, min(255, alpha)))
    return row.resize((width, height))


def vertical_fade(width: int, height: int, overlay: FadeOverlay) -> Image.Image:
    """从下到上的渐隐遮罩（比例 0 在底部，1 在顶部）。"""
    color = overlay.color
    column = Image.new("RGBA", (1, height))
    pixels = column.load()
    for y in range(height):
        ratio = 1 - y / max(1, height - 1)
        alpha = int(255 * lerp_stops(overlay.stops, ratio))
        pixels[0, y] = (*color, max(0, min(255, alpha)))
    return column.resize((width, height))


def fallback_gradient(size: tuple[int, int], spec: BackgroundSpec) -> Image.Image:
    """底图缺失时的深色渐变兜底，保证渲染流程不中断。"""
    height = size[1]
    top, bottom = spec.fallback_top, spec.fallback_bottom
    delta = top[0] - bottom[0]
    column = Image.new("RGBA", (1, height))
    pixels = column.load()
    for y in range(height):
        shade = top[0] - int(delta * (y / max(1, height - 1)))
        pixels[0, y] = (
            shade,
            shade + (top[1] - top[0]),
            shade + (top[2] - top[0]),
            255,
        )
    return column.resize(size)


def build_canvas(spec: BackgroundSpec, size: tuple[int, int], bg_path: str | None) -> Image.Image:
    """底图铺底 → 毛玻璃（可选）→ 两组渐隐遮罩。"""
    if bg_path:
        with Image.open(bg_path) as source:
            canvas = cover(source.convert("RGB"), size, spec.anchor).convert("RGBA")
    else:
        canvas = fallback_gradient(size, spec)
    return canvas


def apply_blur(canvas: Image.Image, blur: BlurOverlay) -> Image.Image:
    """只对指定区域做高斯模糊，其余部分保持清晰。"""
    if not blur.enabled:
        return canvas
    region = blur.region
    box = (
        max(0, region[0]),
        max(0, region[1]),
        min(canvas.width, region[2] or canvas.width),
        min(canvas.height, region[3] or canvas.height),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return canvas
    patch = canvas.crop(box).filter(ImageFilter.GaussianBlur(blur.radius))
    canvas.paste(patch, box)
    return canvas


def apply_fades(canvas: Image.Image, left: FadeOverlay, bottom: FadeOverlay) -> Image.Image:
    width, height = canvas.size
    if left.enabled and left.stops:
        canvas.alpha_composite(horizontal_fade(width, height, left))
    if bottom.enabled and bottom.stops:
        canvas.alpha_composite(vertical_fade(width, height, bottom))
    return canvas
