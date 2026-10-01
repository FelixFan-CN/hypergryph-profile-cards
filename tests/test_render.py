"""渲染层：像素基线、尺寸、遮罩开关、降级与容错。"""

from __future__ import annotations

import hashlib
import os

import pytest
import yaml
from conftest import BASELINE, BASELINE_FONT, load_values, values_for
from PIL import Image, ImageStat

from hypergryph_profile_cards.config import load_config
from hypergryph_profile_cards.render import render_card


def _render(workspace, card_id: str, out_name: str | None = None):
    cards, _ = load_config(str(workspace))
    card = next(c for c in cards if c.id == card_id)
    values = values_for(card, load_values()[card_id])
    out = workspace / (out_name or f"{card_id}.png")
    render_card(card, values, str(workspace / "assets"), str(out))
    return out


def _sha256(path) -> str:
    with open(path, "rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


@pytest.mark.skipif(
    not os.path.exists(BASELINE_FONT),
    reason="像素基线是在装有微软雅黑的机器上生成的，只在同机比对才有意义",
)
@pytest.mark.parametrize("card_id", ["arknights", "endfield"])
def test_matches_baseline(workspace, card_id):
    rendered = _render(workspace, card_id, f"{card_id}.png")
    assert _sha256(rendered) == _sha256(os.path.join(BASELINE, f"{card_id}.png"))


@pytest.mark.parametrize("card_id", ["arknights", "endfield"])
def test_output_size_and_format(workspace, card_id):
    rendered = _render(workspace, card_id)
    with Image.open(rendered) as image:
        assert image.size == (1200, 400)
        assert image.mode == "RGB"


def _mean_luma(image: Image.Image, box) -> float:
    return ImageStat.Stat(image.crop(box).convert("L")).mean[0]


def test_fades_darken_the_expected_regions(workspace):
    """关掉遮罩后，左侧与底部应该明显变亮——间接证明遮罩确实生效。"""
    on = _render(workspace, "arknights", "on.png")

    (workspace / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {
                "cards": [
                    {
                        "id": "arknights",
                        "uid": "1000000001",
                        "output": "assets/arknights-card.png",
                        "stats": [{"field": "register_days", "label": "入职天数"}],
                        "theme_overrides": {
                            "overlays": {
                                "left_fade": {"enabled": False},
                                "bottom_fade": {"enabled": False},
                            }
                        },
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    off = _render(workspace, "arknights", "off.png")

    with Image.open(on) as a, Image.open(off) as b:
        # 左上角：左侧渐隐覆盖区
        assert _mean_luma(a, (0, 0, 200, 120)) < _mean_luma(b, (0, 0, 200, 120))
        # 底部：底部渐隐覆盖区
        assert _mean_luma(a, (300, 330, 900, 400)) < _mean_luma(b, (300, 330, 900, 400))


def test_missing_background_falls_back(workspace, capsys):
    """底图缺失时仍要出图，并打印降级提示。"""
    os.remove(workspace / "assets" / "arknights-bg.png")
    rendered = _render(workspace, "arknights")
    assert rendered.exists()
    assert "未找到底图" in capsys.readouterr().out


def test_blur_overlay_can_be_enabled(workspace):
    (workspace / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {
                "cards": [
                    {
                        "id": "arknights",
                        "uid": "1000000001",
                        "output": "assets/arknights-card.png",
                        "stats": [{"field": "register_days", "label": "入职天数"}],
                        "theme_overrides": {
                            "overlays": {"blur": {"enabled": True, "region": [0, 0, 600, 400]}}
                        },
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    rendered = _render(workspace, "arknights")
    with Image.open(rendered) as image:
        assert image.size == (1200, 400)


@pytest.mark.parametrize("anchor", ["left", "center", "right"])
def test_background_anchor_variants(workspace, anchor, tmp_path):
    (workspace / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {
                "cards": [
                    {
                        "id": "arknights",
                        "uid": "1000000001",
                        "output": "assets/arknights-card.png",
                        "stats": [{"field": "register_days", "label": "入职天数"}],
                        "theme_overrides": {"background": {"anchor": anchor}},
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    rendered = _render(workspace, "arknights")
    assert rendered.exists()


def test_empty_stats_still_renders(workspace):
    (workspace / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {
                "cards": [
                    {
                        "id": "arknights",
                        "uid": "1000000001",
                        "output": "assets/arknights-card.png",
                        "stats": [],
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    rendered = _render(workspace, "arknights")
    with Image.open(rendered) as image:
        assert image.size == (1200, 400)


def test_many_stats_do_not_crash(workspace):
    stats = [{"field": "register_days", "label": f"项{i}"} for i in range(8)]
    (workspace / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {
                "cards": [
                    {
                        "id": "arknights",
                        "uid": "1000000001",
                        "output": "assets/arknights-card.png",
                        "stats": stats,
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    rendered = _render(workspace, "arknights")
    with Image.open(rendered) as image:
        assert image.size == (1200, 400)


def test_canvas_size_is_configurable(workspace):
    (workspace / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {
                "cards": [
                    {
                        "id": "arknights",
                        "uid": "1000000001",
                        "output": "assets/arknights-card.png",
                        "stats": [{"field": "register_days", "label": "入职天数"}],
                        "theme_overrides": {"canvas": {"width": 800, "height": 300}},
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    rendered = _render(workspace, "arknights")
    with Image.open(rendered) as image:
        assert image.size == (800, 300)
