from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

FROZEN_CONTROL_PATH = 'data/dao2/modules/A_JESSICA_KNOWN_ROW_CONTROL_SCOPE_V1.json'
LEDGER_PATH = 'data/GP12_CANDIDATE_MAIN_NET_FLOW_RESIDUAL_LEDGER_V1.json'

_REQUIRED_FIELDS = (
    'buy_lg_amount',
    'buy_elg_amount',
    'sell_lg_amount',
    'sell_elg_amount',
)


def load_frozen_controls(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding='utf-8'))
    controls = obj['controls']
    if obj.get('status') != 'FROZEN_PRE_VENDOR_RESIDUAL_VALUES':
        raise ValueError('control scope is not frozen')
    if len(controls) != 8:
        raise ValueError('frozen control count must equal 8')
    return controls


def load_residual_keys(path: Path) -> list[tuple[str, str]]:
    obj = json.loads(path.read_text(encoding='utf-8'))
    rows = obj['unresolved_keys']
    keys = [(r['ts_code'], r['trade_date']) for r in rows]
    if len(keys) != 16 or len(set(keys)) != 16:
        raise ValueError('authoritative residual ledger must contain 16 unique keys')
    return keys


def candidate_mappings() -> list[dict[str, Any]]:
    # Predefined only. Do not add result-driven field guesses.
    field_sets = [
        {
            'buy_lg_amount': 'activeBuyMainAmt',
            'buy_elg_amount': 'activeBuyLargeAmt',
            'sell_lg_amount': 'activeSellMainAmt',
            'sell_elg_amount': 'activeSellLargeAmt',
        },
        {
            'buy_lg_amount': 'active_buy_main_amt',
            'buy_elg_amount': 'active_buy_large_amt',
            'sell_lg_amount': 'active_sell_main_amt',
            'sell_elg_amount': 'active_sell_large_amt',
        },
    ]
    return [
        {'mapping': mapping, 'scale': scale}
        for mapping in field_sets
        for scale in (1, 0.0001, 10000)
    ]


def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


def score_candidate(
    controls: list[dict[str, Any]],
    rows: dict[tuple[str, str], dict[str, Any]],
    mapping: dict[str, str],
    scale: float,
) -> dict[str, Any]:
    exact = 0
    mismatches: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    dscale = _dec(scale)

    for control in controls:
        norm = control['normalized_row']
        key = (norm['ts_code'], norm['trade_date'])
        row = rows.get(key)
        if row is None:
            missing.append({'ts_code': key[0], 'trade_date': key[1]})
            continue
        for out_field in _REQUIRED_FIELDS:
            in_field = mapping[out_field]
            if in_field not in row or row[in_field] is None:
                mismatches.append({
                    'ts_code': key[0],
                    'trade_date': key[1],
                    'field': out_field,
                    'reason': 'missing_or_null',
                })
                continue
            observed = _dec(row[in_field]) * dscale
            expected = _dec(norm[out_field])
            if observed == expected:
                exact += 1
            else:
                mismatches.append({
                    'ts_code': key[0],
                    'trade_date': key[1],
                    'field': out_field,
                    'expected': str(expected),
                    'observed': str(observed),
                })

    mismatch_count = len(mismatches) + len(missing) * 4
    return {
        'exact_comparisons': exact,
        'mismatch_count': mismatch_count,
        'missing_controls': missing,
        'mismatches': mismatches,
        'pass': exact == 32 and mismatch_count == 0,
    }
