from __future__ import annotations

import argparse
import copy
from collections import Counter
import json
import pathlib

VERSION = 'V4.81'
INDEX_NAMES = (
    'CNINFO_STANDARD_EXACT_TERM_INDEX_UNION_V481.json',
    'CNINFO_STANDARD_EXACT_TERM_INDEX_SUPPLEMENTED_V481.json',
    'CNINFO_STANDARD_EXACT_TERM_INDEX_MERGED_V481.json',
    'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json',
)


def _announcement_identity(x: dict) -> str:
    key = str(x.get('announcementId') or x.get('adjunctUrl') or '').strip()
    if not key:
        raise ValueError('positive CNINFO announcement missing identity')
    return key


def _records_by_symbol(report: dict, expected_scope_n: int) -> dict[str, dict]:
    records = report.get('records') or []
    by = {str(r.get('symbol') or ''): r for r in records}
    if len(records) != expected_scope_n or len(by) != expected_scope_n or '' in by:
        raise ValueError(f'evidence source must contain exact {expected_scope_n} unique symbols')
    return by


def merge_cninfo_evidence_sources(sources: list[tuple[str, dict]], expected_scope_n: int = 87) -> dict:
    if not sources:
        raise ValueError('at least one evidence source is required')
    names = [str(n) for n, _ in sources]
    if len(set(names)) != len(names):
        raise ValueError('duplicate evidence source name')

    source_maps = [(name, _records_by_symbol(rep, expected_scope_n)) for name, rep in sources]
    symbols = sorted(source_maps[0][1])
    for name, by in source_maps[1:]:
        if sorted(by) != symbols:
            raise ValueError(f'symbol scope mismatch in source {name}')

    records = []
    conflict_event_n = 0
    positive_source_counts = Counter()
    for symbol in symbols:
        event_dates = [str(d)[:10] for d in (source_maps[0][1][symbol].get('event_dates') or [])]
        if not event_dates or len(event_dates) != len(set(event_dates)):
            raise ValueError(f'invalid event date set for {symbol}')
        for name, by in source_maps[1:]:
            other = [str(d)[:10] for d in (by[symbol].get('event_dates') or [])]
            if other != event_dates:
                raise ValueError(f'event date mismatch for {symbol} in source {name}')

        matches = {}
        evidence_sources = {}
        for d in event_dates:
            positives = []
            for name, by in source_maps:
                v = (by[symbol].get('matches') or {}).get(d)
                if v is not None:
                    positives.append((name, v))
            if not positives:
                matches[d] = None
                evidence_sources[d] = []
                continue
            identities = {_announcement_identity(v) for _, v in positives}
            if len(identities) != 1:
                conflict_event_n += 1
                raise ValueError(f'conflicting positive CNINFO evidence for {(symbol, d)}: {sorted(identities)}')
            chosen_name, chosen = positives[0]
            matches[d] = copy.deepcopy(chosen)
            evidence_sources[d] = [name for name, _ in positives]
            positive_source_counts[chosen_name] += 1

        missing = [d for d in event_dates if matches[d] is None]
        records.append({
            'symbol': symbol,
            'event_dates': event_dates,
            'matches': matches,
            'matched_event_n': len(event_dates) - len(missing),
            'unmatched_event_dates': missing,
            'evidence_sources': evidence_sources,
            'error': None,
        })

    event_n = sum(len(r['event_dates']) for r in records)
    matched_n = sum(r['matched_event_n'] for r in records)
    all_matched_n = sum(r['matched_event_n'] == len(r['event_dates']) for r in records)
    unresolved_symbol_n = len(records) - all_matched_n
    return {
        'artifact': 'CNINFO_STANDARD_EXACT_TERM_INDEX_UNION_V481',
        'version': VERSION,
        'source_names': names,
        'scope_symbol_n': len(records),
        'event_date_n': event_n,
        'matched_event_n': matched_n,
        'unmatched_event_n': event_n - matched_n,
        'symbols_all_events_matched_n': all_matched_n,
        'symbols_unresolved_n': unresolved_symbol_n,
        'conflict_event_n': conflict_event_n,
        'selected_positive_source_counts': dict(positive_source_counts),
        'status_counts': dict(Counter(
            'ALL_MATCHED' if r['matched_event_n'] == len(r['event_dates']) else 'PARTIAL_MATCH'
            for r in records
        )),
        'records': records,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }


def _find_index_file(root: pathlib.Path) -> pathlib.Path:
    for name in INDEX_NAMES:
        hits = [p for p in root.rglob(name) if p.is_file()]
        if len(hits) == 1:
            return hits[0]
    raise FileNotFoundError(f'cannot locate unique CNINFO index under {root}')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', action='append', required=True,
                    help='NAME=DIR, repeat in preferred positive-evidence precedence order')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--expected-scope-n', type=int, default=87)
    args = ap.parse_args()

    sources = []
    for spec in args.source:
        if '=' not in spec:
            raise ValueError(f'invalid --source {spec!r}; expected NAME=DIR')
        name, directory = spec.split('=', 1)
        root = pathlib.Path(directory)
        report = json.loads(_find_index_file(root).read_text(encoding='utf-8'))
        sources.append((name, report))

    merged = merge_cninfo_evidence_sources(sources, args.expected_scope_n)
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(merged, ensure_ascii=False, indent=2)
    (out / 'CNINFO_STANDARD_EXACT_TERM_INDEX_UNION_V481.json').write_text(text, encoding='utf-8')
    # Compatibility alias lets the existing narrow supplement collector consume the union directly.
    (out / 'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json').write_text(text, encoding='utf-8')
    print(json.dumps({k: merged[k] for k in (
        'scope_symbol_n', 'event_date_n', 'matched_event_n', 'unmatched_event_n',
        'symbols_all_events_matched_n', 'symbols_unresolved_n', 'conflict_event_n',
        'selected_positive_source_counts', 'status_counts')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
