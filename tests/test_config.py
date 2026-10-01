"""配置层：深合并语义、变量插值、旧格式迁移、错误提示。"""

from __future__ import annotations

import os

import pytest
import yaml

from hypergryph_profile_cards.config import (
    ConfigError,
    build_theme,
    deep_merge,
    dump_effective,
    interpolate,
    is_legacy,
    load_config,
    migrate_legacy,
)

LEGACY = {"arknights": {"enabled": True, "uid": "1000000001"}}


def test_deep_merge_recurses_dicts_and_replaces_lists():
    base = {"a": 1, "nested": {"x": 1, "y": 2}, "items": [1, 2, 3]}
    override = {"nested": {"y": 9}, "items": [7]}
    assert deep_merge(base, override) == {
        "a": 1,
        "nested": {"x": 1, "y": 9},
        "items": [7],
    }


def test_deep_merge_null_removes_key():
    base = {"keep": 1, "drop": 2, "nested": {"drop": 3}}
    assert deep_merge(base, {"drop": None, "nested": {"drop": None}}) == {
        "keep": 1,
        "nested": {},
    }


def test_interpolate_env_and_default():
    env = {"SET": "from-env"}
    assert interpolate("${SET}", env) == "from-env"
    assert interpolate("${MISSING:-fallback}", env) == "fallback"
    assert interpolate("${MISSING}", env) == ""
    assert interpolate("prefix-${SET}-suffix", env) == "prefix-from-env-suffix"


def test_interpolate_walks_containers():
    env = {"A": "1"}
    assert interpolate({"k": ["${A}", {"n": "${B:-2}"}]}, env) == {"k": ["1", {"n": "2"}]}


def test_legacy_detection_and_migration():
    assert is_legacy(LEGACY)
    assert not is_legacy({"cards": []})
    migrated = migrate_legacy(LEGACY)
    ids = [c["id"] for c in migrated["cards"]]
    assert ids == ["arknights"]  # 未出现的游戏不会被凭空加上
    card = migrated["cards"][0]
    assert card["uid"] == "${ARKNIGHTS_UID:-1000000001}"
    assert [s["label"] for s in card["stats"]] == [
        "入职天数",
        "干员总数",
        "六星干员",
        "精英二",
        "皮肤保有",
    ]


def test_legacy_env_var_wins(monkeypatch):
    monkeypatch.setenv("ARKNIGHTS_UID", "2000000002")
    data = interpolate(migrate_legacy(LEGACY))
    assert data["cards"][0]["uid"] == "2000000002"


def test_unknown_key_gives_suggestion():
    with pytest.raises(ConfigError) as error:
        build_theme({"canvas": {"width": 100}, "sadow": {}})
    assert "sadow" in str(error.value)


def test_bad_color_reports_path():
    with pytest.raises(ConfigError) as error:
        build_theme({"text_color": "white"})
    assert "text_color" in str(error.value)


def test_preset_missing_lists_available():
    with pytest.raises(ConfigError) as error:
        build_theme({"preset": "nope"})
    assert "hoyocard" in str(error.value)


def test_card_requires_id(tmp_path):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump({"cards": [{"uid": "1"}]}, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(ConfigError) as error:
        load_config(str(tmp_path))
    assert "id" in str(error.value)


def test_duplicate_id_rejected(tmp_path):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump({"cards": [{"id": "a"}, {"id": "a"}]}, allow_unicode=True),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as error:
        load_config(str(tmp_path))
    assert "重复" in str(error.value)


def test_stat_needs_field_or_template(tmp_path):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {"cards": [{"id": "a", "stats": [{"label": "空"}]}]}, allow_unicode=True
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(str(tmp_path))


def test_print_config_is_reloadable(tmp_path):
    (tmp_path / "config.json").write_text(
        '{"arknights": {"enabled": true, "uid": "1000000001"}}', encoding="utf-8"
    )
    cards, _ = load_config(str(tmp_path))
    dumped = dump_effective(cards)

    target = tmp_path / "roundtrip"
    target.mkdir()
    (target / "profile-cards.yaml").write_text(dumped, encoding="utf-8")
    reloaded, _ = load_config(str(target))

    assert [c.id for c in reloaded] == [c.id for c in cards]
    assert reloaded[0].theme.width == cards[0].theme.width
    assert reloaded[0].theme.slots["name"].size == cards[0].theme.slots["name"].size
    assert [s.label for s in reloaded[0].stats] == [s.label for s in cards[0].stats]


def test_config_search_order(tmp_path):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump({"cards": [{"id": "yaml"}]}, allow_unicode=True), encoding="utf-8"
    )
    (tmp_path / "config.json").write_text(
        '{"arknights": {"enabled": true, "uid": "1"}}', encoding="utf-8"
    )
    cards, _ = load_config(str(tmp_path))
    assert cards[0].id == "yaml"


def test_missing_config_mentions_init(tmp_path):
    with pytest.raises(ConfigError) as error:
        load_config(str(tmp_path))
    assert "--init" in str(error.value)


def test_env_scoped_to_cwd(tmp_path, monkeypatch):
    """旧版把 UID 放在环境变量里，迁移后仍应优先于配置。"""
    monkeypatch.setenv("ARKNIGHTS_UID", "3000000003")
    (tmp_path / "config.json").write_text(
        '{"arknights": {"enabled": true, "uid": "1000000001"}}', encoding="utf-8"
    )
    cards, _ = load_config(str(tmp_path))
    assert cards[0].uid == "3000000003"
    os.environ.pop("ARKNIGHTS_UID", None)
