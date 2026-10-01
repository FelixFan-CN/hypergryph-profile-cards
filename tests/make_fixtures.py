"""生成测试用的合成底图。

上游仓库不包含任何官方素材，测试底图由本脚本确定性生成（固定随机种子），
因此任何人 clone 后都能复现同一张图，像素基线才有意义。

用法：
    python tests/make_fixtures.py
"""

import os
import random

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")

# 刻意做成 3:2 而非 3:1，这样 _cover 的缩放与裁切逻辑会真正被覆盖到
SRC_W, SRC_H = 1500, 1000


def _render(path, seed, base_color):
    """画一张高对比、含高频细节的图，用于检验缩放、裁切与渐隐遮罩。"""
    random.seed(seed)
    image = Image.new("RGB", (SRC_W, SRC_H), base_color)
    draw = ImageDraw.Draw(image)

    # 纵向渐变
    for y in range(SRC_H):
        t = y / SRC_H
        draw.line(
            [(0, y), (SRC_W, y)],
            fill=(
                int(base_color[0] + 90 * t),
                int(base_color[1] + 70 * t),
                int(base_color[2] + 50 * t),
            ),
        )

    # 高频线条，用来观察模糊与缩放是否生效
    for _ in range(320):
        x0, y0 = random.randint(0, SRC_W), random.randint(0, SRC_H)
        draw.line(
            [(x0, y0), (x0 + random.randint(-90, 90), y0 + random.randint(-50, 50))],
            fill=(random.randint(200, 255), random.randint(200, 255), random.randint(210, 255)),
            width=3,
        )

    # 亮斑，模拟立绘高光，用来压力测试白字可读性
    for _ in range(120):
        x0, y0 = random.randint(0, SRC_W), random.randint(0, SRC_H)
        r = random.randint(20, 90)
        draw.ellipse([x0, y0, x0 + r, y0 + r], fill=(250, 250, 250))

    image.save(path, "PNG")


def main():
    os.makedirs(FIXTURES, exist_ok=True)
    _render(os.path.join(FIXTURES, "arknights-bg.png"), seed=20260501, base_color=(120, 170, 220))
    _render(os.path.join(FIXTURES, "endfield-bg.png"), seed=20260502, base_color=(200, 180, 150))
    print(f"已生成测试底图：{FIXTURES}")


if __name__ == "__main__":
    main()
