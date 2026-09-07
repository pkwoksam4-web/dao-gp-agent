from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import time

from cninfo_exact_term_v481 import event_query_window, query_cninfo, resolve_orgid
from collect_cninfo_exact_term_indices_v481 import match_announcements_to_events

VERSION = 'V4.82'
EXPECTED_REMAINING_SYMBOL_N = 18
EXPECTED_TARGET_EVENT_N = 98
EXPECTED_PRESEEDED_N = 3
EXPECTED_NETWORK_TARGET_N = 95


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def select_remaining_unmatched_targets(base_index: dict, closure: dict) -> dict[str, list[str]]:
    remaining = {str(s).upper() for s in (closure.get('remaining_symbols') or [])}
    out: dict[str, list[str]] = {}
    for record in base_index.get('records') or []:
        symbol = str(record.get('symbol') or '').upper()
        if symbol not in remaining:
            continue
        dates = [str(d)[:10] for d in (record.get('event_dates') or [])]
        matches = record.get('matches') or {}
        missing = [d for d in dates if not matches.get(d)]
        if missing:
            out[symbol] = sorted(dict.fromkeys(missing))
    return dict(sorted(out.items()))


def remove_preseeded_matches(targets: dict[str, list[str]], probe: dict) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    remaining = {s: list(ds) for s, ds in targets.items()}
    recovered: list[tuple[str, str]] = []
    for row in probe.get('records') or []:
        symbol = str(row.get('symbol') or '').upper()
        ex_date = str(row.get('ex_date') or '')[:10]
        if row.get('error') is not None or row.get('match') is None:
            continue
        if symbol not in remaining or ex_date not in remaining[symbol]:
            continue
        remaining[symbol] = [d for d in remaining[symbol] if d != ex_date]
        recovered.append((symbol, ex_date))
    remaining = {s: ds for s, ds in sorted(remaining.items()) if ds}
    return remaining, sorted(recovered)


def merge_matches(base_index: dict, rows: list[dict]) -> dict:
    out = copy.deepcopy(base_index)
    by_symbol = {str(r.get('symbol') or '').upper(): r for r in (out.get('records') or [])}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        match = row.get('match')
        if match is None:
            continue
        symbol = str(row.get('symbol') or '').upper()
        ex_date = str(row.get('ex_date') or '')[:10]
        key = (symbol, ex_date)
        if key in seen:
            raise ValueError(f'duplicate recovered match {key}')
        seen.add(key)
        if symbol not in by_symbol:
            raise ValueError(f'recovered symbol outside base index: {symbol}')
        record = by_symbol[symbol]
        dates = [str(d)[:10] for d in (record.get('event_dates') or [])]
        if ex_date not in dates:
            raise ValueError(f'recovered event outside base event set: {key}')
        matches = record.setdefault('matches', {})
        if matches.get(ex_date) is not None:
            raise ValueError(f'refuse to overwrite existing CNINFO match: {key}')
        matches[ex_date] = copy.deepcopy(match)
        hist = record.setdefault('v482_low_rate_recovery', {'events': {}})
        hist.setdefault('events', {})[ex_date] = {
            'query': copy.deepcopy(row.get('query')),
            'error': row.get('error'),
            'org_lookup': copy.deepcopy(row.get('org_lookup')),
            'source': row.get('source'),
        }

    for record in out.get('records') or []:
        dates = [str(d)[:10] for d in (record.get('event_dates') or [])]
        matches = record.get('matches') or {}
        missing = [d for d in dates if matches.get(d) is None]
        record['matched_event_n'] = len(dates) - len(missing)
        record['unmatched_event_dates'] = missing
        if not missing:
            record['error'] = None

    total_events = sum(len(r.get('event_dates') or []) for r in (out.get('records') or []))
    matched = sum(int(r.get('matched_event_n') or 0) for r in (out.get('records') or []))
    out['artifact'] = 'CNINFO_STANDARD_EXACT_TERM_INDEX_REMAINING_RECOVERED_V482'
    out['version'] = VERSION
    out['event_date_n'] = total_events
    out['matched_event_n'] = matched
    out['unmatched_event_n'] = total_events - matched
    out['symbols_all_events_matched_n'] = sum(
        int(r.get('matched_event_n') or 0) == len(r.get('event_dates') or []) for r in (out.get('records') or [])
    )
    out['symbols_unresolved_n'] = len(out.get('records') or []) - int(out['symbols_all_events_matched_n'])
    out['formal_promotion'] = False
    out['validated_global_provenance_emitted'] = False
    out['formal_ready'] = False
    out['oos_metrics_allowed'] = False
    return out


def _probe_rows(probe: dict, targets: dict[str, list[str]]) -> list[dict]:
    out = []
    target_keys = {(s, d) for s, dates in targets.items() for d in dates}
    for row in probe.get('records') or []:
        symbol = str(row.get('symbol') or '').upper()
        ex_date = str(row.get('ex_date') or '')[:10]
        if (symbol, ex_date) not in target_keys or row.get('match') is None or row.get('error') is not None:
            continue
        copied = copy.deepcopy(row)
        copied['source'] = 'LOW_RATE_PROBE_PRESEED'
        out.append(copied)
    return out


def collect_network_targets(
    targets: dict[str, list[str]],
    raw_dir: pathlib.Path,
    timeout: int = 45,
    attempts: int = 8,
    sleep_between: float = 2.0,
) -> list[dict]:
    rows: list[dict] = []
    event_counter = 0
    total_events = sum(len(ds) for ds in targets.values())
    for symbol, dates in sorted(targets.items()):
        code = symbol.split('.')[0]
        try:
            org = resolve_orgid(code)
            orgid = org['orgid']
            raw = org['raw']
            org_file = f'{code}_low_rate_orgid.json'
            (raw_dir / org_file).write_bytes(raw)
            org_meta = {
                'orgid': orgid,
                'http_status': org.get('http_status'),
                'attempts': org.get('attempts'),
                'raw_file': org_file,
                'sha256': hashlib.sha256(raw).hexdigest(),
            }
        except Exception as exc:
            err = f'{type(exc).__name__}: {exc}'
            for ex_date in dates:
                event_counter += 1
                rows.append({
                    'symbol': symbol, 'ex_date': ex_date, 'org_lookup': None,
                    'query': None, 'match': None, 'error': err, 'source': 'LOW_RATE_NETWORK',
                })
                print(json.dumps({'event_progress': event_counter, 'event_total': total_events, 'symbol': symbol, 'ex_date': ex_date, 'status': 'ORG_LOOKUP_ERROR'}, ensure_ascii=False), flush=True)
            if sleep_between:
                time.sleep(float(sleep_between))
            continue

        for ex_date in dates:
            event_counter += 1
            start, end = event_query_window(ex_date, 45, 2)
            row = {
                'symbol': symbol, 'ex_date': ex_date, 'org_lookup': org_meta,
                'query': None, 'match': None, 'error': None, 'source': 'LOW_RATE_NETWORK',
            }
            try:
                q = query_cninfo(code, start, end, orgid=orgid, searchkey='实施公告', timeout=timeout, attempts=attempts)
                raw = q['raw']
                raw_file = f'{code}_{ex_date}_low_rate_implementation.json'
                (raw_dir / raw_file).write_bytes(raw)
                items = (q.get('json') or {}).get('announcements') or []
                row['query'] = {
                    'http_status': q.get('http_status'),
                    'content_type': q.get('content_type'),
                    'attempts': q.get('attempts'),
                    'announcement_n': len(items),
                    'searchkey': q.get('searchkey'),
                    'date_window': q.get('date_window'),
                    'raw_file': raw_file,
                    'sha256': hashlib.sha256(raw).hexdigest(),
                    'bytes': len(raw),
                }
                row['match'] = match_announcements_to_events([ex_date], items, max_prior_days=45)[ex_date]
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
            rows.append(row)
            print(json.dumps({
                'event_progress': event_counter,
                'event_total': total_events,
                'symbol': symbol,
                'ex_date': ex_date,
                'matched': row['match'] is not None,
                'error': row['error'],
                'announcement_n': (row['query'] or {}).get('announcement_n'),
            }, ensure_ascii=False), flush=True)
            if sleep_between and event_counter < total_events:
                time.sleep(float(sleep_between))
    return rows


def run_recovery(
    base_index_dir: pathlib.Path,
    closure_dir: pathlib.Path,
    probe_dir: pathlib.Path,
    out_dir: pathlib.Path,
    timeout: int = 45,
    attempts: int = 8,
    sleep_between: float = 2.0,
) -> dict:
    base = _load(_find_unique(base_index_dir, 'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json'))
    closure = _load(_find_unique(closure_dir, 'REPARSED_REMAINING_CLOSURE_V482.json'))
    probe = _load(_find_unique(probe_dir, 'CNINFO_LOW_RATE_PROBE_V482.json'))

    remaining_symbols = closure.get('remaining_symbols') or []
    if len(remaining_symbols) != EXPECTED_REMAINING_SYMBOL_N:
        raise ValueError(f'expected {EXPECTED_REMAINING_SYMBOL_N} remaining symbols; got {len(remaining_symbols)}')
    targets = select_remaining_unmatched_targets(base, closure)
    target_n = sum(len(ds) for ds in targets.values())
    if target_n != EXPECTED_TARGET_EVENT_N:
        raise ValueError(f'expected {EXPECTED_TARGET_EVENT_N} unmatched remaining events; got {target_n}')

    network_targets, recovered_keys = remove_preseeded_matches(targets, probe)
    if len(recovered_keys) != EXPECTED_PRESEEDED_N:
        raise ValueError(f'expected {EXPECTED_PRESEEDED_N} probe-preseed matches; got {len(recovered_keys)}')
    network_target_n = sum(len(ds) for ds in network_targets.values())
    if network_target_n != EXPECTED_NETWORK_TARGET_N:
        raise ValueError(f'expected {EXPECTED_NETWORK_TARGET_N} network targets; got {network_target_n}')

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    preseed_rows = _probe_rows(probe, targets)
    network_rows = collect_network_targets(network_targets, raw_dir, timeout, attempts, sleep_between)
    rows = preseed_rows + network_rows
    if len(rows) != EXPECTED_TARGET_EVENT_N:
        raise ValueError(f'expected {EXPECTED_TARGET_EVENT_N} recovery rows; got {len(rows)}')

    merged = merge_matches(base, rows)
    matched = sum(r.get('match') is not None for r in rows)
    errors = sum(r.get('error') is not None for r in rows)
    unresolved = len(rows) - matched
    report = {
        'artifact': 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482',
        'version': VERSION,
        'remaining_symbol_n': EXPECTED_REMAINING_SYMBOL_N,
        'target_event_n': EXPECTED_TARGET_EVENT_N,
        'preseeded_match_n': len(preseed_rows),
        'network_target_event_n': EXPECTED_NETWORK_TARGET_N,
        'matched_event_n': matched,
        'query_error_event_n': errors,
        'unresolved_event_n': unresolved,
        'network_matched_event_n': sum(r.get('match') is not None for r in network_rows),
        'network_query_error_event_n': sum(r.get('error') is not None for r in network_rows),
        'records': rows,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }
    (out_dir / 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (out_dir / 'CNINFO_STANDARD_EXACT_TERM_INDEX_REMAINING_RECOVERED_V482.json').write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in (
        'remaining_symbol_n','target_event_n','preseeded_match_n','network_target_event_n',
        'matched_event_n','network_matched_event_n','query_error_event_n','unresolved_event_n')
    }, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-index-dir', required=True)
    ap.add_argument('--closure-dir', required=True)
    ap.add_argument('--probe-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--timeout', type=int, default=45)
    ap.add_argument('--attempts', type=int, default=8)
    ap.add_argument('--sleep-between', type=float, default=2.0)
    args = ap.parse_args()
    run_recovery(
        pathlib.Path(args.base_index_dir), pathlib.Path(args.closure_dir), pathlib.Path(args.probe_dir),
        pathlib.Path(args.out_dir), args.timeout, args.attempts, args.sleep_between,
    )


if __name__ == '__main__':
    main()
