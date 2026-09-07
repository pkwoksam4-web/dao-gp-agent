from __future__ import annotations

import argparse
import csv
import json
import pathlib

import effective_term_closure_v482 as base
import recovered_remaining_closure_v482 as prior
from materialize_standard_exact_pdfs_v481 import _parse_sina_js, factor_jump_ratio

THRESHOLD_BP = 5.0
CURRENT_CHECKPOINT = {
    'PASS': 838,
    'EXACT_TERM_REVIEW': 6,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}
EXPECTED_REMAINING_N = 6
EXPECTED_PREVIOUS_BASE_OVERRIDE_N = 208
EXPECTED_PRIOR_ACCEPTED_N = 54
EXPECTED_BASE_OVERRIDE_N = 262


def merge_prior_recovered_overrides(
    base_overrides: dict[tuple[str, str], float],
    prior_rows: list[dict],
) -> dict[tuple[str, str], float]:
    recovered: dict[tuple[str, str], float] = {}
    for row in prior_rows or []:
        key = (
            str(row.get('symbol') or '').upper(),
            str(row.get('ex_date') or '')[:10],
        )
        if not key[0] or not key[1]:
            raise ValueError('prior recovered override missing symbol/ex_date')
        if key in recovered:
            raise ValueError(f'duplicate prior recovered override: {key}')
        recovered[key] = base._positive(
            row.get('corrected_event_ratio'), 'prior recovered corrected_event_ratio'
        )
    return prior.merge_override_maps(base_overrides, recovered)


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


def partition_evidence_scope(rows: list[dict], remaining: set[str]) -> tuple[list[dict], list[dict]]:
    active = []
    ignored = []
    for row in rows or []:
        symbol = str(row.get('symbol') or '').upper()
        normalized = dict(row)
        normalized['symbol'] = symbol
        normalized['ex_date'] = str(row.get('ex_date') or '')[:10]
        (active if symbol in remaining else ignored).append(normalized)
    key = lambda r: (r.get('symbol') or '', r.get('ex_date') or '')
    return sorted(active, key=key), sorted(ignored, key=key)


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load(root: pathlib.Path, name: str) -> dict:
    return json.loads(_find_unique(root, name).read_text(encoding='utf-8'))


def close_final_six(
    frozen_closure_dir: pathlib.Path,
    effective_closure_dir: pathlib.Path,
    secondary_closure_dir: pathlib.Path,
    reparsed_closure_dir: pathlib.Path,
    recovered_838_dir: pathlib.Path,
    final_six_evidence_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
) -> dict:
    frozen = _load(frozen_closure_dir, 'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json')
    effective = _load(effective_closure_dir, 'EFFECTIVE_TERM_CLOSURE_V482.json')
    secondary = _load(secondary_closure_dir, 'REMAINING_EXACT_CLOSURE_V482.json')
    reparsed = _load(reparsed_closure_dir, 'REPARSED_REMAINING_CLOSURE_V482.json')
    recovered_838 = _load(recovered_838_dir, 'RECOVERED_REMAINING_CLOSURE_V482.json')
    evidence = _load(final_six_evidence_dir, 'RECOVERED_REMAINING_PDF_EVIDENCE_V482.json')

    if recovered_838.get('checkpoint_after_recovered_terms') != CURRENT_CHECKPOINT:
        raise ValueError('input recovered closure is not verified 838/6 checkpoint')
    remaining = set(recovered_838.get('remaining_symbols') or [])
    if len(remaining) != EXPECTED_REMAINING_N:
        raise ValueError(f'expected {EXPECTED_REMAINING_N} remaining symbols; got {len(remaining)}')
    for obj in (effective, secondary, reparsed, recovered_838, evidence):
        if obj.get('formal_promotion') is not False or obj.get('validated_global_provenance_emitted') is not False:
            raise ValueError('non-Formal evidence guard violated')

    base208 = prior._load_current_overrides(effective, secondary, reparsed)
    if len(base208) != EXPECTED_PREVIOUS_BASE_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_PREVIOUS_BASE_OVERRIDE_N} prior base overrides; got {len(base208)}')
    prior_rows = recovered_838.get('accepted_overrides') or []
    if len(prior_rows) != EXPECTED_PRIOR_ACCEPTED_N:
        raise ValueError(f'expected {EXPECTED_PRIOR_ACCEPTED_N} prior recovered overrides; got {len(prior_rows)}')
    existing = merge_prior_recovered_overrides(base208, prior_rows)
    if len(existing) != EXPECTED_BASE_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_BASE_OVERRIDE_N} 838-checkpoint overrides; got {len(existing)}')

    frozen_by = {str(r.get('symbol') or '').upper(): r for r in (frozen.get('records') or [])}
    factor_cache: dict[str, list[dict]] = {}

    def factors_for(symbol: str) -> list[dict]:
        if symbol not in factor_cache:
            code, exchange = symbol.split('.')
            raw = _find_unique(source_census_dir, f'{code}_{exchange}_sina_qfq.js').read_bytes()
            factor_cache[symbol] = _parse_sina_js(raw)
        return factor_cache[symbol]

    active_rows, ignored_rows = partition_evidence_scope(evidence.get('records') or [], remaining)
    new_map: dict[tuple[str, str], float] = {}
    accepted_rows = []
    rejected_rows = []
    no_term_rows = []
    text_error_rows = []

    for item in active_rows:
        symbol = item['symbol']
        ex_date = item['ex_date']
        pdf = item.get('pdf_evidence') or {}
        if pdf.get('text_extract_ok') is not True:
            text_error_rows.append({'symbol': symbol, 'ex_date': ex_date, 'text_error': pdf.get('text_error') or pdf.get('error')})
            continue
        terms = pdf.get('effective_terms') or {}
        if not any(terms.get(k) is not None for k in ('cash_per_share', 'cap_ratio')):
            no_term_rows.append({'symbol': symbol, 'ex_date': ex_date, 'pdf_sha256': pdf.get('sha256')})
            continue
        event = prior._event_by_date(frozen_by[symbol], ex_date)
        actual_jump = factor_jump_ratio(factors_for(symbol), ex_date)
        check = prior.validate_recovered_term(event, terms, actual_jump, THRESHOLD_BP)
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
            raise ValueError(f'final-six term collides with existing accepted override: {key}')
        if key in new_map:
            raise ValueError(f'duplicate final-six accepted term: {key}')
        new_map[key] = base._positive(check['corrected_event_ratio'], 'final-six corrected_event_ratio')
        accepted_rows.append(row)

    overrides = prior.merge_override_maps(existing, new_map)
    symbol_rows = []
    prior_validation = {r['symbol']: r for r in (recovered_838.get('symbol_validation') or [])}
    for symbol in sorted(remaining):
        result = base.recompute_symbol_max_diff_bp(frozen_by[symbol], factors_for(symbol), overrides)
        previous = prior_validation[symbol]
        result['previous_max_diff_bp'] = float(previous['max_diff_bp'])
        result['existing_override_event_n'] = sum(1 for s, _ in existing if s == symbol)
        result['new_final_six_override_event_n'] = sum(1 for s, _ in new_map if s == symbol)
        symbol_rows.append(result)

    newly_closed = sorted(r['symbol'] for r in symbol_rows if r['status'] == 'PASS_EFFECTIVE_TERMS_V482')
    remaining_after = sorted(r['symbol'] for r in symbol_rows if r['status'] != 'PASS_EFFECTIVE_TERMS_V482')
    checkpoint = updated_checkpoint(CURRENT_CHECKPOINT, len(newly_closed))

    return {
        'artifact': 'FINAL_SIX_CLOSURE_V482',
        'version': 'V4.82',
        'input_checkpoint': CURRENT_CHECKPOINT,
        'source_matched_event_n': int(evidence.get('matched_event_n') or 0),
        'source_pdf_text_ok_event_n': int(evidence.get('pdf_text_ok_event_n') or 0),
        'source_effective_term_event_n': int(evidence.get('effective_term_event_n') or 0),
        'base_standard_override_n': len(existing),
        'active_evidence_event_n': len(active_rows),
        'ignored_already_closed_evidence_n': len(ignored_rows),
        'accepted_new_override_n': len(accepted_rows),
        'rejected_term_event_n': len(rejected_rows),
        'no_term_event_n': len(no_term_rows),
        'text_error_event_n': len(text_error_rows),
        'total_standard_override_n': len(overrides),
        'newly_closed_symbol_n': len(newly_closed),
        'remaining_exact_review_symbol_n': len(remaining_after),
        'newly_closed_symbols': newly_closed,
        'remaining_symbols': remaining_after,
        'checkpoint_after_final_six_terms': checkpoint,
        'accepted_overrides': accepted_rows,
        'rejected_terms': rejected_rows,
        'no_term_events': no_term_rows,
        'text_errors': text_error_rows,
        'ignored_evidence': [
            {'symbol': r['symbol'], 'ex_date': r['ex_date'], 'reason': 'ALREADY_CLOSED_AT_838_CHECKPOINT'}
            for r in ignored_rows
        ],
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
    ap.add_argument('--recovered-838-dir', required=True)
    ap.add_argument('--final-six-evidence-dir', required=True)
    ap.add_argument('--source-census-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    result = close_final_six(
        pathlib.Path(args.frozen_closure_dir),
        pathlib.Path(args.effective_closure_dir),
        pathlib.Path(args.secondary_closure_dir),
        pathlib.Path(args.reparsed_closure_dir),
        pathlib.Path(args.recovered_838_dir),
        pathlib.Path(args.final_six_evidence_dir),
        pathlib.Path(args.source_census_dir),
    )
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'FINAL_SIX_CLOSURE_V482.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'FINAL_SIX_CLOSURE_V482.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        fields = ['symbol','status','previous_max_diff_bp','max_diff_bp','worst_date','existing_override_event_n','new_final_six_override_event_n']
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in result['symbol_validation']:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({
        'accepted_new_override_n': result['accepted_new_override_n'],
        'rejected_term_event_n': result['rejected_term_event_n'],
        'no_term_event_n': result['no_term_event_n'],
        'ignored_already_closed_evidence_n': result['ignored_already_closed_evidence_n'],
        'newly_closed_symbol_n': result['newly_closed_symbol_n'],
        'remaining_exact_review_symbol_n': result['remaining_exact_review_symbol_n'],
        'checkpoint': result['checkpoint_after_final_six_terms'],
        'newly_closed_symbols': result['newly_closed_symbols'],
        'remaining_symbols': result['remaining_symbols'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
