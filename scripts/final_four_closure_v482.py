from __future__ import annotations

import argparse
import csv
import json
import pathlib

import effective_term_closure_v482 as base
import recovered_remaining_closure_v482 as recovered
import final_six_closure_v482 as final_six
import cninfo_effective_terms_final_v482 as final_terms
from materialize_standard_exact_pdfs_v481 import _parse_sina_js, factor_jump_ratio

THRESHOLD_BP = 5.0
CURRENT_CHECKPOINT = {
    'PASS': 840,
    'EXACT_TERM_REVIEW': 4,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}
EXPECTED_REMAINING_N = 4
EXPECTED_838_BASE_N = 262
EXPECTED_FINAL_SIX_ACCEPTED_N = 3
EXPECTED_BASE_OVERRIDE_N = 265


def merge_final_six_overrides(
    base_overrides: dict[tuple[str, str], float],
    rows: list[dict],
) -> dict[tuple[str, str], float]:
    extra: dict[tuple[str, str], float] = {}
    for row in rows or []:
        key = (
            str(row.get('symbol') or '').upper(),
            str(row.get('ex_date') or '')[:10],
        )
        if not key[0] or not key[1]:
            raise ValueError('final-six override missing symbol/ex_date')
        if key in base_overrides or key in extra:
            raise ValueError(f'final-six override collision: {key}')
        extra[key] = base._positive(row.get('corrected_event_ratio'), 'final-six corrected_event_ratio')
    return recovered.merge_override_maps(base_overrides, extra)


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
    active, ignored = [], []
    for row in rows or []:
        symbol = str(row.get('symbol') or '').upper()
        x = dict(row)
        x['symbol'] = symbol
        x['ex_date'] = str(row.get('ex_date') or '')[:10]
        (active if symbol in remaining else ignored).append(x)
    key = lambda r: (r.get('symbol') or '', r.get('ex_date') or '')
    return sorted(active, key=key), sorted(ignored, key=key)


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load(root: pathlib.Path, name: str) -> dict:
    return json.loads(_find_unique(root, name).read_text(encoding='utf-8'))


def close_final_four(
    frozen_closure_dir: pathlib.Path,
    effective_closure_dir: pathlib.Path,
    secondary_closure_dir: pathlib.Path,
    reparsed_closure_dir: pathlib.Path,
    recovered_838_dir: pathlib.Path,
    final_six_840_dir: pathlib.Path,
    recovered_92_evidence_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
) -> dict:
    frozen = _load(frozen_closure_dir, 'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json')
    effective = _load(effective_closure_dir, 'EFFECTIVE_TERM_CLOSURE_V482.json')
    secondary = _load(secondary_closure_dir, 'REMAINING_EXACT_CLOSURE_V482.json')
    reparsed = _load(reparsed_closure_dir, 'REPARSED_REMAINING_CLOSURE_V482.json')
    recovered_838 = _load(recovered_838_dir, 'RECOVERED_REMAINING_CLOSURE_V482.json')
    final_840 = _load(final_six_840_dir, 'FINAL_SIX_CLOSURE_V482.json')
    evidence = _load(recovered_92_evidence_dir, 'RECOVERED_REMAINING_PDF_EVIDENCE_V482.json')

    if final_840.get('checkpoint_after_final_six_terms') != CURRENT_CHECKPOINT:
        raise ValueError('input final-six closure is not verified 840/4 checkpoint')
    remaining = set(final_840.get('remaining_symbols') or [])
    if len(remaining) != EXPECTED_REMAINING_N:
        raise ValueError(f'expected {EXPECTED_REMAINING_N} remaining symbols; got {len(remaining)}')
    for obj in (effective, secondary, reparsed, recovered_838, final_840, evidence):
        if obj.get('formal_promotion') is not False or obj.get('validated_global_provenance_emitted') is not False:
            raise ValueError('non-Formal evidence guard violated')

    base208 = recovered._load_current_overrides(effective, secondary, reparsed)
    prior54 = recovered_838.get('accepted_overrides') or []
    base262 = final_six.merge_prior_recovered_overrides(base208, prior54)
    if len(base262) != EXPECTED_838_BASE_N:
        raise ValueError(f'expected {EXPECTED_838_BASE_N} overrides at 838 checkpoint; got {len(base262)}')
    final3 = final_840.get('accepted_overrides') or []
    if len(final3) != EXPECTED_FINAL_SIX_ACCEPTED_N:
        raise ValueError(f'expected {EXPECTED_FINAL_SIX_ACCEPTED_N} final-six overrides; got {len(final3)}')
    existing = merge_final_six_overrides(base262, final3)
    if len(existing) != EXPECTED_BASE_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_BASE_OVERRIDE_N} overrides at 840 checkpoint; got {len(existing)}')

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
    accepted_rows, rejected_rows, no_term_rows, text_error_rows, already_covered_rows = [], [], [], [], []

    for item in active_rows:
        symbol = item['symbol']
        ex_date = item['ex_date']
        key = (symbol, ex_date)
        if key in existing:
            already_covered_rows.append({'symbol': symbol, 'ex_date': ex_date, 'reason': 'ALREADY_ACCEPTED_BEFORE_840'})
            continue
        pdf = item.get('pdf_evidence') or {}
        if pdf.get('text_extract_ok') is not True:
            text_error_rows.append({'symbol': symbol, 'ex_date': ex_date, 'text_error': pdf.get('text_error') or pdf.get('error')})
            continue
        text_file = str(pdf.get('text_file') or '')
        if not text_file:
            text_error_rows.append({'symbol': symbol, 'ex_date': ex_date, 'text_error': 'missing text_file'})
            continue
        text = _find_unique(recovered_92_evidence_dir, pathlib.Path(text_file).name).read_text(encoding='utf-8', errors='replace')
        try:
            terms = final_terms.extract_effective_terms(text)
        except Exception as e:
            text_error_rows.append({'symbol': symbol, 'ex_date': ex_date, 'text_error': f'{type(e).__name__}: {e}'})
            continue
        if not any(terms.get(k) is not None for k in ('cash_per_share', 'cap_ratio', 'formula_share_change_ratio')):
            no_term_rows.append({'symbol': symbol, 'ex_date': ex_date, 'pdf_sha256': pdf.get('sha256')})
            continue
        event = recovered._event_by_date(frozen_by[symbol], ex_date)
        actual = factor_jump_ratio(factors_for(symbol), ex_date)
        try:
            ratio = final_terms.corrected_event_ratio(event, terms)
            diff = abs(actual / ratio - 1.0) * 10000.0
        except Exception as e:
            rejected_rows.append({
                'symbol': symbol, 'ex_date': ex_date, 'actual_factor_jump': actual,
                'rejection_reason': f'{type(e).__name__}: {e}',
            })
            continue
        row = {
            'symbol': symbol,
            'ex_date': ex_date,
            'actual_factor_jump': actual,
            'corrected_event_ratio': ratio,
            'corrected_event_diff_bp': diff,
            'cash_per_share_effective': terms.get('cash_per_share'),
            'cap_ratio_effective': terms.get('cap_ratio'),
            'formula_share_change_ratio': terms.get('formula_share_change_ratio'),
            'cash_evidence_kind': terms.get('cash_evidence_kind'),
            'cap_evidence_kind': terms.get('cap_evidence_kind'),
            'formula_share_change_evidence_kind': terms.get('formula_share_change_evidence_kind'),
            'announcement_id': (item.get('announcement') or {}).get('announcementId'),
            'pdf_sha256': pdf.get('sha256'),
            'rejection_reason': None if diff <= THRESHOLD_BP else 'EVENT_DIFF_ABOVE_5BP',
        }
        if diff > THRESHOLD_BP:
            rejected_rows.append(row)
            continue
        if key in new_map:
            raise ValueError(f'duplicate final-four accepted term: {key}')
        new_map[key] = base._positive(ratio, 'final-four corrected_event_ratio')
        accepted_rows.append(row)

    overrides = recovered.merge_override_maps(existing, new_map)
    prior_validation = {r['symbol']: r for r in (final_840.get('symbol_validation') or [])}
    symbol_rows = []
    for symbol in sorted(remaining):
        result = base.recompute_symbol_max_diff_bp(frozen_by[symbol], factors_for(symbol), overrides)
        previous = prior_validation[symbol]
        result['previous_max_diff_bp'] = float(previous['max_diff_bp'])
        result['existing_override_event_n'] = sum(1 for s, _ in existing if s == symbol)
        result['new_final_four_override_event_n'] = sum(1 for s, _ in new_map if s == symbol)
        symbol_rows.append(result)

    newly_closed = sorted(r['symbol'] for r in symbol_rows if r['status'] == 'PASS_EFFECTIVE_TERMS_V482')
    remaining_after = sorted(r['symbol'] for r in symbol_rows if r['status'] != 'PASS_EFFECTIVE_TERMS_V482')
    checkpoint = updated_checkpoint(CURRENT_CHECKPOINT, len(newly_closed))

    return {
        'artifact': 'FINAL_FOUR_CLOSURE_V482',
        'version': 'V4.82',
        'input_checkpoint': CURRENT_CHECKPOINT,
        'source_recovered_pdf_event_n': len(evidence.get('records') or []),
        'base_standard_override_n': len(existing),
        'active_evidence_event_n': len(active_rows),
        'ignored_other_symbol_evidence_n': len(ignored_rows),
        'already_covered_event_n': len(already_covered_rows),
        'accepted_new_override_n': len(accepted_rows),
        'rejected_term_event_n': len(rejected_rows),
        'no_term_event_n': len(no_term_rows),
        'text_error_event_n': len(text_error_rows),
        'total_standard_override_n': len(overrides),
        'newly_closed_symbol_n': len(newly_closed),
        'remaining_exact_review_symbol_n': len(remaining_after),
        'newly_closed_symbols': newly_closed,
        'remaining_symbols': remaining_after,
        'checkpoint_after_final_four_terms': checkpoint,
        'accepted_overrides': accepted_rows,
        'rejected_terms': rejected_rows,
        'no_term_events': no_term_rows,
        'text_errors': text_error_rows,
        'already_covered_events': already_covered_rows,
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
    ap.add_argument('--final-six-840-dir', required=True)
    ap.add_argument('--recovered-92-evidence-dir', required=True)
    ap.add_argument('--source-census-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    result = close_final_four(
        pathlib.Path(args.frozen_closure_dir),
        pathlib.Path(args.effective_closure_dir),
        pathlib.Path(args.secondary_closure_dir),
        pathlib.Path(args.reparsed_closure_dir),
        pathlib.Path(args.recovered_838_dir),
        pathlib.Path(args.final_six_840_dir),
        pathlib.Path(args.recovered_92_evidence_dir),
        pathlib.Path(args.source_census_dir),
    )
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'FINAL_FOUR_CLOSURE_V482.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'FINAL_FOUR_CLOSURE_V482.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        fields = ['symbol','status','previous_max_diff_bp','max_diff_bp','worst_date','existing_override_event_n','new_final_four_override_event_n']
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in result['symbol_validation']:
            writer.writerow({k: row.get(k) for k in fields})
    print(json.dumps({
        'accepted_new_override_n': result['accepted_new_override_n'],
        'rejected_term_event_n': result['rejected_term_event_n'],
        'no_term_event_n': result['no_term_event_n'],
        'text_error_event_n': result['text_error_event_n'],
        'newly_closed_symbol_n': result['newly_closed_symbol_n'],
        'remaining_exact_review_symbol_n': result['remaining_exact_review_symbol_n'],
        'checkpoint': result['checkpoint_after_final_four_terms'],
        'newly_closed_symbols': result['newly_closed_symbols'],
        'remaining_symbols': result['remaining_symbols'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
