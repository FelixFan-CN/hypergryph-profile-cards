"""编排：逐张卡独立地「拉数据 → 整理 → 渲染」。

单张卡失败不会影响其它卡；缺凭证/缺 UID 记为 skipped，网络或接口错误记为 failed。
"""

from __future__ import annotations

import re
import traceback
from dataclasses import dataclass

from .context import RunContext
from .errors import EnkaError, SklandError
from .fetch import fetch_endfield, summarize_arknights, summarize_endfield
from .model import CardSpec, CardValues, StatSpec
from .render import render_card
from .skland import fetch_arknights

SKLAND_TOKEN_ENV = "SKLAND_TOKEN"
FIELD_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"


@dataclass
class CardResult:
    id: str
    title: str
    status: str
    path: str | None = None
    error: str | None = None


def _as_text(value) -> str:
    return "" if value is None else str(value)


def format_stat(spec: StatSpec, flat: dict) -> str | None:
    """按配置把一个字段格式化成一格文字；返回 None 表示这一格不显示。"""
    if spec.template:
        text = FIELD_PATTERN.sub(lambda m: _as_text(flat.get(m.group(1))), spec.template)
        if not text.strip():
            return None if spec.hide_if_empty else ""
    else:
        raw = flat.get(spec.field)
        if raw in (None, ""):
            return None if spec.hide_if_empty else ""
        if spec.thousands and isinstance(raw, (int, float)):
            text = f"{raw:,}"
        else:
            text = str(raw)
    return f"{spec.prefix}{text}{spec.suffix}"


def build_values(card: CardSpec, flat: dict) -> CardValues:
    stats = []
    for spec in card.stats:
        text = format_stat(spec, flat)
        if text is None:
            continue
        stats.append((spec.label, text))
    return CardValues(
        nickname=_as_text(flat.get("nickname")),
        level_text=_as_text(flat.get("level")),
        uid_text=_as_text(flat.get("uid")),
        stats=tuple(stats),
    )


def _collect_arknights(card: CardSpec, ctx: RunContext) -> tuple[dict | None, str | None]:
    token = ctx.env_value(SKLAND_TOKEN_ENV)
    if not token:
        return None, f"未配置 {SKLAND_TOKEN_ENV}"
    payload = fetch_arknights(token, card.uid or None)
    return summarize_arknights(payload, card.options), None


def _collect_endfield(card: CardSpec, ctx: RunContext) -> tuple[dict | None, str | None]:
    if not card.uid:
        return None, "未配置 uid"
    payload = fetch_endfield(card.uid)
    return summarize_endfield(payload, card.options), None


COLLECTORS = {
    "arknights": _collect_arknights,
    "endfield": _collect_endfield,
}


def run(cards: list[CardSpec], ctx: RunContext) -> list[CardResult]:
    results: list[CardResult] = []

    for card in cards:
        if ctx.only and card.id not in ctx.only:
            continue
        if not card.enabled:
            results.append(CardResult(card.id, card.title, STATUS_SKIPPED, error="已在配置中禁用"))
            continue

        collector = COLLECTORS.get(card.id)
        if collector is None:
            results.append(
                CardResult(
                    card.id,
                    card.title,
                    STATUS_FAILED,
                    error=f"不支持的游戏 id，当前可用：{sorted(COLLECTORS)}",
                )
            )
            continue

        try:
            flat, skip_reason = collector(card, ctx)
            if flat is None:
                results.append(CardResult(card.id, card.title, STATUS_SKIPPED, error=skip_reason))
                continue

            values = build_values(card, flat)
            out_path = render_card(
                card, values, ctx.resolve_assets_root(), ctx.resolve_output(card.output)
            )
            results.append(
                CardResult(
                    card.id,
                    card.title,
                    STATUS_OK,
                    path=out_path,
                )
            )
        except (SklandError, EnkaError) as error:
            results.append(CardResult(card.id, card.title, STATUS_FAILED, error=str(error)))
        except Exception:  # noqa: BLE001 - 保证单卡失败不拖垮整体
            traceback.print_exc()
            results.append(CardResult(card.id, card.title, STATUS_FAILED, error="未知异常"))

    return results


def exit_code(results: list[CardResult], strict: bool = False) -> int:
    """有任意一张成功即返回 0；strict 模式下任意失败即返回 1。"""
    failed = [r for r in results if r.status == STATUS_FAILED]
    produced = [r for r in results if r.status == STATUS_OK]
    if strict and failed:
        return 1
    if failed and not produced:
        return 1
    return 0


def summarize_text(results: list[CardResult]) -> str:
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return (
        f"完成：生成 {counts['ok']} 张，"
        f"跳过 {counts['skipped']} 张，失败 {counts['failed']} 张"
    )
