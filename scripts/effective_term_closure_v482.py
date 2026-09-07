from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import pathlib
from typing import Iterable

from collect_cninfo_exact_term_indices_v481 import EXACT_STATUSES, SPECIAL_RESTRUCTURING_11
from materialize_standard_exact_pdfs_v481 import _parse_sina_js

FORMAL_BEG = '2020-06-01'
FORMAL_END = '2026-04-17'
THRESHOLD_BP = 5.0
EXPECTED_STANDARD_SCOPE_N = 87
EXPECTED_EFFECTIVE_EVENT_N = 26
EXPECTED_CLOSED_SYMBOL_N = 9
BASE_AFTER_SPECIAL = {
    'PASS': 757,
    'EXACT_TERM_REVIEW': 87,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}


def _positive(value, label: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f'{label} must be positive finite')
    return x


def corrected_event_ratio(event: dict, terms: dict) -> float:
    prev = _positive(event.get('prev_actual_close'), 'prev_actual_close')
    cash = terms.get('cash_per_share')
    if cash is None:
        cash = float(event.get('cash_per_share_nominal') or 0.0)
    cash = float(cash)
    cap = terms.get('cap_ratio')
    if cap is None:
        cap = float(event.get('capitalization_ratio') or 0.0)
    cap = float(cap)
    stock = float(event.get('stock_ratio') or 0.0)
    rights = float(event.get('rights_ratio') or 0.0)
    rights_price = event.get('rights_price')
    if min(cash, cap, stock, rights) < 0:
        raise ValueError('negative distribution term')
    if rights > 0 and rights_price in (None, ''):
        raise ValueError('rights issue missing price')
    rights_term = 0.0 if rights == 0 else rights * _positive(rights_price, 'rights_price')
    shares = 1.0 + stock + cap + rights
    ex_ref = (prev - cash + rights_term) / shares
    if ex_ref <= 0:
        raise ValueError('invalid corrected ex-right reference price')
    return ex_ref / prev


def factor_for_date(factors: list[dict], date_str: str) -> float:
    out = None
    for row in sorted(factors, key=lambda r: str(r.get('d') or '')):
        d = str(row.get('d') or '')[:10]
        if not d:
            continue
        if d <= date_str:
            out = _positive(row.get('f'), 'Sina factor')
        else:
            break
    if out is None:
        raise ValueError(f'no Sina factor covering {date_str}')
    return out


def recompute_symbol_max_diff_bp(
    record: dict,
    factors: list[dict],
    overrides: dict[tuple[str, str], float],
    formal_beg: str = FORMAL_BEG,
    formal_end: str = FORMAL_END,
) -> dict:
    symbol = str(record.get('symbol') or '').upper()
    events = sorted(record.get('events') or [], key=lambda e: str(e.get('ex_date') or ''))
    if not symbol or not events:
        raise ValueError('exact-term record missing symbol/events')
    ratios = {}
    for event in events:
        ex_date = str(event.get('ex_date') or '')[:10]
        nominal = _positive(event.get('event_ratio'), 'event_ratio')
        ratios[ex_date] = _positive(overrides.get((symbol, ex_date), nominal), 'effective event ratio')

    anchor_factor = factor_for_date(factors, formal_end)
    start = dt.date.fromisoformat(formal_beg)
    end = dt.date.fromisoformat(formal_end)
    if start > end:
        raise ValueError('invalid formal window')
    max_bp = -1.0
    worst_date = None
    checked_days = 0
    cur = start
    while cur <= end:
        d = cur.isoformat()
        expected = 1.0
        for event in events:
            ex_date = str(event.get('ex_date') or '')[:10]
            if d < ex_date <= formal_end:
                expected *= ratios[ex_date]
        actual = anchor_factor / factor_for_date(factors, d)
        bp = abs(actual / expected - 1.0) * 10000.0
        checked_days += 1
        if bp > max_bp:
            max_bp = bp
            worst_date = d
        cur += dt.timedelta(days=1)
    return {
        'symbol': symbol,
        'max_diff_bp': max_bp,
        'worst_date': worst_date,
        'checked_calendar_days': checked_days,
        'status': 'PASS_EFFECTIVE_TERMS_V482' if max_bp <= THRESHOLD_BP else 'REVIEW_EXACT_TERMS_V482',
    }


def updated_checkpoint(pass_n: int, base: dict | None = None) -> dict:
    base = dict(BASE_AFTER_SPECIAL if base is None else base)
    n = int(pass_n)
    if n < 0 or n > int(base.get('EXACT_TERM_REVIEW', -1)):
        raise ValueError('invalid effective-term pass count')
    out = dict(base)
    out['PASS'] = int(out['PASS']) + n
    out['EXACT_TERM_REVIEW'] = int(out['EXACT_TERM_REVIEW']) - n
    if sum(out.values()) != 847:
        raise ValueError('847 partition invariant failed')
    return out


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _standard_records(closure: dict) -> dict[str, dict]:
    out = {}
    for row in closure.get('records') or []:
        symbol = str(row.get('symbol') or '').upper()
        if row.get('status') not in EXACT_STATUSES or symbol in SPECIAL_RESTRUCTURING_11:
            continue
        out[symbol] = row
    if len(out) != EXPECTED_STANDARD_SCOPE_N:
        raise ValueError(f'expected {EXPECTED_STANDARD_SCOPE_N} standard exact-review symbols; got {len(out)}')
    return dict(sorted(out.items()))


def _event_by_date(record: dict, ex_date: str) -> dict:
    hits = [e for e in (record.get('events') or []) if str(e.get('ex_date') or '')[:10] == ex_date]
    if len(hits) != 1:
        raise ValueError(f'{record.get("symbol")} {ex_date}: expected one frozen event; found={len(hits)}')
    return hits[0]


def build_effective_overrides(evidence: dict, standard: dict[str, dict]) -> tuple[dict[tuple[str, str], float], list[dict]]:
    overrides = {}
    rows = []
    for item in evidence.get('records') or []:
        pdf = item.get('pdf_evidence') or {}
        terms = pdf.get('effective_terms') or {}
        if not any(terms.get(k) is not None for k in ('cash_per_share', 'cap_ratio')):
            continue
        symbol = str(item.get('symbol') or '').upper()
        ex_date = str(item.get('ex_date') or '')[:10]
        if symbol not in standard:
            raise ValueError(f'effective-term evidence outside standard scope: {symbol}')
        if pdf.get('text_extract_ok') is not True or not (item.get('announcement') or {}):
            raise ValueError(f'{symbol} {ex_date}: effective term lacks materialized official PDF')
        event = _event_by_date(standard[symbol], ex_date)
        ratio = corrected_event_ratio(event, terms)
        actual_jump = _positive(item.get('actual_factor_jump'), 'actual_factor_jump')
        event_diff_bp = abs(actual_jump / ratio - 1.0) * 10000.0
        if event_diff_bp > THRESHOLD_BP:
            raise ValueError(f'{symbol} {ex_date}: extracted effective term still exceeds threshold ({event_diff_bp:.6f}bp)')
        key = (symbol, ex_date)
        if key in overrides:
            raise ValueError(f'duplicate effective-term override {symbol} {ex_date}')
        overrides[key] = ratio
        rows.append({
            'symbol': symbol,
            'ex_date': ex_date,
            'nominal_event_ratio': float(item.get('nominal_event_ratio')),
            'corrected_event_ratio': ratio,
            'actual_factor_jump': actual_jump,
            'nominal_event_diff_bp': float(item.get('event_diff_bp')),
            'corrected_event_diff_bp': event_diff_bp,
            'cash_per_share_effective': terms.get('cash_per_share'),
            'cap_ratio_effective': terms.get('cap_ratio'),
            'cash_evidence_kind': terms.get('cash_evidence_kind'),
            'cap_evidence_kind': terms.get('cap_evidence_kind'),
            'announcement_id': (item.get('announcement') or {}).get('announcementId'),
            'pdf_sha256': pdf.get('sha256'),
        })
    if len(overrides) != EXPECTED_EFFECTIVE_EVENT_N:
        raise ValueError(f'expected {EXPECTED_EFFECTIVE_EVENT_N} effective-term overrides; got {len(overrides)}')
    return overrides, sorted(rows, key=lambda r: (r['symbol'], r['ex_date']))


def close_effective_terms(
    frozen_closure_dir: pathlib.Path,
    evidence_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
    special_closure_dir: pathlib.Path,
) -> dict:
    frozen = _load_json(_find_unique(frozen_closure_dir, 'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json'))
    evidence = _load_json(_find_unique(evidence_dir, 'CNINFO_STANDARD_EXACT_PDF_EVIDENCE_V481.json'))
    special = _load_json(_find_unique(special_closure_dir, 'SPECIAL_EXRIGHT_CLOSURE_V482.json'))
    if special.get('checkpoint_after_special_exright') != BASE_AFTER_SPECIAL:
        raise ValueError('special-exright base checkpoint mismatch')
    if special.get('formal_promotion') is not False or special.get('validated_global_provenance_emitted') is not False:
        raise ValueError('special-exright artifact violated non-Formal guard')
    if evidence.get('candidate_event_n') != 89 or evidence.get('candidate_symbol_n') != 56:
        raise ValueError('unexpected exact-term candidate partition')
    if evidence.get('announcement_matched_event_n') != 67 or evidence.get('pdf_text_ok_event_n') != 67:
        raise ValueError('official PDF materialization partition changed')

    standard = _standard_records(frozen)
    overrides, event_rows = build_effective_overrides(evidence, standard)
    source_root = source_census_dir
    symbol_rows = []
    for symbol, record in standard.items():
        code, exchange = symbol.split('.')
        raw = _find_unique(source_root, f'{code}_{exchange}_sina_qfq.js').read_bytes()
        factors = _parse_sina_js(raw)
        result = recompute_symbol_max_diff_bp(record, factors, overrides)
        result['frozen_max_diff_bp'] = float((record.get('factor_validation') or {}).get('max_diff_bp'))
        result['effective_override_event_n'] = sum(1 for s, _ in overrides if s == symbol)
        symbol_rows.append(result)

    closed = sorted(r['symbol'] for r in symbol_rows if r['status'] == 'PASS_EFFECTIVE_TERMS_V482')
    remaining = sorted(r['symbol'] for r in symbol_rows if r['status'] != 'PASS_EFFECTIVE_TERMS_V482')
    if len(closed) != EXPECTED_CLOSED_SYMBOL_N:
        raise ValueError(f'expected exactly {EXPECTED_CLOSED_SYMBOL_N} fully closed symbols; got {len(closed)}')
    checkpoint = updated_checkpoint(len(closed), special['checkpoint_after_special_exright'])
    return {
        'artifact': 'EFFECTIVE_TERM_CLOSURE_V482',
        'version': 'V4.82',
        'standard_scope_n': len(standard),
        'candidate_event_n': evidence['candidate_event_n'],
        'candidate_symbol_n': evidence['candidate_symbol_n'],
        'announcement_matched_event_n': evidence['announcement_matched_event_n'],
        'effective_override_event_n': len(event_rows),
        'effective_override_symbol_n': len({r['symbol'] for r in event_rows}),
        'fully_closed_symbol_n': len(closed),
        'remaining_exact_review_symbol_n': len(remaining),
        'closed_symbols': closed,
        'remaining_symbols': remaining,
        'checkpoint_after_effective_terms': checkpoint,
        'event_overrides': event_rows,
        'symbol_validation': symbol_rows,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--frozen-closure-dir', required=True)
    ap.add_argument('--evidence-dir', required=True)
    ap.add_argument('--source-census-dir', required=True)
    ap.add_argument('--special-closure-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    report = close_effective_terms(
        pathlib.Path(args.frozen_closure_dir),
        pathlib.Path(args.evidence_dir),
        pathlib.Path(args.source_census_dir),
        pathlib.Path(args.special_closure_dir),
    )
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'EFFECTIVE_TERM_CLOSURE_V482.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'EFFECTIVE_TERM_CLOSURE_V482.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        fields = ['symbol', 'status', 'frozen_max_diff_bp', 'max_diff_bp', 'worst_date', 'effective_override_event_n']
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in report['symbol_validation']:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({
        'effective_override_event_n': report['effective_override_event_n'],
        'fully_closed_symbol_n': report['fully_closed_symbol_n'],
        'remaining_exact_review_symbol_n': report['remaining_exact_review_symbol_n'],
        'checkpoint_after_effective_terms': report['checkpoint_after_effective_terms'],
        'closed_symbols': report['closed_symbols'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
