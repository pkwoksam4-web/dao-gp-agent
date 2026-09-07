from __future__ import annotations

import argparse
import json
import pathlib

from collect_cninfo_exact_term_indices_v481 import match_announcements_to_events

VERSION = 'V4.82'


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load_raw_query(root: pathlib.Path, raw_file: str) -> dict:
    p = _find_unique(root, pathlib.Path(raw_file).name)
    return json.loads(p.read_text(encoding='utf-8'))


def rematch_unresolved(recovery_dir: pathlib.Path, out_dir: pathlib.Path) -> dict:
    source_path = _find_unique(recovery_dir, 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482.json')
    source = json.loads(source_path.read_text(encoding='utf-8'))
    if source.get('formal_promotion') is not False or source.get('validated_global_provenance_emitted') is not False:
        raise ValueError('source recovery artifact violated non-Formal guard')

    unresolved = []
    for row in source.get('records') or []:
        if row.get('error') is None and row.get('match') is None:
            unresolved.append(dict(row))
    unresolved.sort(key=lambda r: (str(r.get('symbol') or ''), str(r.get('ex_date') or '')))

    out_records = []
    for row in unresolved:
        symbol = str(row.get('symbol') or '').upper()
        ex_date = str(row.get('ex_date') or '')[:10]
        query = row.get('query') or {}
        raw_file = str(query.get('raw_file') or '')
        if not symbol or not ex_date or not raw_file:
            raise ValueError(f'unresolved row missing symbol/ex_date/raw_file: {row!r}')
        payload = _load_raw_query(recovery_dir, raw_file)
        items = payload.get('announcements') or []
        match = match_announcements_to_events([ex_date], items, max_prior_days=45)[ex_date]
        out = dict(row)
        out['symbol'] = symbol
        out['ex_date'] = ex_date
        out['match'] = match
        out['source'] = 'OFFLINE_TITLE_REMATCH_V482'
        out_records.append(out)

    matched = sum(r.get('match') is not None for r in out_records)
    report = {
        'artifact': 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482',
        'version': VERSION,
        'source_artifact': source.get('artifact'),
        'source_target_event_n': int(source.get('target_event_n') or len(source.get('records') or [])),
        'source_matched_event_n': int(source.get('matched_event_n') or 0),
        'source_unresolved_event_n': len(unresolved),
        'target_event_n': len(unresolved),
        'preseeded_match_n': 0,
        'network_target_event_n': 0,
        'matched_event_n': matched,
        'network_matched_event_n': 0,
        'query_error_event_n': 0,
        'unresolved_event_n': len(out_records) - matched,
        'records': out_records,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (out_dir / 'CNINFO_UNRESOLVED_OFFLINE_REMATCH_V482.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps({k: report[k] for k in (
        'source_target_event_n','source_matched_event_n','source_unresolved_event_n',
        'target_event_n','matched_event_n','unresolved_event_n')
    }, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--recovery-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    rematch_unresolved(pathlib.Path(args.recovery_dir), pathlib.Path(args.out_dir))


if __name__ == '__main__':
    main()
