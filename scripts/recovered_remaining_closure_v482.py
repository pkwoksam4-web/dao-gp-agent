from __future__ import annotations

import argparse
import csv
import json
import pathlib

import effective_term_closure_v482 as base
from materialize_standard_exact_pdfs_v481 import _parse_sina_js, factor_jump_ratio

THRESHOLD_BP = 5.0
CURRENT_CHECKPOINT = {
    'PASS': 826,
    'EXACT_TERM_REVIEW': 18,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}
EXPECTED_CURRENT_REMAINING_N = 18
EXPECTED_BASE_OVERRIDE_N = 208


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


def validate_recovered_term(event: dict, terms: dict, actual_factor_jump: float, threshold_bp: float = THRESHOLD_BP) -> dict:
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


def _load_current_overrides(effective: dict, secondary: dict, reparsed: dict) -> dict[tuple[str, str], float]:
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

    third = {}
    for row in reparsed.get('new_overrides') or []:
        key = (str(row.get('symbol') or '').upper(), str(row.get('ex_date') or '')[:10])
        third[key] = base._positive(row.get('corrected_event_ratio'), 'reparsed corrected_event_ratio')
    if len(third) != 17:
        raise ValueError(f'expected 17 reparsed overrides; got {len(third)}')

    out = merge_override_maps(first, second)
    out = merge_override_maps(out, third)
    if len(out) != EXPECTED_BASE_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_BASE_OVERRIDE_N} current overrides; got {len(out)}')
    return out


def close_recovered_remaining(
    frozen_closure_dir: pathlib.Path,
    effective_closure_dir: pathlib.Path,
    secondary_closure_dir: pathlib.Path,
    reparsed_closure_dir: pathlib.Path,
    recovered_evidence_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
) -> dict:
    frozen = _load(_find_unique(frozen_closure_dir, 'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json'))
    effective = _load(_find_unique(effective_closure_dir, 'EFFECTIVE_TERM_CLOSURE_V482.json'))
    secondary = _load(_find_unique(secondary_closure_dir, 'REMAINING_EXACT_CLOSURE_V482.json'))
    reparsed = _load(_find_unique(reparsed_closure_dir, 'REPARSED_REMAINING_CLOSURE_V482.json'))
    evidence = _load(_find_unique(recovered_evidence_dir, 'RECOVERED_REMAINING_PDF_EVIDENCE_V482.json'))

    if reparsed.get('checkpoint_after_reparsed_terms') != CURRENT_CHECKPOINT:
        raise ValueError('input reparsed closure is not verified 826/18 checkpoint')
    remaining = set(reparsed.get('remaining_symbols') or [])
    if len(remaining) != EXPECTED_CURRENT_REMAINING_N:
        raise ValueError(f'expected {EXPECTED_CURRENT_REMAINING_N} remaining symbols; got {len(remaining)}')
    for obj in (effective, secondary, reparsed, evidence):
        if obj.get('formal_promotion') is not False or obj.get('validated_global_provenance_emitted') is not False:
            raise ValueError('non-Formal evidence guard violated')

    frozen_by = {str(r.get('symbol') or '').upper(): r for r in (frozen.get('records') or [])}
    existing = _load_current_overrides(effective, secondary, reparsed)
    factor_cache: dict[str, list[dict]] = {}

    def factors_for(symbol: str) -> list[dict]:
        if symbol not in factor_cache:
            code, exchange = symbol.split('.')
            raw = _find_unique(source_census_dir, f'{code}_{exchange}_sina_qfq.js').read_bytes()
            factor_cache[symbol] = _parse_sina_js(raw)
        return factor_cache[symbol]

    new_map: dict[tuple[str, str], float] = {}
    accepted_rows = []
    rejected_rows = []
    no_term_rows = []
    text_error_rows = []

    for item in evidence.get('records') or []:
        symbol = str(item.get('symbol') or '').upper()
        ex_date = str(item.get('ex_date') or '')[:10]
        if symbol not in remaining:
            raise ValueError(f'recovered PDF evidence outside current remaining scope: {symbol}')
        pdf = item.get('pdf_evidence') or {}
        if pdf.get('text_extract_ok') is not True:
            text_error_rows.append({'symbol': symbol, 'ex_date': ex_date, 'text_error': pdf.get('text_error') or pdf.get('error')})
            continue
        terms = pdf.get('effective_terms') or {}
        if not any(terms.get(k) is not None for k in ('cash_per_share', 'cap_ratio')):
            no_term_rows.append({'symbol': symbol, 'ex_date': ex_date, 'pdf_sha256': pdf.get('sha256')})
            continue
        event = _event_by_date(frozen_by[symbol], ex_date)
        actual_jump = factor_jump_ratio(factors_for(symbol), ex_date)
        check = validate_recovered_term(event, terms, actual_jump, THRESHOLD_BP)
        row = {
            'symbol': symbol,
            'ex_date': ex_date,
            'actual_factor_jump': actual_jump,
            'corrected_event_ratio': check['corrected_event_ratio'],
            'corrected_event_diff_bp': check['corrected_event_diff_bp'],
            'cash_per_share_effective': terms.get('cash_per_share'),
            'cap_ratio_effective': terms.get('cap_ratio'),
            'cash_evidence_kind': terms.get('cash_evidence_kind'),
            'cap_evidence_kind': terms.get('cap_evidence_kind'),
            'announcement_id': (item.get('announcement') or {}).get('announcementId'),
            'pdf_sha256': pdf.get('sha256'),
            'rejection_reason': check['rejection_reason'],
        }
        if not check['accepted']:
            rejected_rows.append(row)
            continue
        key = (symbol, ex_date)
        if key in existing:
            raise ValueError(f'recovered term collides with existing accepted override: {key}')
        if key in new_map:
            raise ValueError(f'duplicate recovered accepted term: {key}')
        new_map[key] = base._positive(check['corrected_event_ratio'], 'recovered corrected_event_ratio')
        accepted_rows.append(row)

    overrides = merge_override_maps(existing, new_map)
    symbol_rows = []
    for symbol in sorted(remaining):
        record = frozen_by[symbol]
        result = base.recompute_symbol_max_diff_bp(record, factors_for(symbol), overrides)
        prior = next(r for r in reparsed['symbol_validation'] if r['symbol'] == symbol)
        result['previous_max_diff_bp'] = float(prior['max_diff_bp'])
        result['existing_override_event_n'] = sum(1 for s, _ in existing if s == symbol)
        result['new_recovered_override_event_n'] = sum(1 for s, _ in new_map if s == symbol)
        symbol_rows.append(result)

    newly_closed = sorted(r['symbol'] for r in symbol_rows if r['status'] == 'PASS_EFFECTIVE_TERMS_V482')
    remaining_after = sorted(r['symbol'] for r in symbol_rows if r['status'] != 'PASS_EFFECTIVE_TERMS_V482')
    checkpoint = updated_checkpoint(reparsed['checkpoint_after_reparsed_terms'], len(newly_closed))

    return {
        'artifact': 'RECOVERED_REMAINING_CLOSURE_V482',
        'version': 'V4.82',
        'input_checkpoint': CURRENT_CHECKPOINT,
        'source_matched_event_n': int(evidence.get('matched_event_n') or 0),
        'source_pdf_text_ok_event_n': int(evidence.get('pdf_text_ok_event_n') or 0),
        'source_effective_term_event_n': int(evidence.get('effective_term_event_n') or 0),
        'base_standard_override_n': len(existing),
        'accepted_new_override_n': len(accepted_rows),
        'rejected_term_event_n': len(rejected_rows),
        'no_term_event_n': len(no_term_rows),
        'text_error_event_n': len(text_error_rows),
        'total_standard_override_n': len(overrides),
        'newly_closed_symbol_n': len(newly_closed),
        'remaining_exact_review_symbol_n': len(remaining_after),
        'newly_closed_symbols': newly_closed,
        'remaining_symbols': remaining_after,
        'checkpoint_after_recovered_terms': checkpoint,
        'accepted_overrides': sorted(accepted_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'rejected_terms': sorted(rejected_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'no_term_events': sorted(no_term_rows, key=lambda r: (r['symbol'], r['ex_date'])),
        'text_errors': sorted(text_error_rows, key=lambda r: (r['symbol'], r['ex_date'])),
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
    ap.add_argument('--reparsed-closure-dir', required=True)
    ap.add_argument('--recovered-evidence-dir', required=True)
    ap.add_argument('--source-census-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    x = close_recovered_remaining(
        pathlib.Path(args.frozen_closure_dir),
        pathlib.Path(args.effective_closure_dir),
        pathlib.Path(args.secondary_closure_dir),
        pathlib.Path(args.reparsed_closure_dir),
        pathlib.Path(args.recovered_evidence_dir),
        pathlib.Path(args.source_census_dir),
    )
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'RECOVERED_REMAINING_CLOSURE_V482.json').write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'RECOVERED_REMAINING_CLOSURE_V482.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        fields = ['symbol','status','previous_max_diff_bp','max_diff_bp','worst_date','existing_override_event_n','new_recovered_override_event_n']
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in x['symbol_validation']:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({
        'accepted_new_override_n': x['accepted_new_override_n'],
        'rejected_term_event_n': x['rejected_term_event_n'],
        'newly_closed_symbol_n': x['newly_closed_symbol_n'],
        'remaining_exact_review_symbol_n': x['remaining_exact_review_symbol_n'],
        'checkpoint': x['checkpoint_after_recovered_terms'],
        'newly_closed_symbols': x['newly_closed_symbols'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
