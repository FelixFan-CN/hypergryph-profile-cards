"""命令行入口。

    python -m hypergryph_profile_cards                 # 按配置生成所有卡片
    python -m hypergryph_profile_cards --init          # 生成一份最小可用配置
    python -m hypergryph_profile_cards --print-config  # 打印完整生效配置
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .config import MINIMAL_CONFIG, ConfigError, dump_effective, load_config
from .context import RunContext
from .orchestrator import STATUS_FAILED, STATUS_OK, STATUS_SKIPPED, exit_code, run, summarize_text

DEFAULT_CONFIG_NAME = "profile-cards.yaml"

_STATUS_LABEL = {
    STATUS_OK: "已生成",
    STATUS_SKIPPED: "跳过",
    STATUS_FAILED: "失败",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hypergryph-profile-cards",
        description="把《明日方舟》《终末地》的玩家数据渲染成个人主页名片",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", help="配置文件路径（默认自动查找 profile-cards.yaml 等）")
    parser.add_argument("--root", default=".", help="仓库根目录，默认当前目录")
    parser.add_argument("--assets-dir", default="assets", help="底图所在目录，默认 assets")
    parser.add_argument("--output-dir", help="产物输出目录，默认沿用配置里的 output")
    parser.add_argument("--only", default="", help="只处理指定的卡片 id，逗号分隔")
    parser.add_argument("--strict", action="store_true", help="任意一张卡失败就让进程返回非零")
    parser.add_argument("--init", action="store_true", help=f"生成一份 {DEFAULT_CONFIG_NAME}")
    parser.add_argument("--print-config", action="store_true", help="打印合并后的完整生效配置")
    return parser


def _handle_init(root: str) -> int:
    target = os.path.join(root, DEFAULT_CONFIG_NAME)
    if os.path.exists(target):
        print(f"{target} 已存在，未覆盖")
        return 1
    with open(target, "w", encoding="utf-8") as fp:
        fp.write(MINIMAL_CONFIG)
    print(f"已生成起步配置：{target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root)

    if args.init:
        return _handle_init(root)

    try:
        cards, _ = load_config(root, args.config)
    except ConfigError as error:
        print(f"配置有误：{error}", file=sys.stderr)
        return 2

    if args.print_config:
        print(dump_effective(cards), end="")
        return 0

    ctx = RunContext(
        root=root,
        assets_dir=args.assets_dir,
        output_dir=args.output_dir,
        only=tuple(x.strip() for x in args.only.split(",") if x.strip()),
        strict=args.strict,
    )

    results = run(cards, ctx)
    for result in results:
        label = _STATUS_LABEL.get(result.status, result.status)
        detail = result.path or result.error or ""
        print(f"[{result.title}] {label}{'：' + detail if detail else ''}")

    print()
    print(summarize_text(results))
    return exit_code(results, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
