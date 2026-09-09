from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from gp12_sina_share_amount_v1 import normalize_symbol


VERSION = '1.0'
FORMAL_END = '2026-04-17'
SHA_RE = re.compile(r'^[0-9a-f]{64}$')


def _canonical_date(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f'{name} must be canonical ISO date')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{name} must be canonical ISO date') from exc
    if parsed.isoformat() != value:
        raise ValueError(f'{name} must be canonical ISO date')
    return value


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ValueError(f'{name} must be lowercase sha256')
    return value


def _positive_shares(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('outstanding_share_shares must be numeric') from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError('outstanding_share_shares must be finite and positive')
    return numeric


def _display_value(row: dict) -> tuple[str, int, Decimal]:
    display = row.get('circulating_a_10k_display')
    scale = row.get('circulating_a_display_scale')
    if not isinstance(display, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', display):
        raise ValueError('circulating A-share display invalid')
    if not isinstance(scale, int) or isinstance(scale, bool) or scale < 0:
        raise ValueError('circulating A-share display scale invalid')
    actual_scale = len(display.partition('.')[2]) if '.' in display else 0
    if actual_scale != scale:
        raise ValueError('circulating A-share display scale mismatch')
    try:
        value = Decimal(display)
    except InvalidOperation as exc:
        raise ValueError('circulating A-share display invalid') from exc
    if not value.is_finite() or value <= 0:
        raise ValueError('circulating A-share display must be positive')
    return display, scale, value


def _matches_display(api_amount_10k: Decimal, display_text: str, scale: int) -> bool:
    quantum = Decimal(1).scaleb(-scale)
    return (
        api_amount_10k.quantize(quantum, rounding=ROUND_HALF_UP)
        == Decimal(display_text)
    )


def _normalize_structure_rows(symbol: str, rows: list[dict]) -> list[dict]:
    if not isinstance(rows, list):
        raise ValueError('structure_rows must be a list')
    normalized: list[dict] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError('StockStructure row must be an object')
        if normalize_symbol(raw.get('symbol')) != symbol:
            raise ValueError('StockStructure symbol mismatch')
        change_date = _canonical_date(raw.get('change_date'), 'change_date')
        announcement_date = _canonical_date(
            raw.get('announcement_date'), 'announcement_date')
        display_text, scale, _ = _display_value(raw)
        normalized.append({
            'symbol': symbol,
            'change_date': change_date,
            'announcement_date': announcement_date,
            'change_reason': str(raw.get('change_reason') or '').strip(),
            'circulating_a_10k_display': display_text,
            'circulating_a_display_scale': scale,
        })
    normalized.sort(key=lambda item: (
        item['change_date'],
        item['announcement_date'],
        item['circulating_a_10k_display'],
    ))
    return normalized


def bind_known_at_states(
    symbol: str,
    share_rows: list[dict],
    structure_rows: list[dict],
    share_raw_sha256: str,
    structure_raw_sha256: str,
    formal_end: str = FORMAL_END,
) -> dict:
    normalized_symbol = normalize_symbol(symbol)
    share_sha = _sha256(share_raw_sha256, 'share_raw_sha256')
    structure_sha = _sha256(structure_raw_sha256, 'structure_raw_sha256')
    formal_boundary = _canonical_date(formal_end, 'formal_end')
    structures = _normalize_structure_rows(normalized_symbol, structure_rows)
    if not isinstance(share_rows, list):
        raise ValueError('share_rows must be a list')

    states: list[dict] = []
    blockers: set[str] = set()
    seen_share_dates: set[str] = set()
    formal_share_row_n = 0
    post_formal_share_row_n = 0

    for raw in share_rows:
        if not isinstance(raw, dict):
            raise ValueError('ShareAmount row must be an object')
        if normalize_symbol(raw.get('symbol')) != normalized_symbol:
            raise ValueError('ShareAmount symbol mismatch')
        change_date = _canonical_date(raw.get('record_date'), 'record_date')
        shares = _positive_shares(raw.get('outstanding_share_shares'))
        if change_date in seen_share_dates:
            raise ValueError('duplicate Formal ShareAmount date')
        seen_share_dates.add(change_date)

        if change_date > formal_boundary:
            post_formal_share_row_n += 1
            continue
        formal_share_row_n += 1

        same_date = [
            item for item in structures
            if item['change_date'] == change_date
        ]
        if not same_date:
            blockers.add('SINA_STOCK_STRUCTURE_MATCH_MISSING')
            continue

        api_amount_10k = Decimal(str(shares)) / Decimal('10000')
        matching = [
            item for item in same_date
            if _matches_display(
                api_amount_10k,
                item['circulating_a_10k_display'],
                item['circulating_a_display_scale'],
            )
        ]
        if not matching:
            blockers.add('SINA_STOCK_STRUCTURE_AMOUNT_MISMATCH')
            continue
        if len(matching) != 1:
            blockers.add('SINA_STOCK_STRUCTURE_MATCH_AMBIGUOUS')
            continue

        matched = matching[0]
        announcement_date = matched['announcement_date']
        known_at = max(change_date, announcement_date)
        states.append({
            'symbol': normalized_symbol,
            'change_date': change_date,
            'announcement_date': announcement_date,
            'known_at': known_at,
            'outstanding_share_shares': shares,
            'share_amount_raw_sha256': share_sha,
            'stock_structure_raw_sha256': structure_sha,
        })

    states.sort(key=lambda item: (item['change_date'], item['announcement_date']))
    if formal_share_row_n == 0:
        blockers.add('SINA_SHARE_KNOWN_AT_UNVERIFIED')

    blocker_list = sorted(blockers)
    return {
        'artifact': 'SINA_SHARE_KNOWN_AT_V1',
        'version': VERSION,
        'symbol': normalized_symbol,
        'formal_end': formal_boundary,
        'formal_share_row_n': formal_share_row_n,
        'post_formal_share_row_n': post_formal_share_row_n,
        'matched_state_n': len(states),
        'states': states,
        'blockers': blocker_list,
        'pit_verified': bool(states) and not blocker_list,
        'formal_feature_ready': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def resolve_known_at_state(states: list[dict], trade_date: str) -> dict | None:
    """Select the latest state whose effective and known-at dates are observable.

    This resolver is intentionally temporal-only. Numeric share validation and
    source-provenance validation belong to the consuming materializer so that
    those failures retain their exact production blocker/counter categories.
    """
    target = _canonical_date(trade_date, 'trade_date')
    if not isinstance(states, list):
        raise ValueError('states must be a list')
    eligible: list[dict] = []
    for raw in states:
        if not isinstance(raw, dict):
            raise ValueError('known-at state must be an object')
        change_date = _canonical_date(raw.get('change_date'), 'change_date')
        announcement_date = _canonical_date(
            raw.get('announcement_date'), 'announcement_date')
        known_at = _canonical_date(raw.get('known_at'), 'known_at')
        if known_at != max(change_date, announcement_date):
            raise ValueError('known_at invariant violation')
        if change_date <= target and known_at <= target:
            eligible.append(dict(raw))

    if not eligible:
        return None
    latest_change = max(item['change_date'] for item in eligible)
    latest = [item for item in eligible if item['change_date'] == latest_change]
    if len(latest) != 1:
        raise ValueError('ambiguous known-at state for trade date')
    return latest[0]
