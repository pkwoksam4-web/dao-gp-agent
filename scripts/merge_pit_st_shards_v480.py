#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def merge_reports(reports, expected_symbols):
    symbols = [a.get('symbol') for r in reports for a in r.get('audits', [])]
    counts = Counter(symbols)
    duplicate = sorted([s for s, n in counts.items() if n > 1])
    missing = sorted(set(expected_symbols) - set(symbols))
    extra = sorted(set(symbols) - set(expected_symbols))
    audits = [a for r in reports for a in r.get('audits', [])]
    unresolved = sorted(a['symbol'] for a in audits if a.get('status') != 'MATERIALIZED_CANDIDATE_AUDIT_PENDING')
    lifecycle_unresolved = sorted(a['symbol'] for a in audits if not a.get('lifecycle_metadata_materialized', False))
    transition_symbols = sorted(a['symbol'] for a in audits if int(a.get('transition_count', 0)) > 0)
    partition_ok = not duplicate and not missing and not extra and len(symbols) == len(expected_symbols)
    return {
        'artifact': 'GP_PIT_ST_MATERIALIZATION_MERGED_V480',
        'version': 'V4.80',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope_n': len(expected_symbols),
        'audit_symbol_n': len(symbols),
        'duplicate_audit_symbols': duplicate,
        'missing_audit_symbols': missing,
        'extra_audit_symbols': extra,
        'materialization_partition_ok': partition_ok,
        'materialized_symbol_n': len(symbols) - len(unresolved),
        'unresolved_symbol_n': len(unresolved),
        'unresolved_symbols': unresolved,
        'lifecycle_unresolved_n': len(lifecycle_unresolved),
        'lifecycle_unresolved_symbols': lifecycle_unresolved,
        'transition_symbol_n': len(transition_symbols),
        'transition_symbols': transition_symbols,
        'daily_rows': sum(int(r.get('daily_rows', 0)) for r in reports),
        'formal_admission': False,
        'pit_st_gate_closed': False,
        'independent_transition_audit': 'PENDING',
        'audits': audits,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--scope', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    root = Path(args.root)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    expected = [x.strip().upper() for x in Path(args.scope).read_text(encoding='utf-8').splitlines() if x.strip()]
    report_paths = sorted(root.glob('**/PIT_ST_AUDIT_V480.json'))
    if not report_paths:
        raise RuntimeError('no shard reports found')
    reports = [json.loads(p.read_text(encoding='utf-8')) for p in report_paths]
    merged = merge_reports(reports, expected)

    rows = []
    for p in sorted(root.glob('**/PIT_ST_DAILY_V480.csv')):
        with p.open(encoding='utf-8', newline='') as f:
            rows.extend(csv.DictReader(f))
    keys = [(r['symbol'], r['date']) for r in rows]
    dup_rows = sorted([f'{s}|{d}' for (s, d), n in Counter(keys).items() if n > 1])
    merged['duplicate_daily_keys'] = dup_rows
    merged['daily_rows_actual'] = len(rows)
    merged['daily_rows_reported'] = merged['daily_rows']
    merged['daily_partition_ok'] = not dup_rows and len(rows) == merged['daily_rows']
    (out / 'PIT_ST_AUDIT_MERGED_V480.json').write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')

    with (out / 'PIT_ST_DAILY_MERGED_V480.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['symbol', 'date', 'code', 'tradestatus', 'isST'])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r['symbol'], r['date'])))

    checkpoint = {
        'artifact': 'FORMAL_GATE_CHECKPOINT_V480',
        'version': 'V4.80',
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'pit_st': {
            'status': 'MATERIALIZED_AUDIT_PENDING' if merged['materialization_partition_ok'] and merged['unresolved_symbol_n'] == 0 and merged['daily_partition_ok'] else 'MATERIALIZATION_INCOMPLETE',
            'scope_n': merged['scope_n'],
            'materialized_symbol_n': merged['materialized_symbol_n'],
            'unresolved_symbol_n': merged['unresolved_symbol_n'],
            'lifecycle_unresolved_n': merged['lifecycle_unresolved_n'],
            'daily_rows': merged['daily_rows_actual'],
            'independent_transition_audit': 'PENDING',
            'formal_admission': False,
        },
        'adjustment_provenance': 'SAMPLE50_CLOSED_V479__GLOBAL_847_OPEN',
        'locked_rule': 'No Formal OOS until PIT-ST and global 847 adjustment provenance close.',
    }
    (out / 'FORMAL_GATE_CHECKPOINT_V480.json').write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: merged[k] for k in ['scope_n','audit_symbol_n','materialization_partition_ok','unresolved_symbol_n','lifecycle_unresolved_n','transition_symbol_n','daily_rows_actual','daily_partition_ok']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
