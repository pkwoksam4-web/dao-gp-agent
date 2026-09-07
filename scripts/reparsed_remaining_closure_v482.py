from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib

import effective_term_closure_v482 as base
from materialize_standard_exact_pdfs_v481 import _parse_sina_js

THRESHOLD_BP = 5.0
CURRENT_CHECKPOINT = {
    'PASS': 821,
    'EXACT_TERM_REVIEW': 23,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}
EXPECTED_CURRENT_REMAINING_N = 23
EXPECTED_REPARSED_SOURCE_N = 203
EXPECTED_REPARSED_EVENT_N = 202
EXPECTED_REPARSED_PARSE_ERROR_N = 1
EXPECTED_REPARSED_EFFECTIVE_N = 142
EXPECTED_RELEVANT_EVENT_N = 32
EXPECTED_RELEVANT_EFFECTIVE_N = 20
EXPECTED_RELEVANT_PARSE_ERROR_N = 1
EXPECTED_RELEVANT_NO_TERM_N = 11
EXPECTED_EXISTING_OVERRIDE_N = 191
EXPECTED_CONFIRMED_EXISTING_N = 3
EXPECTED_NEW_OVERRIDE_N = 17
EXPECTED_TOTAL_OVERRIDE_N = 208
EXPECTED_NEW_CLOSED_N = 5
EXPECTED_FINAL_REMAINING_N = 18


def validate_reparsed_term(event: dict, terms: dict, actual_factor_jump: float, threshold_bp: float = THRESHOLD_BP) -> dict:
    try:
        ratio = base.corrected_event_ratio(event, terms)
    except (TypeError, ValueError, OverflowError) as exc:
        return {
            'accepted': False,
            'corrected_event_ratio': None,
            'corrected_event_diff_bp': float('inf'),
            'threshold_bp': float(threshold_bp),
            'rejection_reason': f'{type(exc).__name__}: {exc}',
        }
    actual = base._positive(actual_factor_jump, 'actual_factor_jump')
    diff = abs(actual / ratio - 1.0) * 10000.0
    return {
        'accepted': diff <= float(threshold_bp),
        'corrected_event_ratio': ratio,
        'corrected_event_diff_bp': diff,
        'threshold_bp': float(threshold_bp),
        'rejection_reason': None if diff <= float(threshold_bp) else f'event_diff_bp={diff:.12f}',
    }


def merge_override_maps(existing: dict[tuple[str, str], float], new: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    overlap = set(existing) & set(new)
    if overlap:
        raise ValueError(f'duplicate override keys: {sorted(overlap)}')
    out = dict(existing)
    out.update(new)
    return out


def updated_checkpoint(current: dict, newly_closed_n: int) -> dict:
    if dict(current) != CURRENT_CHECKPOINT:
        raise ValueError(f'current checkpoint mismatch: {current}')
    n = int(newly_closed_n)
    if n < 0 or n > int(current['EXACT_TERM_REVIEW']):
        raise ValueError('invalid newly-closed count')
    out = dict(current)
    out['PASS'] += n
    out['EXACT_TERM_REVIEW'] -= n
    if sum(out.values()) != 847:
        raise ValueError('847 partition invariant failed')
    return out


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _event_by_date(record: dict, ex_date: str) -> dict:
    hits = [e for e in (record.get('events') or []) if str(e.get('ex_date') or '')[:10] == ex_date]
    if len(hits) != 1:
        raise ValueError(f'{record.get("symbol")} {ex_date}: expected one frozen event; found={len(hits)}')
    return hits[0]


def _load_existing_overrides(effective: dict, secondary: dict) -> dict[tuple[str, str], float]:
    first = {}
    for row in effective.get('event_overrides') or []:
        key = (str(row.get('symbol') or '').upper(), str(row.get('ex_date') or '')[:10])
        first[key] = base._positive(row.get('corrected_event_ratio'), 'first-stage corrected_event_ratio')
    if len(first) != 67:
        raise ValueError(f'expected 67 first-stage overrides; got {len(first)}')
    second = {}
    for row in secondary.get('accepted_overrides') or []:
        key = (str(row.get('symbol') or '').upper(), str(row.get('ex_date') or '')[:10])
        second[key] = base._positive(row.get('corrected_event_ratio'), 'second-stage corrected_event_ratio')
    if len(second) != 124:
        raise ValueError(f'expected 124 second-stage overrides; got {len(second)}')
    out = merge_override_maps(first, second)
    if len(out) != EXPECTED_EXISTING_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_EXISTING_OVERRIDE_N} existing overrides; got {len(out)}')
    return out


def close_reparsed_remaining(
    frozen_closure_dir: pathlib.Path,
    effective_closure_dir: pathlib.Path,
    secondary_closure_dir: pathlib.Path,
    reparsed_evidence_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
) -> dict:
    frozen = _load(_find_unique(frozen_closure_dir, 'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json'))
    effective = _load(_find_unique(effective_closure_dir, 'EFFECTIVE_TERM_CLOSURE_V482.json'))
    secondary = _load(_find_unique(secondary_closure_dir, 'REMAINING_EXACT_CLOSURE_V482.json'))
    reparsed = _load(_find_unique(reparsed_evidence_dir, 'REMAINING_EXACT_REPARSED_EVIDENCE_V482.json'))

    if secondary.get('checkpoint_after_secondary_exact_terms') != CURRENT_CHECKPOINT:
        raise ValueError('input secondary closure is not the verified 821/23 checkpoint')
    remaining = set(secondary.get('remaining_symbols') or [])
    if len(remaining) != EXPECTED_CURRENT_REMAINING_N:
        raise ValueError(f'expected {EXPECTED_CURRENT_REMAINING_N} remaining symbols; got {len(remaining)}')
    if reparsed.get('source_matched_candidate_event_n') != EXPECTED_REPARSED_SOURCE_N:
        raise ValueError('reparsed source partition changed')
    if reparsed.get('reparsed_event_n') != EXPECTED_REPARSED_EVENT_N or reparsed.get('parse_error_event_n') != EXPECTED_REPARSED_PARSE_ERROR_N:
        raise ValueError('reparsed success/error partition changed')
    if reparsed.get('effective_term_event_n') != EXPECTED_REPARSED_EFFECTIVE_N:
        raise ValueError('reparsed effective-term partition changed')
    for obj in (effective, secondary, reparsed):
        if obj.get('formal_promotion') is not False or obj.get('validated_global_provenance_emitted') is not False:
            raise ValueError('non-Formal evidence guard violated')

    frozen_by = {str(r.get('symbol') or '').upper(): r for r in (frozen.get('records') or [])}
    existing = _load_existing_overrides(effective, secondary)

    relevant = [r for r in (reparsed.get('records') or []) if str(r.get('symbol') or '').upper() in remaining]
    if len(relevant) != EXPECTED_RELEVANT_EVENT_N:
        raise ValueError(f'expected {EXPECTED_RELEVANT_EVENT_N} relevant reparsed events; got {len(relevant)}')

    new_map = {}
    new_rows = []
    confirmed_rows = []
    rejected_rows = []
    no_term_rows = []
    parse_error_rows = []
    effective_seen = 0

    for item in relevant:
        symbol = str(item.get('symbol') or '').upper()
        ex_date = str(item.get('ex_date') or '')[:10]
        pdf = item.get('pdf_evidence') or {}
        reparse_error = pdf.get('reparse_error')
        if reparse_error:
            parse_error_rows.append({'symbol': symbol, 'ex_date': ex_date, 'reparse_error': reparse_error})
            continue
        terms = pdf.get('effective_terms') or {}
        if not any(terms.get(k) is not None for k in ('cash_per_share', 'cap_ratio')):
            no_term_rows.append({'symbol': symbol, 'ex_date': ex_date})
            continue
        effective_seen += 1
        event = _event_by_date(frozen_by[symbol], ex_date)
        check = validate_reparsed_term(event, terms, item.get('actual_factor_jump'), THRESHOLD_BP)
        row = {
            'symbol': symbol,
            'ex_date': ex_date,
            'accepted': check['accepted'],
            'corrected_event_ratio': check['corrected_event_ratio'],
            'corrected_event_diff_bp': check['corrected_event_diff_bp'],
            'cash_per_share_effective': terms.get('cash_per_share'),
            'cap_ratio_effective': terms.get('cap_ratio'),
            'cash_evidence_kind': terms.get('cash_evidence_kind'),
            'cap_evidence_kind': terms.get('cap_evidence_kind'),
            'rejection_reason': check['rejection_reason'],
        }
        if not check['accepted']:
            rejected_rows.append(row)
            continue
        key = (symbol, ex_date)
        ratio = base._positive(check['corrected_event_ratio'], 'reparsed corrected_event_ratio')
        if key in existing:
            prior = existing[key]
            diff_bp = abs(ratio / prior - 1.0) * 10000.0
            if diff_bp > 0.000001:
                raise ValueError(f'{symbol} {ex_date}: reparsed term conflicts with prior accepted override ({diff_bp:.12f}bp)')
            row['prior_override_ratio'] = prior
            row['prior_override_diff_bp'] = diff_bp
            confirmed_rows.append(row)
            continue
        if key in new_map:
            raise ValueError(f'duplicate new reparsed override {key}')
        new_map[key] = ratio
        new_rows.append(row)

    if effective_seen != EXPECTED_RELEVANT_EFFECTIVE_N:
        raise ValueError(f'expected {EXPECTED_RELEVANT_EFFECTIVE_N} relevant effective terms; got {effective_seen}')
    if len(parse_error_rows) != EXPECTED_RELEVANT_PARSE_ERROR_N or len(no_term_rows) != EXPECTED_RELEVANT_NO_TERM_N:
        raise ValueError(f'expected parse/no-term {EXPECTED_RELEVANT_PARSE_ERROR_N}/{EXPECTED_RELEVANT_NO_TERM_N}; got {len(parse_error_rows)}/{len(no_term_rows)}')
    if rejected_rows:
        raise ValueError(f'expected zero event-level rejections after reparse; got {len(rejected_rows)}')
    if len(confirmed_rows) != EXPECTED_CONFIRMED_EXISTING_N or len(new_rows) != EXPECTED_NEW_OVERRIDE_N:
        raise ValueError(f'expected confirmed/new {EXPECTED_CONFIRMED_EXISTING_N}/{EXPECTED_NEW_OVERRIDE_N}; got {len(confirmed_rows)}/{len(new_rows)}')

    overrides = merge_override_maps(existing, new_map)
    if len(overrides) != EXPECTED_TOTAL_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_TOTAL_OVERRIDE_N} total overrides; got {len(overrides)}')

    symbol_rows = []
    for symbol in sorted(remaining):
        record = frozen_by[symbol]
        code, exchange = symbol.split('.')
        raw = _find_unique(source_census_dir, f'{code}_{exchange}_sina_qfq.js').read_bytes()
        factors = _parse_sina_js(raw)
        result = base.recompute_symbol_max_diff_bp(record, factors, overrides)
        prior_row = next(r for r in secondary['symbol_validation'] if r['symbol'] == symbol)
        result['previous_max_diff_bp'] = float(prior_row['max_diff_bp'])
        result['existing_override_event_n'] = sum(1 for s, _ in existing if s == symbol)
        result['new_reparsed_override_event_n'] = sum(1 for s, _ in new_map if s == symbol)
        symbol_rows.append(result)

    newly_closed = sorted(r['symbol'] for r in symbol_rows if r['status'] == 'PASS_EFFECTIVE_TERMS_V482')
    remaining_after = sorted(r['symbol'] for r in symbol_rows if r['status'] != 'PASS_EFFECTIVE_TERMS_V482')
    if len(newly_closed) != EXPECTED_NEW_CLOSED_N or len(remaining_after) != EXPECTED_FINAL_REMAINING_N:
        raise ValueError(f'expected close/remain {EXPECTED_NEW_CLOSED_N}/{EXPECTED_FINAL_REMAINING_N}; got {len(newly_closed)}/{len(remaining_after)}')
    checkpoint = updated_checkpoint(secondary['checkpoint_after_secondary_exact_terms'], len(newly_closed))

    return {
        'artifact': 'REPARSED_REMAINING_CLOSURE_V482',
        'version': 'V4.82',
        'input_checkpoint': CURRENT_CHECKPOINT,
        'reparsed_source_event_n': EXPECTED_REPARSED_SOURCE_N,
        'relevant_reparsed_event_n': len(relevant),
        'relevant_effective_term_n': effective_seen,
        'relevant_parse_error_n': len(parse_error_rows),
        'relevant_no_term_n': len(no_term_rows),
        'confirmed_existing_override_n': len(confirmed_rows),
        'new_reparsed_override_n': len(new_rows),
        'total_standard_override_n': len(overrides),
        'newly_closed_symbol_n': len(newly_closed),
        'remaining_exact_review_symbol_n': len(remaining_after),
        'newly_closed_symbols': newly_closed,
        'remaining_symbols': remaining_after,
        'checkpoint_after_reparsed_terms': checkpoint,
        'new_overrides': sorted(new_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'confirmed_existing_overrides': sorted(confirmed_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'parse_errors': sorted(parse_error_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'no_term_events': sorted(no_term_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'symbol_validation': symbol_rows,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--frozen-closure-dir', required=True)
    ap.add_argument('--effective-closure-dir', required=True)
    ap.add_argument('--secondary-closure-dir', required=True)
    ap.add_argument('--reparsed-evidence-dir', required=True)
    ap.add_argument('--source-census-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    x = close_reparsed_remaining(
        pathlib.Path(args.frozen_closure_dir),
        pathlib.Path(args.effective_closure_dir),
        pathlib.Path(args.secondary_closure_dir),
        pathlib.Path(args.reparsed_evidence_dir),
        pathlib.Path(args.source_census_dir),
    )
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'REPARSED_REMAINING_CLOSURE_V482.json').write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'REPARSED_REMAINING_CLOSURE_V482.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        fields = ['symbol', 'status', 'previous_max_diff_bp', 'max_diff_bp', 'worst_date', 'existing_override_event_n', 'new_reparsed_override_event_n']
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in x['symbol_validation']:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({
        'new_reparsed_override_n': x['new_reparsed_override_n'],
        'total_standard_override_n': x['total_standard_override_n'],
        'newly_closed_symbol_n': x['newly_closed_symbol_n'],
        'remaining_exact_review_symbol_n': x['remaining_exact_review_symbol_n'],
        'checkpoint': x['checkpoint_after_reparsed_terms'],
        'newly_closed_symbols': x['newly_closed_symbols'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
