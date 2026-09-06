from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from global_qfq_nominal_v481 import (
    classify_nominal_symbol,
    eastmoney_report_coverage,
    sina_formal_event_dates,
)
from global_qfq_source_v481 import shard_symbols
from sample50_probe import report_url, sohu_history_url
from sample50_validate import (
    compare_factor_path,
    event_ratio,
    expected_factor_for_date,
    merge_actions,
    normalize_rights_rows,
    normalize_sharebonus_rows,
    parse_eastmoney_report,
    parse_sina_qfq,
    parse_sohu_history_bytes,
    prev_close_before,
    sina_normalized_for_date,
)

FORMAL_BEG = '2020-06-01'
FORMAL_END = '2026-04-17'
THRESHOLD_BP = 5.0
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_scope(path: pathlib.Path) -> list[str]:
    symbols = [x.strip().upper() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(symbols) != 847 or len(set(symbols)) != 847:
        raise RuntimeError(f'V4.81 requires exact 847-symbol scope; rows={len(symbols)} unique={len(set(symbols))}')
    return symbols


def fetch_bytes(url: str, referer: str, attempts: int = 3) -> tuple[bytes, dict]:
    last = {'ok': False, 'status': None, 'content_type': None, 'bytes': 0, 'sha256': sha256(b''), 'attempts': 0, 'error': None, 'url': url}
    for attempt in range(1, attempts + 1):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Referer': referer})
            with urlopen(req, timeout=30) as r:
                body = r.read()
                return body, {
                    'ok': True,
                    'status': getattr(r, 'status', 200),
                    'content_type': r.headers.get('Content-Type'),
                    'bytes': len(body),
                    'sha256': sha256(body),
                    'attempts': attempt,
                    'error': None,
                    'url': url,
                }
        except HTTPError as e:
            try:
                body = e.read()
            except Exception:
                body = b''
            last = {
                'ok': False,
                'status': e.code,
                'content_type': e.headers.get('Content-Type') if e.headers else None,
                'bytes': len(body),
                'sha256': sha256(body),
                'attempts': attempt,
                'error': f'HTTPError: {e}',
                'url': url,
            }
            if 400 <= e.code < 500 and e.code != 429:
                return body, last
        except Exception as e:
            last = {
                'ok': False,
                'status': None,
                'content_type': None,
                'bytes': 0,
                'sha256': sha256(b''),
                'attempts': attempt,
                'error': f'{type(e).__name__}: {e}',
                'url': url,
            }
        if attempt < attempts:
            time.sleep(0.7 * attempt)
    return b'', last


def fetch_report(symbol: str, report_name: str, raw_dir: pathlib.Path) -> tuple[list[dict], str, list[dict]]:
    rows: list[dict] = []
    metas: list[dict] = []
    page = 1
    max_pages = 1
    final_coverage = 'EXPLICIT_SUCCESS'
    while page <= max_pages:
        url = report_url(symbol, report_name, page_number=page)
        body, meta = fetch_bytes(url, 'https://data.eastmoney.com/')
        raw_name = f'{symbol.replace(".", "_")}_{report_name}_p{page}.json'
        (raw_dir / raw_name).write_bytes(body)
        coverage = eastmoney_report_coverage(body) if meta['ok'] else 'FAILED'
        meta.update({'report': report_name, 'page': page, 'coverage': coverage, 'raw_file': 'raw/' + raw_name})
        metas.append(meta)
        if coverage == 'FAILED':
            return rows, 'FAILED', metas
        if coverage == 'EMPTY_UNPROVEN':
            return rows, 'EMPTY_UNPROVEN', metas
        try:
            page_rows, pages = parse_eastmoney_report(body)
        except Exception as e:
            metas[-1]['parse_error'] = f'{type(e).__name__}: {e}'
            return rows, 'FAILED', metas
        rows.extend(page_rows)
        max_pages = max(1, int(pages or 1))
        if max_pages > 20:
            metas[-1]['parse_error'] = f'unreasonable pages={max_pages}'
            return rows, 'FAILED', metas
        page += 1
    return rows, final_coverage, metas


def one(symbol: str, source_census: pathlib.Path, out_root: pathlib.Path) -> dict:
    raw_dir = out_root / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    rec = {
        'symbol': symbol,
        'status': None,
        'formal_rows': 0,
        'event_count': 0,
        'sina_formal_event_n': 0,
        'sina_formal_event_dates': [],
        'factor_validation': None,
        'sharebonus_coverage': None,
        'rights_coverage': None,
        'events': [],
        'source_meta': {},
        'error': None,
        'formal_promotion': False,
    }
    try:
        sina_path = source_census / 'raw' / (symbol.replace('.', '_') + '_sina_qfq.js')
        if not sina_path.exists():
            raise FileNotFoundError(f'missing corrected Sina raw: {sina_path}')
        sina_raw = sina_path.read_bytes()
        factors = parse_sina_qfq(sina_raw)
        sina_dates = sina_formal_event_dates(factors, FORMAL_BEG, FORMAL_END)
        rec['sina_formal_event_dates'] = sina_dates
        rec['sina_formal_event_n'] = len(sina_dates)
        rec['source_meta']['sina'] = {
            'source': 'corrected V4.81 census run 34009079533',
            'raw_file': str(sina_path),
            'bytes': len(sina_raw),
            'sha256': sha256(sina_raw),
        }

        sb_rows, sb_cov, sb_meta = fetch_report(symbol, 'RPT_SHAREBONUS_DET', raw_dir)
        rr_rows, rr_cov, rr_meta = fetch_report(symbol, 'RPT_IPO_ALLOTMENT', raw_dir)
        rec['sharebonus_coverage'] = sb_cov
        rec['rights_coverage'] = rr_cov
        rec['source_meta']['sharebonus'] = sb_meta
        rec['source_meta']['rights'] = rr_meta

        sohu_url = sohu_history_url(symbol)
        sohu_raw, sohu_meta = fetch_bytes(sohu_url, 'https://q.stock.sohu.com/')
        sohu_name = symbol.replace('.', '_') + '_sohu_raw_history.js'
        (raw_dir / sohu_name).write_bytes(sohu_raw)
        sohu_meta['raw_file'] = 'raw/' + sohu_name
        rec['source_meta']['sohu'] = sohu_meta
        if not sohu_meta['ok']:
            rec['status'] = 'BLOCKED_RAW_SOURCE'
            rec['error'] = sohu_meta['error']
            return rec

        try:
            raw_rows = parse_sohu_history_bytes(sohu_raw)
        except Exception as e:
            rec['status'] = 'BLOCKED_RAW_PARSE'
            rec['error'] = f'{type(e).__name__}: {e}'
            return rec
        if len({r['date'] for r in raw_rows}) != len(raw_rows):
            rec['status'] = 'BLOCKED_RAW_DUPLICATE_DATES'
            rec['error'] = 'duplicate Sohu dates'
            return rec
        formal_rows = [r for r in raw_rows if FORMAL_BEG <= r['date'] <= FORMAL_END]
        rec['formal_rows'] = len(formal_rows)
        if not formal_rows:
            rec['status'] = classify_nominal_symbol(
                formal_row_n=0,
                event_count=0,
                factor_compare_status=None,
                sharebonus_coverage=sb_cov,
                rights_coverage=rr_cov,
                sina_formal_event_n=len(sina_dates),
            )
            return rec

        try:
            actions = merge_actions(
                normalize_sharebonus_rows(symbol, sb_rows)
                + normalize_rights_rows(symbol, rr_rows)
            )
            actions = [a for a in actions if FORMAL_BEG < a.ex_date <= FORMAL_END]
        except Exception as e:
            rec['status'] = 'REVIEW_REQUIRED_EVENT_PARSE'
            rec['error'] = f'{type(e).__name__}: {e}'
            return rec

        rec['event_count'] = len(actions)
        factor_status = None
        if actions:
            try:
                ratios = {}
                for a in actions:
                    p = prev_close_before(raw_rows, a.ex_date)
                    ratios[a.ex_date] = event_ratio(a, p)
                    rec['events'].append({
                        'ex_date': a.ex_date,
                        'cash_per_share_nominal': a.cash_per_share,
                        'stock_ratio': a.stock_ratio,
                        'capitalization_ratio': a.cap_ratio,
                        'rights_ratio': a.rights_ratio,
                        'rights_price': a.rights_price,
                        'prev_actual_close': p,
                        'event_ratio': ratios[a.ex_date],
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
                rec['status'] = 'REVIEW_REQUIRED_FACTOR_COMPARISON'
                rec['error'] = f'{type(e).__name__}: {e}'
                return rec
        else:
            # For a proven no-action window the normalized expected path is 1.0.
            # The classifier still requires explicit coverage from both event-source families.
            factor_status = 'PASS' if not sina_dates else None

        rec['status'] = classify_nominal_symbol(
            formal_row_n=len(formal_rows),
            event_count=len(actions),
            factor_compare_status=factor_status,
            sharebonus_coverage=sb_cov,
            rights_coverage=rr_cov,
            sina_formal_event_n=len(sina_dates),
        )
        return rec
    except Exception as e:
        rec['status'] = 'INTERNAL_ERROR_FAIL_CLOSED'
        rec['error'] = f'{type(e).__name__}: {e}'
        return rec


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--scope', required=True)
    p.add_argument('--source-census', required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--shard-index', required=True, type=int)
    p.add_argument('--shard-count', required=True, type=int)
    p.add_argument('--workers', type=int, default=4)
    args = p.parse_args()

    scope = read_scope(pathlib.Path(args.scope))
    selected = shard_symbols(scope, args.shard_index, args.shard_count)
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    source_census = pathlib.Path(args.source_census)

    results: list[dict | None] = [None] * len(selected)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = {ex.submit(one, symbol, source_census, out): i for i, symbol in enumerate(selected)}
        for f in as_completed(futures):
            i = futures[f]
            try:
                results[i] = f.result()
            except Exception as e:
                results[i] = {
                    'symbol': selected[i],
                    'status': 'INTERNAL_ERROR_FAIL_CLOSED',
                    'error': repr(e),
                    'formal_promotion': False,
                }
            done = sum(x is not None for x in results)
            if done % 10 == 0 or done == len(selected):
                r = results[i]
                print(json.dumps({'shard': args.shard_index, 'progress': done, 'total': len(selected), 'last': r['symbol'], 'status': r['status']}, ensure_ascii=False), flush=True)

    final_results = [r for r in results if r is not None]
    counts = Counter(r['status'] for r in final_results)
    report = {
        'artifact': f'GLOBAL_QFQ_NOMINAL_CROSSCHECK_V481_SHARD_{args.shard_index}',
        'version': 'V4.81',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'formal_window': [FORMAL_BEG, FORMAL_END],
        'threshold_bp': THRESHOLD_BP,
        'scope_n': len(scope),
        'shard_index': args.shard_index,
        'shard_count': args.shard_count,
        'shard_symbol_n': len(selected),
        'status_counts': dict(sorted(counts.items())),
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'rule': 'Nominal event terms are triage only. Empty/unproven event coverage never proves factor=1; nominal PASS does not emit VALIDATED_GLOBAL_PROVENANCE.',
        'results': final_results,
    }
    (out / f'GLOBAL_QFQ_NOMINAL_CROSSCHECK_V481_SHARD_{args.shard_index}.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps({'done': True, 'shard': args.shard_index, 'symbols': len(final_results), 'status_counts': report['status_counts']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
