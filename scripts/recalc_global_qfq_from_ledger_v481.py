from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import time
from collections import Counter, defaultdict

from sample50_validate import (
    compare_factor_path,
    event_ratio,
    expected_factor_for_date,
    merge_actions,
    normalize_rights_rows,
    normalize_sharebonus_rows,
    parse_sina_qfq,
    parse_sohu_history_bytes,
    prev_close_before,
    sina_normalized_for_date,
)

FORMAL_BEG = '2020-06-01'
FORMAL_END = '2026-04-17'
THRESHOLD_BP = 5.0


def rows_by_security_code(rows):
    """Group global-ledger rows by six-digit SECURITY_CODE without collapsing duplicates."""
    out = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            raise ValueError('ledger row must be a dict')
        code = str(row.get('SECURITY_CODE') or '').strip()
        if len(code) != 6 or not code.isdigit():
            raise ValueError(f'invalid SECURITY_CODE: {code!r}')
        out[code].append(row)
    return dict(out)


def classify_result(
    formal_row_n: int,
    event_count: int,
    factor_compare_status: str | None,
    ledger_event_dates,
    sina_event_dates,
) -> str:
    """Fail-closed classification for the complete-global-ledger recalc stage."""
    if formal_row_n <= 0:
        return 'NOT_APPLICABLE_NO_FORMAL_ROWS'

    ledger_dates = sorted(set(ledger_event_dates or []))
    sina_dates = sorted(set(sina_event_dates or []))

    if ledger_dates != sina_dates:
        return 'REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH'

    if factor_compare_status is None:
        return 'REVIEW_GLOBAL_LEDGER_FACTOR_COMPARISON'

    if factor_compare_status == 'PASS':
        if event_count <= 0:
            return 'PASS_GLOBAL_LEDGER_PROVEN_NO_ACTION'
        return 'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR'

    if factor_compare_status == 'FAIL':
        return 'REVIEW_GLOBAL_LEDGER_EXACT_TERMS'

    return 'REVIEW_GLOBAL_LEDGER_FACTOR_COMPARISON'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with path.open(encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f'{path.name}:{lineno} is not an object')
            rows.append(row)
    return rows


def read_scope(path: pathlib.Path) -> list[str]:
    symbols = [x.strip().upper() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(symbols) != 847 or len(set(symbols)) != 847:
        raise RuntimeError(f'V4.81 requires exact 847 scope; rows={len(symbols)} unique={len(set(symbols))}')
    for symbol in symbols:
        code, exch = symbol.split('.')
        if len(code) != 6 or not code.isdigit() or exch not in {'SZ', 'SH'}:
            raise RuntimeError(f'invalid A-share symbol in scope: {symbol}')
    return symbols


def validate_ledger_dir(ledger_dir: pathlib.Path) -> tuple[list[dict], list[dict], dict]:
    audit_path = ledger_dir / 'GLOBAL_EVENT_LEDGER_AUDIT_V481.json'
    share_path = ledger_dir / 'RPT_SHAREBONUS_DET_FORMAL_LEDGER_V481.jsonl'
    rights_path = ledger_dir / 'RPT_IPO_ALLOTMENT_FORMAL_LEDGER_V481.jsonl'
    for p in (audit_path, share_path, rights_path):
        if not p.exists():
            raise RuntimeError(f'missing global ledger input: {p}')

    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    if audit.get('artifact') != 'GLOBAL_EVENT_LEDGER_V481':
        raise RuntimeError('unexpected global ledger artifact id')
    if audit.get('status') != 'GLOBAL_EVENT_LEDGER_EXPLICIT_SUCCESS':
        raise RuntimeError('global ledger is not explicitly complete')
    if audit.get('formal_window') != [FORMAL_BEG, FORMAL_END]:
        raise RuntimeError('global ledger Formal window mismatch')
    if audit.get('formal_promotion') is not False or audit.get('validated_global_provenance_emitted') is not False:
        raise RuntimeError('upstream ledger unexpectedly promoted Formal state')

    report_meta = {r.get('report'): r for r in audit.get('reports', [])}
    for report in ('RPT_SHAREBONUS_DET', 'RPT_IPO_ALLOTMENT'):
        meta = report_meta.get(report) or {}
        if meta.get('status') != 'GLOBAL_LEDGER_EXPLICIT_SUCCESS':
            raise RuntimeError(f'{report} ledger incomplete')
        if meta.get('page_hash_recheck') != 'PASS_BYTE_IDENTICAL_TWO_PASS':
            raise RuntimeError(f'{report} page hash recheck not closed')
        if int(meta.get('row_count', -1)) != int(meta.get('api_count', -2)):
            raise RuntimeError(f'{report} row/api count mismatch')

    share_rows = load_jsonl(share_path)
    rights_rows = load_jsonl(rights_path)
    if len(share_rows) != int(report_meta['RPT_SHAREBONUS_DET']['row_count']):
        raise RuntimeError('sharebonus JSONL row count mismatch')
    if len(rights_rows) != int(report_meta['RPT_IPO_ALLOTMENT']['row_count']):
        raise RuntimeError('rights JSONL row count mismatch')
    return share_rows, rights_rows, audit


def build_basename_index(root: pathlib.Path, suffix: str) -> dict[str, list[pathlib.Path]]:
    out: dict[str, list[pathlib.Path]] = defaultdict(list)
    for p in root.rglob('*' + suffix):
        if p.is_file():
            out[p.name].append(p)
    return dict(out)


def unique_input(index: dict[str, list[pathlib.Path]], basename: str) -> pathlib.Path:
    paths = index.get(basename, [])
    if len(paths) != 1:
        raise FileNotFoundError(f'expected exactly one {basename}; found={len(paths)}')
    return paths[0]


def recalc_symbol(
    symbol: str,
    share_by_code: dict[str, list[dict]],
    rights_by_code: dict[str, list[dict]],
    sina_index: dict[str, list[pathlib.Path]],
    sohu_index: dict[str, list[pathlib.Path]],
) -> dict:
    code, exch = symbol.split('.')
    prefix = f'{code}_{exch}'
    rec = {
        'symbol': symbol,
        'status': None,
        'formal_rows': 0,
        'sharebonus_ledger_rows': len(share_by_code.get(code, [])),
        'rights_ledger_rows': len(rights_by_code.get(code, [])),
        'event_count': 0,
        'ledger_event_dates': [],
        'sina_event_dates': [],
        'missing_in_sina': [],
        'missing_in_ledger': [],
        'factor_validation': None,
        'events': [],
        'source_meta': {},
        'error': None,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
    }

    try:
        sina_path = unique_input(sina_index, prefix + '_sina_qfq.js')
        sohu_path = unique_input(sohu_index, prefix + '_sohu_raw_history.js')
        sina_raw = sina_path.read_bytes()
        sohu_raw = sohu_path.read_bytes()
        rec['source_meta']['sina'] = {
            'path': str(sina_path), 'bytes': len(sina_raw), 'sha256': sha256_bytes(sina_raw),
            'provenance': 'corrected V4.81 source census run 34009079533 artifact gp-global-qfq-source-census-v481',
        }
        rec['source_meta']['sohu'] = {
            'path': str(sohu_path), 'bytes': len(sohu_raw), 'sha256': sha256_bytes(sohu_raw),
            'provenance': 'V4.81 nominal shard raw run 34009535349',
        }
        factors = parse_sina_qfq(sina_raw)
        raw_rows = parse_sohu_history_bytes(sohu_raw)
        if len({r['date'] for r in raw_rows}) != len(raw_rows):
            raise ValueError('duplicate Sohu dates')
    except Exception as e:
        rec['status'] = 'BLOCKED_GLOBAL_LEDGER_RAW_SOURCE'
        rec['error'] = f'{type(e).__name__}: {e}'
        return rec

    formal_rows = [r for r in raw_rows if FORMAL_BEG <= r['date'] <= FORMAL_END]
    rec['formal_rows'] = len(formal_rows)
    if not formal_rows:
        rec['status'] = 'NOT_APPLICABLE_NO_FORMAL_ROWS'
        return rec

    try:
        actions = merge_actions(
            normalize_sharebonus_rows(symbol, share_by_code.get(code, []))
            + normalize_rights_rows(symbol, rights_by_code.get(code, []))
        )
        actions = [a for a in actions if FORMAL_BEG < a.ex_date <= FORMAL_END]
    except Exception as e:
        rec['status'] = 'REVIEW_GLOBAL_LEDGER_EVENT_PARSE'
        rec['error'] = f'{type(e).__name__}: {e}'
        return rec

    ledger_dates = sorted({a.ex_date for a in actions})
    sina_dates = sorted({r['date'] for r in factors if FORMAL_BEG < r['date'] <= FORMAL_END})
    rec['event_count'] = len(actions)
    rec['ledger_event_dates'] = ledger_dates
    rec['sina_event_dates'] = sina_dates
    rec['missing_in_sina'] = sorted(set(ledger_dates) - set(sina_dates))
    rec['missing_in_ledger'] = sorted(set(sina_dates) - set(ledger_dates))

    factor_status = None
    try:
        ratios = {}
        for a in actions:
            prev_close = prev_close_before(raw_rows, a.ex_date)
            ratio = event_ratio(a, prev_close)
            ratios[a.ex_date] = ratio
            rec['events'].append({
                'ex_date': a.ex_date,
                'cash_per_share_nominal': a.cash_per_share,
                'stock_ratio': a.stock_ratio,
                'capitalization_ratio': a.cap_ratio,
                'rights_ratio': a.rights_ratio,
                'rights_price': a.rights_price,
                'prev_actual_close': prev_close,
                'event_ratio': ratio,
                'source': a.source,
            })

        expected = {
            r['date']: expected_factor_for_date(r['date'], actions, ratios, FORMAL_END)
            for r in formal_rows
        }
        actual = {
            r['date']: sina_normalized_for_date(factors, r['date'], FORMAL_END)
            for r in formal_rows
        }
        cmp = compare_factor_path(formal_rows, expected, actual, THRESHOLD_BP)
        rec['factor_validation'] = cmp
        factor_status = cmp['status']
    except Exception as e:
        rec['status'] = 'REVIEW_GLOBAL_LEDGER_FACTOR_COMPARISON'
        rec['error'] = f'{type(e).__name__}: {e}'
        return rec

    rec['status'] = classify_result(
        len(formal_rows), len(actions), factor_status, ledger_dates, sina_dates
    )
    return rec


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    fields = [
        'symbol', 'status', 'formal_rows', 'event_count', 'sharebonus_ledger_rows',
        'rights_ledger_rows', 'max_diff_bp', 'ledger_event_dates', 'sina_event_dates',
        'missing_in_sina', 'missing_in_ledger', 'error',
    ]
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            fv = r.get('factor_validation') or {}
            w.writerow({
                'symbol': r.get('symbol'),
                'status': r.get('status'),
                'formal_rows': r.get('formal_rows'),
                'event_count': r.get('event_count'),
                'sharebonus_ledger_rows': r.get('sharebonus_ledger_rows'),
                'rights_ledger_rows': r.get('rights_ledger_rows'),
                'max_diff_bp': fv.get('max_diff_bp'),
                'ledger_event_dates': '|'.join(r.get('ledger_event_dates') or []),
                'sina_event_dates': '|'.join(r.get('sina_event_dates') or []),
                'missing_in_sina': '|'.join(r.get('missing_in_sina') or []),
                'missing_in_ledger': '|'.join(r.get('missing_in_ledger') or []),
                'error': r.get('error'),
            })


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--scope', required=True)
    p.add_argument('--ledger-dir', required=True)
    p.add_argument('--source-census', required=True)
    p.add_argument('--nominal-shards', required=True)
    p.add_argument('--out-dir', required=True)
    args = p.parse_args()

    scope = read_scope(pathlib.Path(args.scope))
    share_rows, rights_rows, ledger_audit = validate_ledger_dir(pathlib.Path(args.ledger_dir))
    share_by_code = rows_by_security_code(share_rows)
    rights_by_code = rows_by_security_code(rights_rows)

    sina_index = build_basename_index(pathlib.Path(args.source_census), '_sina_qfq.js')
    sohu_index = build_basename_index(pathlib.Path(args.nominal_shards), '_sohu_raw_history.js')

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    records = []
    for i, symbol in enumerate(scope, 1):
        rec = recalc_symbol(symbol, share_by_code, rights_by_code, sina_index, sohu_index)
        records.append(rec)
        if i % 50 == 0 or i == len(scope):
            print(json.dumps({'progress': i, 'total': len(scope), 'symbol': symbol, 'status': rec['status']}, ensure_ascii=False), flush=True)

    if len(records) != 847 or len({r['symbol'] for r in records}) != 847:
        raise RuntimeError('recalc output is not exact 847 partition')

    counts = Counter(r['status'] for r in records)
    pass_statuses = {'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR', 'PASS_GLOBAL_LEDGER_PROVEN_NO_ACTION'}
    pass_n = sum(1 for r in records if r['status'] in pass_statuses)
    not_applicable_n = sum(1 for r in records if r['status'] == 'NOT_APPLICABLE_NO_FORMAL_ROWS')
    review_records = [r for r in records if r['status'] not in pass_statuses and r['status'] != 'NOT_APPLICABLE_NO_FORMAL_ROWS']
    compared = [r for r in records if isinstance(r.get('factor_validation'), dict)]
    over_5bp = [r for r in compared if float(r['factor_validation'].get('max_diff_bp', 0.0)) > THRESHOLD_BP]

    report = {
        'artifact': 'GLOBAL_QFQ_LEDGER_RECALC_V481',
        'version': 'V4.81',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'formal_window': [FORMAL_BEG, FORMAL_END],
        'threshold_bp': THRESHOLD_BP,
        'scope_n': 847,
        'record_n': len(records),
        'partition_exact': len(records) == 847 and len({r['symbol'] for r in records}) == 847,
        'status_counts': dict(sorted(counts.items())),
        'nominal_pass_n': pass_n,
        'not_applicable_n': not_applicable_n,
        'review_n': len(review_records),
        'factor_compared_n': len(compared),
        'factor_over_5bp_n': len(over_5bp),
        'global_event_ledger': {
            'artifact': ledger_audit.get('artifact'),
            'status': ledger_audit.get('status'),
            'sharebonus_rows': len(share_rows),
            'rights_rows': len(rights_rows),
            'coverage_semantics': ledger_audit.get('coverage_semantics'),
            'source_run': 34009915082,
            'source_artifact': 'gp-global-event-ledger-v481',
        },
        'source_factor_census': {
            'source_run': 34009079533,
            'source_artifact': 'gp-global-qfq-source-census-v481',
        },
        'raw_history_source': {
            'source_run': 34009535349,
            'source_artifacts': 'gp-global-qfq-nominal-v481-shard-*',
        },
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'interpretation': 'Complete global EastMoney ledgers close negative corporate-action coverage. Numeric PASS remains nominal triage only; exact-term and event-date mismatches require official implementation evidence before global provenance can close.',
        'locked_rule': 'No Formal OOS until PIT-ST and global 847 adjustment provenance close.',
        'records': records,
        'review_records': review_records,
    }
    (out / 'GLOBAL_QFQ_LEDGER_RECALC_V481.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(out / 'GLOBAL_QFQ_LEDGER_VALIDATION_MATRIX_V481.csv', records)
    write_csv(out / 'GLOBAL_QFQ_LEDGER_REVIEW_QUEUE_V481.csv', review_records)

    checkpoint = {
        'artifact': 'FORMAL_GATE_CHECKPOINT_V481_LEDGER_RECALC',
        'version': 'V4.81',
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'pit_st': 'CLOSED_V480_BAOSTOCK_MATERIALIZED_AUDITED',
        'adjustment_provenance': {
            'status': 'GLOBAL_847_LEDGER_RECALC_COMPLETE__EXACT_REVIEW_OPEN',
            'scope_n': 847,
            'nominal_pass_n': pass_n,
            'not_applicable_n': not_applicable_n,
            'review_n': len(review_records),
            'factor_over_5bp_n': len(over_5bp),
            'validated_global_provenance_emitted': False,
        },
        'locked_rule': 'No Formal OOS until PIT-ST and global 847 adjustment provenance close.',
    }
    (out / 'FORMAL_GATE_CHECKPOINT_V481_LEDGER_RECALC.json').write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({
        'done': True,
        'scope_n': 847,
        'status_counts': report['status_counts'],
        'nominal_pass_n': pass_n,
        'not_applicable_n': not_applicable_n,
        'review_n': len(review_records),
        'factor_compared_n': len(compared),
        'factor_over_5bp_n': len(over_5bp),
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
