from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

EXPERIMENT_ID = 'BTC-FLOW-SUCCESSOR-20261009-B'
RELEASE_ZIP_SHA256 = 'b6f952c783009b7642720e06d8f5f1781e080497f91b98521aea545cbcb2d86d'
ENDPOINT = 'https://www.okx.com/api/v5/market/history-candles'
INST_ID = 'BTC-USDT-SWAP'
BAR = '5m'
LIMIT = 100
STEP_MS = 300_000
START_MS = 1786218900000
END_EXCLUSIVE_MS = 1786650900000
EXPECTED_ROWS = 1440
MAX_BODY = 8 * 1024 * 1024
MAX_PAGES = 20
USER_AGENT = 'BTCQ-Successor-B-OKX-gap-capture/1'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _url(params: dict) -> str:
    return ENDPOINT + '?' + urllib.parse.urlencode(params)


def https_get(endpoint: str, params: dict) -> tuple[bytes, dict]:
    url = endpoint + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT}, method='GET')
    started = _now()
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = int(resp.status)
        if status != 200:
            raise RuntimeError(f'HTTP_STATUS_{status}')
        body = resp.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise RuntimeError('RESPONSE_TOO_LARGE')
        return body, {
            'request_url': url,
            'http_status': status,
            'started_at_utc': started,
            'retrieved_at_utc': _now(),
            'content_type': resp.headers.get('Content-Type'),
            'content_length': resp.headers.get('Content-Length'),
            'response_size_bytes': len(body),
            'response_sha256': hashlib.sha256(body).hexdigest(),
            'ca_verification_enabled': True,
        }


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')


def capture_all(root: Path, *, fetcher=https_get) -> dict:
    root = Path(root)
    page_dir = root / 'pages'
    page_dir.mkdir(parents=True, exist_ok=True)
    reasons: list[str] = []
    all_rows: list[list[str]] = []
    cursor = END_EXCLUSIVE_MS
    pages = 0
    source_start_reached = False

    for page_index in range(MAX_PAGES):
        params = {'instId': INST_ID, 'bar': BAR, 'after': str(cursor), 'limit': LIMIT}
        request_url = _url(params)
        try:
            body, transport = fetcher(ENDPOINT, dict(params))
        except Exception as exc:
            _write_json(page_dir / f'transport_error_{page_index:03d}.meta.json', {
                'request_url': request_url,
                'request_params': params,
                'error_type': type(exc).__name__,
                'error': str(exc),
                'retrieved_at_utc': _now(),
            })
            reasons.append('OKX_TRANSPORT_ERROR')
            break

        raw_path = page_dir / f'page_{page_index:03d}.json'
        raw_path.write_bytes(body)
        meta = {
            'request_url': request_url,
            'request_params': params,
            'raw_body_sha256': hashlib.sha256(body).hexdigest(),
            'transport': transport,
        }
        pages += 1

        try:
            payload = json.loads(body.decode('utf-8'))
        except Exception as exc:
            meta['parse_error'] = f'{type(exc).__name__}: {exc}'
            _write_json(page_dir / f'page_{page_index:03d}.meta.json', meta)
            reasons.append('OKX_JSON_INVALID')
            break

        code = str(payload.get('code', ''))
        rows = payload.get('data')
        meta['api_code'] = code
        meta['api_msg'] = str(payload.get('msg', ''))
        if code != '0':
            meta['row_count'] = len(rows) if isinstance(rows, list) else None
            _write_json(page_dir / f'page_{page_index:03d}.meta.json', meta)
            reasons.append('OKX_API_CODE_NONZERO')
            break
        if not isinstance(rows, list):
            _write_json(page_dir / f'page_{page_index:03d}.meta.json', meta)
            reasons.append('OKX_DATA_NOT_LIST')
            break
        if not rows:
            meta['row_count'] = 0
            _write_json(page_dir / f'page_{page_index:03d}.meta.json', meta)
            break

        page_ts = []
        malformed = False
        for row in rows:
            if not isinstance(row, list) or len(row) < 9:
                malformed = True
                break
            try:
                page_ts.append(int(row[0]))
            except Exception:
                malformed = True
                break
        if malformed:
            meta['row_count'] = len(rows)
            _write_json(page_dir / f'page_{page_index:03d}.meta.json', meta)
            reasons.append('OKX_ROW_SHAPE_INVALID')
            break
        if any(b >= a for a, b in zip(page_ts, page_ts[1:])):
            reasons.append('OKX_PAGE_ORDER_INVALID')

        meta.update({
            'row_count': len(rows),
            'first_timestamp_ms': page_ts[0],
            'last_timestamp_ms': page_ts[-1],
            'all_closed': all(str(r[8]) == '1' for r in rows),
        })
        _write_json(page_dir / f'page_{page_index:03d}.meta.json', meta)
        all_rows.extend(rows)

        oldest = min(page_ts)
        if oldest <= START_MS:
            source_start_reached = True
            break
        if oldest >= cursor:
            reasons.append('OKX_PAGINATION_NO_PROGRESS')
            break
        cursor = oldest
    else:
        reasons.append('OKX_MAX_PAGES_EXCEEDED')

    parsed = []
    malformed_total = 0
    for row in all_rows:
        try:
            parsed.append((int(row[0]), row))
        except Exception:
            malformed_total += 1
    if malformed_total:
        reasons.append('OKX_TIMESTAMP_INVALID')

    in_window = [(ts, row) for ts, row in parsed if START_MS <= ts < END_EXCLUSIVE_MS]
    timestamps = [ts for ts, _ in in_window]
    unique_ts = set(timestamps)
    duplicate_count = len(timestamps) - len(unique_ts)
    expected = set(range(START_MS, END_EXCLUSIVE_MS, STEP_MS))
    missing = expected - unique_ts
    extra = unique_ts - expected
    all_closed = all(str(row[8]) == '1' for _, row in in_window) if in_window else False

    if duplicate_count:
        reasons.append('GRID_DUPLICATE_TIMESTAMPS')
    if missing:
        reasons.append('GRID_MISSING_SLOTS')
    if extra:
        reasons.append('GRID_EXTRA_SLOTS')
    if len(in_window) != EXPECTED_ROWS:
        reasons.append('GRID_ROW_COUNT_MISMATCH')
    if not all_closed:
        reasons.append('OKX_UNCLOSED_BAR_PRESENT')
    if not source_start_reached:
        reasons.append('OKX_SOURCE_START_NOT_REACHED')

    canonical = sorted(in_window, key=lambda x: x[0])
    if canonical:
        with gzip.open(root / 'okx_btc_usdt_swap_5m_gap.csv.gz', 'wt', newline='', encoding='utf-8') as gz:
            w = csv.writer(gz)
            w.writerow(['timestamp_ms','open','high','low','close','vol','volCcy','volCcyQuote','confirm'])
            for _, row in canonical:
                w.writerow(row[:9])

    pass_gate = (
        not reasons and source_start_reached and len(in_window) == EXPECTED_ROWS and
        duplicate_count == 0 and not missing and not extra and all_closed
    )
    report = {
        'schema_version': 1,
        'experiment_id': EXPERIMENT_ID,
        'release_zip_sha256': RELEASE_ZIP_SHA256,
        'source': 'OKX official /api/v5/market/history-candles',
        'purpose': 'Successor-B missing OKX prefix only; merge with independently verified Successor-A OKX artifact.',
        'instrument': INST_ID,
        'bar': BAR,
        'start_ms': START_MS,
        'end_exclusive_ms': END_EXCLUSIVE_MS,
        'expected_rows': EXPECTED_ROWS,
        'pages_captured': pages,
        'raw_rows_captured': len(all_rows),
        'rows_in_window': len(in_window),
        'unique_timestamps_in_window': len(unique_ts),
        'duplicate_timestamps': duplicate_count,
        'missing_slots': len(missing),
        'extra_slots': len(extra),
        'all_closed': all_closed,
        'source_start_reached': source_start_reached,
        'pass': pass_gate,
        'status': 'OKX_B_GAP_COVERAGE_PROVEN' if pass_gate else 'OKX_B_GAP_COVERAGE_BLOCKED',
        'reasons': sorted(set(reasons)),
        'okx_b_gap_coverage_proven': pass_gate,
        'dataset_coverage_proven': False,
        'flow_alpha_allowed': False,
        'mainnet_authorized': False,
        'order_capability_created': False,
    }
    _write_json(root / 'OKX_B_GAP_CAPTURE_REPORT.json', report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description='BTC Successor-B fixed OKX missing-prefix capture')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    report = capture_all(Path(args.out))
    print(json.dumps({k: report[k] for k in ('status','pass','pages_captured','rows_in_window','missing_slots','duplicate_timestamps','flow_alpha_allowed')}, indent=2, sort_keys=True))
    return 0 if report['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
