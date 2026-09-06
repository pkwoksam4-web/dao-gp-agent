from __future__ import annotations

import argparse
import csv
import json
import pathlib
import time
from collections import Counter

PASS_STATUSES = {
    'PASS_NOMINAL_EVENT_FACTOR',
    'PASS_PROVEN_NO_FORMAL_ACTIONS',
    'NOT_APPLICABLE_NO_FORMAL_ROWS',
}


def merge_records(scope: list[str], records: list[dict]) -> dict:
    scope = [str(s).strip().upper() for s in scope]
    if len(scope) != len(set(scope)):
        raise ValueError('duplicate symbol in scope')
    seen: dict[str, dict] = {}
    scope_set = set(scope)
    for record in records:
        symbol = str(record.get('symbol', '')).strip().upper()
        if not symbol or symbol not in scope_set:
            raise ValueError(f'out-of-scope or missing symbol: {symbol!r}')
        if symbol in seen:
            raise ValueError(f'duplicate nominal record: {symbol}')
        seen[symbol] = record
    missing = sorted(scope_set - set(seen))
    if missing:
        raise ValueError(f'missing nominal records: {len(missing)}; sample={missing[:10]}')
    ordered = [seen[s] for s in scope]
    counts = Counter(str(r.get('status')) for r in ordered)
    review = [r for r in ordered if str(r.get('status')) not in PASS_STATUSES]
    return {
        'scope_n': len(scope),
        'record_n': len(ordered),
        'partition_exact': len(ordered) == len(scope) and len(seen) == len(scope),
        'status_counts': dict(sorted(counts.items())),
        'nominal_resolved_n': len(ordered) - len(review),
        'review_n': len(review),
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'records': ordered,
        'review_records': review,
    }


def read_scope(path: pathlib.Path) -> list[str]:
    symbols = [x.strip().upper() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(symbols) != 847 or len(set(symbols)) != 847:
        raise RuntimeError(f'V4.81 exact scope required; rows={len(symbols)} unique={len(set(symbols))}')
    return symbols


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--scope', required=True)
    p.add_argument('--input-dir', required=True)
    p.add_argument('--out-dir', required=True)
    args = p.parse_args()

    scope = read_scope(pathlib.Path(args.scope))
    input_dir = pathlib.Path(args.input_dir)
    shard_files = sorted(input_dir.rglob('GLOBAL_QFQ_NOMINAL_CROSSCHECK_V481_SHARD_*.json'))
    if len(shard_files) != 16:
        raise RuntimeError(f'expected 16 nominal shard summaries, found {len(shard_files)}')
    all_records: list[dict] = []
    shard_meta = []
    for path in shard_files:
        doc = json.loads(path.read_text(encoding='utf-8'))
        all_records.extend(doc.get('results') or [])
        shard_meta.append({
            'artifact': doc.get('artifact'),
            'shard_index': doc.get('shard_index'),
            'shard_symbol_n': doc.get('shard_symbol_n'),
            'status_counts': doc.get('status_counts'),
            'file': str(path),
        })

    merged = merge_records(scope, all_records)
    merged.update({
        'artifact': 'GLOBAL_QFQ_NOMINAL_CROSSCHECK_V481',
        'version': 'V4.81',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'formal_window': ['2020-06-01', '2026-04-17'],
        'threshold_bp': 5.0,
        'source_factor_census': {
            'run_id': 34009079533,
            'artifact_id': 9981906893,
            'status': 'SINA_FACTOR_PATH_SOURCE_READY_847_OF_847',
        },
        'shards': shard_meta,
        'interpretation': (
            'Nominal EastMoney corporate-action terms are used only to triage the 847 scope against '
            'the corrected Sina factor paths. Nominal PASS is not Formal promotion. Review/unknown '
            'symbols require exact official action evidence or explicit coverage remediation.'
        ),
        'locked_rule': 'No nominal result may emit VALIDATED_GLOBAL_PROVENANCE or unlock Formal OOS.',
    })

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'GLOBAL_QFQ_NOMINAL_CROSSCHECK_V481.json').write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    with (out / 'GLOBAL_QFQ_NOMINAL_REVIEW_QUEUE_V481.csv').open('w', encoding='utf-8', newline='') as f:
        fields = [
            'symbol', 'status', 'formal_rows', 'event_count', 'sina_formal_event_n',
            'sharebonus_coverage', 'rights_coverage', 'max_diff_bp', 'error'
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in merged['review_records']:
            cmp = r.get('factor_validation') or {}
            w.writerow({
                'symbol': r.get('symbol'),
                'status': r.get('status'),
                'formal_rows': r.get('formal_rows'),
                'event_count': r.get('event_count'),
                'sina_formal_event_n': r.get('sina_formal_event_n'),
                'sharebonus_coverage': r.get('sharebonus_coverage'),
                'rights_coverage': r.get('rights_coverage'),
                'max_diff_bp': cmp.get('max_diff_bp'),
                'error': r.get('error'),
            })

    checkpoint = {
        'artifact': 'FORMAL_GATE_CHECKPOINT_V481_NOMINAL',
        'version': 'V4.81',
        'generated_at_utc': merged['generated_at_utc'],
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'price_history': {'status': 'CLOSED_V465'},
        'pit_st': {'status': 'CLOSED_V480'},
        'adjustment_provenance': {
            'sample50': 'CLOSED_V479',
            'sina_source_847': 'CLOSED_SOURCE_COVERAGE_847_OF_847',
            'nominal_triage': 'COMPLETE' if merged['partition_exact'] else 'FAILED',
            'nominal_resolved_n': merged['nominal_resolved_n'],
            'review_n': merged['review_n'],
            'global_847': 'OPEN',
            'validated_global_provenance_emitted': False,
        },
        'liquidity': {'threshold_cny': 80000000, 'status': 'WAITING_FOR_GLOBAL_ADJUSTMENT_PROVENANCE'},
        'locked_rule': 'Formal OOS remains OFF until exact official/global row-level adjustment provenance closes and full-panel downstream audit passes.',
    }
    (out / 'FORMAL_GATE_CHECKPOINT_V481_NOMINAL.json').write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(json.dumps({
        'done': True,
        'scope_n': merged['scope_n'],
        'record_n': merged['record_n'],
        'partition_exact': merged['partition_exact'],
        'status_counts': merged['status_counts'],
        'nominal_resolved_n': merged['nominal_resolved_n'],
        'review_n': merged['review_n'],
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
