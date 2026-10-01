"""命令行入口：--init / --print-config / 退出码 / 过滤。"""

from __future__ import annotations

import yaml

from hypergryph_profile_cards.cli import main


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exit_code:
        assert exit_code.code == 0
    assert "hypergryph-profile-cards" in capsys.readouterr().out


def test_init_creates_config(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "--init"]) == 0
    config = tmp_path / "profile-cards.yaml"
    assert config.exists()
    assert "cards:" in config.read_text(encoding="utf-8")
    assert "已生成起步配置" in capsys.readouterr().out


def test_init_does_not_overwrite(tmp_path, capsys):
    config = tmp_path / "profile-cards.yaml"
    config.write_text("keep me", encoding="utf-8")
    assert main(["--root", str(tmp_path), "--init"]) == 1
    assert config.read_text(encoding="utf-8") == "keep me"
    assert "已存在" in capsys.readouterr().out


def test_print_config_outputs_yaml(tmp_path, capsys):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {"cards": [{"id": "endfield", "uid": "1", "stats": [{"field": "play_days", "label": "苏醒天数"}]}]},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "--print-config"]) == 0
    out = capsys.readouterr().out
    assert "苏醒天数" in out
    assert "theme_overrides" in out


def test_missing_credentials_are_skipped(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SKLAND_TOKEN", raising=False)
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump({"cards": [{"id": "arknights", "uid": ""}]}, allow_unicode=True),
        encoding="utf-8",
    )
    # 底图缺失也应照常跳过，不触发网络
    assert main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "跳过" in out
    assert "SKLAND_TOKEN" in out


def test_disabled_card_is_reported(tmp_path, capsys):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {"cards": [{"id": "arknights", "uid": "", "enabled": False}]}, allow_unicode=True
        ),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path)]) == 0
    assert "已在配置中禁用" in capsys.readouterr().out


def test_only_filters_cards(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SKLAND_TOKEN", raising=False)
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump(
            {"cards": [{"id": "arknights", "uid": ""}, {"id": "endfield", "uid": ""}]},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "--only", "arknights"]) == 0
    out = capsys.readouterr().out
    assert "明日方舟" in out or "arknights" in out
    assert "终末地" not in out


def test_broken_config_returns_two(tmp_path, capsys):
    (tmp_path / "profile-cards.yaml").write_text("cards:\n  - uid: no-id\n", encoding="utf-8")
    assert main(["--root", str(tmp_path)]) == 2
    assert "配置有误" in capsys.readouterr().err


def test_unsupported_card_id_fails(tmp_path, capsys):
    (tmp_path / "profile-cards.yaml").write_text(
        yaml.safe_dump({"cards": [{"id": "genshin", "uid": "1"}]}, allow_unicode=True),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "不支持的游戏 id" in out
    assert "arknights" in out
