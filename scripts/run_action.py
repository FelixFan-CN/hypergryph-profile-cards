"""Action 的渲染步骤：调用本包渲染名片，并把结果写回 workflow。

注意两个根必须严格区分：
  - 代码位置用 github.action_path（由 action.yml 通过脚本路径传入）
  - 底图 / 产物 / 配置用 inputs.root（默认 ${{ github.workspace }}）
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from hypergryph_profile_cards.config import ConfigError, load_config
from hypergryph_profile_cards.context import RunContext
from hypergryph_profile_cards.orchestrator import (
    STATUS_FAILED,
    STATUS_OK,
    STATUS_SKIPPED,
    exit_code,
    run,
    summarize_text,
)


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_output(name: str, value: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as fp:
        if "\n" in value:
            delimiter = f"EOF_{name}"
            fp.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
        else:
            fp.write(f"{name}={value}\n")


def _write_summary(rows: list[tuple[str, str, str]]) -> None:
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    lines = ["| 卡片 | 状态 | 说明 |", "| --- | --- | --- |"]
    for title, status, detail in rows:
        lines.append(f"| {title} | {status} | {detail} |")
    with open(target, "a", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")


def main() -> int:
    workspace = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()
    root = os.path.abspath(os.environ.get("PC_ROOT") or workspace)
    config = os.environ.get("PC_CONFIG") or None
    strict = _bool(os.environ.get("PC_STRICT", "false"))

    try:
        cards, _ = load_config(root, config)
    except ConfigError as error:
        print(f"配置有误：{error}", file=sys.stderr)
        return 2

    ctx = RunContext(
        root=root,
        assets_dir=os.environ.get("PC_ASSETS_DIR") or "assets",
        output_dir=os.environ.get("PC_OUTPUT_DIR") or None,
        only=tuple(x.strip() for x in (os.environ.get("PC_ONLY") or "").split(",") if x.strip()),
        strict=strict,
    )

    # 记录渲染前的产物哈希，用来判断 changed
    targets = {card.id: Path(ctx.resolve_output(card.output)) for card in cards}
    before = {card_id: _digest(path) for card_id, path in targets.items()}

    results = run(cards, ctx)

    after = {card_id: _digest(path) for card_id, path in targets.items()}
    changed = any(before.get(k) != after.get(k) for k in targets)

    produced = [r.path for r in results if r.status == STATUS_OK and r.path]
    failed = [r.id for r in results if r.status == STATUS_FAILED]
    skipped = [r.id for r in results if r.status == STATUS_SKIPPED]

    rows = []
    for result in results:
        detail = result.path or result.error or ""
        rows.append((result.title, result.status, detail))
        print(f"[{result.title}] {result.status}：{detail}")

    summary = summarize_text(results)
    print(summary)

    _write_output("produced", "\n".join(produced))
    _write_output("failed", "\n".join(failed))
    _write_output("skipped", "\n".join(skipped))
    _write_output("changed", "true" if changed else "false")
    _write_output("summary", summary)
    _write_summary(rows)

    return exit_code(results, strict=strict)


if __name__ == "__main__":
    sys.exit(main())
