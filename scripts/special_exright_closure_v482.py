from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
from typing import Iterable

from sample50_validate import Action, event_ratio_v482

BASE_CHECKPOINT = {
    'PASS': 746,
    'EXACT_TERM_REVIEW': 98,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}
EXPECTED_OVERRIDE_N = 11
THRESHOLD_BP = 5.0


def _positive_float(value, label: str) -> float:
    out = float(value)
    if not math.isfinite(out) or out <= 0:
        raise ValueError(f'{label} must be positive finite')
    return out


def load_override_ledger(path: pathlib.Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('artifact') != 'SPECIAL_EXRIGHT_REFERENCE_V482' or obj.get('version') != 'V4.82':
        raise ValueError('unexpected V4.82 special-exright ledger identity')
    if obj.get('formal_promotion') is not False or obj.get('validated_global_provenance_emitted') is not False:
        raise ValueError('special-exright ledger must remain non-Formal')
    rows = obj.get('records')
    if not isinstance(rows, list) or len(rows) != EXPECTED_OVERRIDE_N or obj.get('record_n') != EXPECTED_OVERRIDE_N:
        raise ValueError(f'expected exact {EXPECTED_OVERRIDE_N}-record special-exright ledger')
    seen = set()
    out = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError('override row must be object')
        symbol = str(raw.get('symbol') or '').upper()
        ex_date = str(raw.get('ex_date') or '')[:10]
        if not symbol or len(ex_date) != 10:
            raise ValueError('override row missing symbol/ex_date')
        key = (symbol, ex_date)
        if key in seen:
            raise ValueError(f'duplicate override {symbol} {ex_date}')
        seen.add(key)
        row = dict(raw)
        row['symbol'] = symbol
        row['ex_date'] = ex_date
        row['adjusted_reference_price'] = _positive_float(raw.get('adjusted_reference_price'), 'adjusted_reference_price')
        row['expected_prev_close'] = _positive_float(raw.get('expected_prev_close'), 'expected_prev_close')
        if row.get('formal_promotion') is not False:
            raise ValueError(f'{symbol} {ex_date}: formal_promotion must remain false')
        if not str(row.get('evidence_kind') or '') or not str(row.get('evidence_url') or '').startswith('http'):
            raise ValueError(f'{symbol} {ex_date}: missing evidence provenance')
        out.append(row)
    return sorted(out, key=lambda r: (r['symbol'], r['ex_date']))


def _event_for_override(frozen: dict, override: dict) -> dict:
    symbol = str(frozen.get('symbol') or '').upper()
    if symbol != override['symbol']:
        raise ValueError(f'symbol mismatch frozen={symbol} override={override["symbol"]}')
    matches = [e for e in (frozen.get('events') or []) if str(e.get('ex_date') or '')[:10] == override['ex_date']]
    if len(matches) != 1:
        raise ValueError(f'{symbol}: expected one event for {override["ex_date"]}, found {len(matches)}')
    return matches[0]


def _observed_sina_factor(frozen: dict) -> float:
    fv = frozen.get('factor_validation') or {}
    rows = fv.get('worst_rows') or []
    if not rows:
        raise ValueError(f'{frozen.get("symbol")}: missing frozen Sina comparison rows')
    vals = [_positive_float(r.get('sina_factor'), 'sina_factor') for r in rows if r.get('sina_factor') is not None]
    if not vals:
        raise ValueError(f'{frozen.get("symbol")}: no observed Sina factor')
    # All 11 targeted records are single-event paths. The pre-event normalized factor
    # therefore has to be stable across the frozen worst rows; fail closed otherwise.
    lo, hi = min(vals), max(vals)
    if abs(hi / lo - 1.0) * 10000.0 > 0.01:
        raise ValueError(f'{frozen.get("symbol")}: non-constant observed factor in single-event closure')
    return vals[0]


def validate_one(frozen: dict, override: dict, threshold_bp: float = THRESHOLD_BP) -> dict:
    symbol = str(frozen.get('symbol') or '').upper()
    event = _event_for_override(frozen, override)
    prev_close = _positive_float(event.get('prev_actual_close'), 'prev_actual_close')
    expected_prev = _positive_float(override.get('expected_prev_close'), 'expected_prev_close')
    prev_close_diff_bp = abs(prev_close / expected_prev - 1.0) * 10000.0
    if prev_close_diff_bp > 0.01:
        raise ValueError(f'{symbol}: frozen previous close differs from validated evidence')

    action = Action(
        symbol=symbol,
        ex_date=override['ex_date'],
        cash_per_share=float(event.get('cash_per_share') or 0.0),
        stock_ratio=float(event.get('stock_ratio') or 0.0),
        cap_ratio=float(event.get('capitalization_ratio') or event.get('cap_ratio') or 0.0),
        rights_ratio=float(event.get('rights_ratio') or 0.0),
        rights_price=None if event.get('rights_price') in (None, '') else float(event.get('rights_price')),
        source=str(event.get('source') or 'FROZEN_V481_EVENT'),
    )
    old_ratio = _positive_float(event.get('event_ratio'), 'old_event_ratio') if event.get('event_ratio') is not None else None
    corrected = event_ratio_v482(action, prev_close, adjusted_reference_price=override['adjusted_reference_price'])
    observed = _observed_sina_factor(frozen)
    diff_bp = abs(observed / corrected - 1.0) * 10000.0
    old_diff_bp = None if old_ratio is None else abs(observed / old_ratio - 1.0) * 10000.0
    status = 'PASS_SPECIAL_EXRIGHT_V482' if diff_bp <= float(threshold_bp) else 'REVIEW_SPECIAL_EXRIGHT_V482'
    return {
        'symbol': symbol,
        'ex_date': override['ex_date'],
        'status': status,
        'threshold_bp': float(threshold_bp),
        'prev_actual_close': prev_close,
        'adjusted_reference_price': override['adjusted_reference_price'],
        'old_event_ratio': old_ratio,
        'corrected_event_ratio': corrected,
        'observed_sina_factor': observed,
        'old_diff_bp': old_diff_bp,
        'diff_bp': diff_bp,
        'evidence_kind': override['evidence_kind'],
        'evidence_url': override['evidence_url'],
        'formal_promotion': False,
    }


def _load_records(path: pathlib.Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding='utf-8'))
    rows = obj.get('records')
    if not isinstance(rows, list):
        raise ValueError(f'{path}: missing records[]')
    return rows


def close_special_exright(recalc53_path: pathlib.Path, recalc7_path: pathlib.Path, ledger_path: pathlib.Path) -> dict:
    frozen_rows = _load_records(recalc53_path) + _load_records(recalc7_path)
    by_symbol = {}
    for row in frozen_rows:
        symbol = str(row.get('symbol') or '').upper()
        if symbol in by_symbol:
            raise ValueError(f'duplicate frozen symbol {symbol}')
        by_symbol[symbol] = row

    overrides = load_override_ledger(ledger_path)
    results = []
    for override in overrides:
        frozen = by_symbol.get(override['symbol'])
        if frozen is None:
            raise ValueError(f'{override["symbol"]}: missing frozen V4.81 record')
        if frozen.get('status') != 'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT':
            raise ValueError(f'{override["symbol"]}: frozen record is not exact-term review')
        results.append(validate_one(frozen, override))

    pass_n = sum(r['status'] == 'PASS_SPECIAL_EXRIGHT_V482' for r in results)
    review_n = len(results) - pass_n
    checkpoint = dict(BASE_CHECKPOINT)
    checkpoint['PASS'] += pass_n
    checkpoint['EXACT_TERM_REVIEW'] -= pass_n
    if checkpoint['EXACT_TERM_REVIEW'] < 0:
        raise ValueError('invalid checkpoint after V4.82 closure')
    if sum(checkpoint.values()) != 847:
        raise ValueError('V4.82 checkpoint partition invariant failed')

    return {
        'artifact': 'SPECIAL_EXRIGHT_CLOSURE_V482',
        'version': 'V4.82',
        'target_n': len(results),
        'pass_n': pass_n,
        'review_n': review_n,
        'threshold_bp': THRESHOLD_BP,
        'base_checkpoint': BASE_CHECKPOINT,
        'checkpoint_after_special_exright': checkpoint,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'records': results,
    }


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}, found {len(hits)}')
    return hits[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--recalc53-dir', required=True)
    ap.add_argument('--recalc7-dir', required=True)
    ap.add_argument('--override-ledger', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()

    report = close_special_exright(
        _find_unique(pathlib.Path(args.recalc53_dir), 'MISSING_EVENT_FACTOR_RECALC_53_V481.json'),
        _find_unique(pathlib.Path(args.recalc7_dir), 'MISSING_EVENT_FACTOR_RECALC_V481.json'),
        pathlib.Path(args.override_ledger),
    )
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'SPECIAL_EXRIGHT_CLOSURE_V482.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'SPECIAL_EXRIGHT_CLOSURE_V482.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        fields = ['symbol', 'ex_date', 'status', 'old_diff_bp', 'diff_bp', 'prev_actual_close',
                  'adjusted_reference_price', 'old_event_ratio', 'corrected_event_ratio',
                  'observed_sina_factor', 'evidence_kind', 'evidence_url']
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in report['records']:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({
        'target_n': report['target_n'],
        'pass_n': report['pass_n'],
        'review_n': report['review_n'],
        'checkpoint_after_special_exright': report['checkpoint_after_special_exright'],
        'max_corrected_diff_bp': max(r['diff_bp'] for r in report['records']),
    }, ensure_ascii=False, indent=2))
    if report['review_n']:
        raise SystemExit(f'fail-closed: {report["review_n"]} special ex-right records remain review')


if __name__ == '__main__':
    main()
