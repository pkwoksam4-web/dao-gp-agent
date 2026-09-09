from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from gp12_sina_share_amount_v1 import normalize_symbol


VERSION = '1.0'
FORMAL_START = '2020-06-01'
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


def _normalize_share_rows(symbol: str, rows: list[dict], formal_end: str) -> tuple[list[dict], int]:
    if not isinstance(rows, list):
        raise ValueError('share_rows must be a list')
    normalized: list[dict] = []
    seen: set[str] = set()
    post_formal_n = 0
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError('ShareAmount row must be an object')
        if normalize_symbol(raw.get('symbol')) != symbol:
            raise ValueError('ShareAmount symbol mismatch')
        change_date = _canonical_date(raw.get('record_date'), 'record_date')
        shares = _positive_shares(raw.get('outstanding_share_shares'))
        if change_date in seen:
            raise ValueError('duplicate Formal ShareAmount date')
        seen.add(change_date)
        if change_date > formal_end:
            post_formal_n += 1
            continue
        normalized.append({
            'symbol': symbol,
            'change_date': change_date,
            'outstanding_share_shares': shares,
        })
    normalized.sort(key=lambda item: item['change_date'])
    return normalized, post_formal_n


def _match_share_state(
    symbol: str,
    share: dict,
    structures: list[dict],
    share_sha: str,
    structure_sha: str,
) -> tuple[str, dict | None]:
    change_date = share['change_date']
    shares = share['outstanding_share_shares']
    same_date = [item for item in structures if item['change_date'] == change_date]
    if not same_date:
        return 'MISSING', None

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
        return 'AMOUNT_MISMATCH', None
    if len(matching) != 1:
        return 'AMBIGUOUS', None

    matched = matching[0]
    announcement_date = matched['announcement_date']
    known_at = max(change_date, announcement_date)
    return 'MATCH', {
        'symbol': symbol,
        'change_date': change_date,
        'announcement_date': announcement_date,
        'known_at': known_at,
        'outstanding_share_shares': shares,
        'share_amount_raw_sha256': share_sha,
        'stock_structure_raw_sha256': structure_sha,
    }


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
    shares, post_formal_share_row_n = _normalize_share_rows(
        normalized_symbol, share_rows, formal_boundary)

    states: list[dict] = []
    blockers: set[str] = set()
    for share in shares:
        status, state = _match_share_state(
            normalized_symbol, share, structures, share_sha, structure_sha)
        if status == 'MISSING':
            blockers.add('SINA_STOCK_STRUCTURE_MATCH_MISSING')
        elif status == 'AMOUNT_MISMATCH':
            blockers.add('SINA_STOCK_STRUCTURE_AMOUNT_MISMATCH')
        elif status == 'AMBIGUOUS':
            blockers.add('SINA_STOCK_STRUCTURE_MATCH_AMBIGUOUS')
        elif state is not None:
            states.append(state)

    states.sort(key=lambda item: (item['change_date'], item['announcement_date']))
    if not shares:
        blockers.add('SINA_SHARE_KNOWN_AT_UNVERIFIED')

    blocker_list = sorted(blockers)
    return {
        'artifact': 'SINA_SHARE_KNOWN_AT_V1',
        'version': VERSION,
        'symbol': normalized_symbol,
        'formal_end': formal_boundary,
        'formal_share_row_n': len(shares),
        'post_formal_share_row_n': post_formal_share_row_n,
        'matched_state_n': len(states),
        'states': states,
        'blockers': blocker_list,
        'pit_verified': bool(states) and not blocker_list,
        'formal_feature_ready': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def bind_formal_anchor_states(
    symbol: str,
    share_rows: list[dict],
    structure_rows: list[dict],
    share_raw_sha256: str,
    structure_raw_sha256: str,
    formal_start: str = FORMAL_START,
    formal_end: str = FORMAL_END,
) -> dict:
    normalized_symbol = normalize_symbol(symbol)
    share_sha = _sha256(share_raw_sha256, 'share_raw_sha256')
    structure_sha = _sha256(structure_raw_sha256, 'structure_raw_sha256')
    start = _canonical_date(formal_start, 'formal_start')
    end = _canonical_date(formal_end, 'formal_end')
    if start > end:
        raise ValueError('formal_start must not exceed formal_end')

    structures = _normalize_structure_rows(normalized_symbol, structure_rows)
    shares, post_formal_share_row_n = _normalize_share_rows(
        normalized_symbol, share_rows, end)

    match_results: list[dict] = []
    for share in shares:
        status, state = _match_share_state(
            normalized_symbol, share, structures, share_sha, structure_sha)
        match_results.append({
            'change_date': share['change_date'],
            'status': status,
            'state': state,
        })

    anchor_candidates = [
        item['state']
        for item in match_results
        if item['status'] == 'MATCH'
        and item['state'] is not None
        and item['state']['change_date'] <= start
        and item['state']['known_at'] <= start
    ]
    anchor = max(anchor_candidates, key=lambda item: item['change_date']) if anchor_candidates else None

    blockers: set[str] = set()
    if anchor is None:
        blockers.add('SINA_FORMAL_ANCHOR_MISSING')
        return {
            'artifact': 'SINA_SHARE_FORMAL_ANCHOR_V1',
            'version': VERSION,
            'symbol': normalized_symbol,
            'formal_start': start,
            'formal_end': end,
            'post_formal_share_row_n': post_formal_share_row_n,
            'formal_anchor_change_date': None,
            'formal_anchor_announcement_date': None,
            'formal_anchor_known_at': None,
            'formal_anchor_outstanding_share_shares': None,
            'pre_anchor_share_row_n': 0,
            'pre_anchor_matched_state_n': 0,
            'pre_anchor_mismatch_n': 0,
            'pre_anchor_mismatch_dates': [],
            'formal_required_share_row_n': 0,
            'formal_matched_state_n': 0,
            'formal_chain_mismatch_n': 0,
            'formal_chain_mismatch_dates': [],
            'states': [],
            'blockers': sorted(blockers),
            'pit_verified': False,
            'formal_feature_ready': False,
            'model_freeze_allowed': False,
            'oos_metrics_allowed': False,
        }

    anchor_date = anchor['change_date']
    pre_anchor = [item for item in match_results if item['change_date'] < anchor_date]
    required = [item for item in match_results if item['change_date'] >= anchor_date]

    formal_states: list[dict] = []
    formal_mismatch_dates: list[str] = []
    for item in required:
        status = item['status']
        if status == 'MATCH' and item['state'] is not None:
            formal_states.append(item['state'])
        else:
            formal_mismatch_dates.append(item['change_date'])
            if status == 'MISSING':
                blockers.add('SINA_FORMAL_CHAIN_MATCH_MISSING')
            elif status == 'AMOUNT_MISMATCH':
                blockers.add('SINA_FORMAL_CHAIN_AMOUNT_MISMATCH')
            elif status == 'AMBIGUOUS':
                blockers.add('SINA_FORMAL_CHAIN_MATCH_AMBIGUOUS')

    formal_states.sort(key=lambda item: (item['change_date'], item['announcement_date']))
    pre_anchor_mismatch_dates = sorted(
        item['change_date'] for item in pre_anchor if item['status'] != 'MATCH')
    pre_anchor_matched_state_n = sum(1 for item in pre_anchor if item['status'] == 'MATCH')

    blocker_list = sorted(blockers)
    return {
        'artifact': 'SINA_SHARE_FORMAL_ANCHOR_V1',
        'version': VERSION,
        'symbol': normalized_symbol,
        'formal_start': start,
        'formal_end': end,
        'post_formal_share_row_n': post_formal_share_row_n,
        'formal_anchor_change_date': anchor['change_date'],
        'formal_anchor_announcement_date': anchor['announcement_date'],
        'formal_anchor_known_at': anchor['known_at'],
        'formal_anchor_outstanding_share_shares': anchor['outstanding_share_shares'],
        'pre_anchor_share_row_n': len(pre_anchor),
        'pre_anchor_matched_state_n': pre_anchor_matched_state_n,
        'pre_anchor_mismatch_n': len(pre_anchor_mismatch_dates),
        'pre_anchor_mismatch_dates': pre_anchor_mismatch_dates,
        'formal_required_share_row_n': len(required),
        'formal_matched_state_n': len(formal_states),
        'formal_chain_mismatch_n': len(formal_mismatch_dates),
        'formal_chain_mismatch_dates': sorted(formal_mismatch_dates),
        'states': formal_states,
        'blockers': blocker_list,
        'pit_verified': bool(formal_states) and not blocker_list,
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


def dual_source_probe_gate(
    *,
    structural_blockers: list[str],
    binding_blockers: list[str],
    matched_state_n: int,
    pit_verified: bool,
) -> str:
    """Return the single-symbol probe gate without weakening PIT blockers."""
    if not isinstance(structural_blockers, list):
        raise ValueError('structural_blockers must be a list')
    if not isinstance(binding_blockers, list):
        raise ValueError('binding_blockers must be a list')
    if not isinstance(matched_state_n, int) or isinstance(matched_state_n, bool):
        raise ValueError('matched_state_n must be an integer')
    if not isinstance(pit_verified, bool):
        raise ValueError('pit_verified must be boolean')
    if (
        not structural_blockers
        and not binding_blockers
        and matched_state_n > 0
        and pit_verified
    ):
        return 'DUAL_SOURCE_STRUCTURAL_PASS'
    return 'BLOCKED'
