from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import time
import urllib.parse
import urllib.request


SOHU_URL = 'https://q.stock.sohu.com/hisHq'
SINA_URL = 'https://finance.sina.com.cn/realstock/company/{sina_symbol}/qfq.js'


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if '.' not in value:
        raise ValueError(f'exchange-qualified symbol required: {symbol!r}')
    code, exchange = value.split('.', 1)
    if len(code) != 6 or not code.isdigit() or exchange not in {'SZ', 'SH'}:
        raise ValueError(f'unsupported symbol: {symbol!r}')
    return f'{code}.{exchange}'


def _decode(raw: bytes) -> str:
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError('Sohu payload decode failed')


def parse_sohu_hishq_bytes(symbol: str, raw: bytes) -> list[dict]:
    symbol = normalize_symbol(symbol)
    text = _decode(raw).strip()
    match = re.match(r'^\s*historySearchHandler\((.*)\)\s*;?\s*$', text, re.S)
    if not match:
        raise ValueError('Sohu JSONP wrapper mismatch')
    payload = json.loads(match.group(1))
    if not isinstance(payload, list) or not payload:
        raise ValueError('Sohu payload missing list')
    block = payload[0]
    if not isinstance(block, dict) or int(block.get('status', -1)) != 0:
        raise ValueError('Sohu status/data invalid')
    rows = []
    for index, parts in enumerate(block.get('hq') or []):
        if not isinstance(parts, list) or len(parts) < 10:
            raise ValueError(f'Sohu row {index} has too few fields')
        date = str(parts[0])[:10]
        try:
            open_, close, low, high = map(float, (parts[1], parts[2], parts[5], parts[6]))
            volume_lots = float(parts[7])
            amount_10k = float(parts[8])
            turnover_pct = float(str(parts[9]).rstrip('%'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Sohu row {index} has invalid numeric fields') from exc
        if (not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) or
                not all(math.isfinite(x) for x in (open_, close, low, high,
                                                     volume_lots, amount_10k,
                                                     turnover_pct)) or
                min(open_, close, low, high) <= 0 or volume_lots < 0 or amount_10k < 0):
            raise ValueError(f'Sohu row {index} is invalid')
        rows.append({
            'symbol': symbol,
            'date': date,
            'raw_open': open_,
            'raw_close': close,
            'raw_low': low,
            'raw_high': high,
            'volume_shares': volume_lots * 100.0,
            'amount_cny': amount_10k * 10_000.0,
            'turnover_ratio': turnover_pct / 100.0,
            'source_id': 'sohu:hishq:raw',
        })
    rows.sort(key=lambda row: row['date'])
    dates = [row['date'] for row in rows]
    if len(dates) != len(set(dates)):
        raise ValueError('Sohu history contains duplicate dates')
    return rows


def parse_sina_qfq_js(symbol: str, raw: bytes) -> list[dict]:
    symbol = normalize_symbol(symbol)
    text = raw.decode('utf-8-sig', errors='strict')
    match = re.search(r'=\s*(\{.*\})\s*;?\s*(?:/\*.*)?$', text, re.S)
    if not match:
        raise ValueError('Sina qfq object not found')
    obj = json.loads(match.group(1))
    if not isinstance(obj.get('data'), list) or not obj['data']:
        raise ValueError('Sina qfq data is empty')
    rows = []
    for index, raw_row in enumerate(obj['data']):
        if not isinstance(raw_row, dict):
            raise ValueError(f'Sina factor row {index} is not an object')
        date = str(raw_row.get('d') or '')[:10]
        try:
            factor = float(raw_row.get('f'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Sina factor row {index} is invalid') from exc
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) or not math.isfinite(factor) or factor <= 0:
            raise ValueError(f'Sina factor row {index} is invalid')
        rows.append({'date': date, 'factor': factor, 'source_id': f'sina:qfq:{symbol}'})
    rows.sort(key=lambda row: row['date'])
    dates = [row['date'] for row in rows]
    if len(dates) != len(set(dates)):
        raise ValueError('Sina qfq contains duplicate dates')
    return rows


def factor_for_date(factors: list[dict], date: str) -> float:
    target = dt.date.fromisoformat(date)
    value = None
    for row in factors:
        if dt.date.fromisoformat(row['date']) <= target:
            value = float(row['factor'])
        else:
            break
    if value is None:
        raise ValueError(f'no Sina factor covering {date}')
    return value


def sina_normalized_for_date(factors: list[dict], date: str, anchor: str) -> float:
    anchor_date = dt.date.fromisoformat(anchor)
    if not factors or anchor_date > dt.date.fromisoformat(factors[-1]['date']):
        raise ValueError('anchor is later than the available Sina factor path')
    return factor_for_date(factors, anchor) / factor_for_date(factors, date)


def materialize_qfq_rows(raw_rows: list[dict], factors: list[dict], *, anchor: str) -> list[dict]:
    out = []
    for row in raw_rows:
        if row['date'] > anchor:
            raise ValueError('raw row is after the point-in-time anchor')
        normalized = sina_normalized_for_date(factors, row['date'], anchor)
        out.append({
            **row,
            'adjustment': 'sina_qfq_normalized',
            'qfq_factor': normalized,
            'adjusted_close': row['raw_close'] * normalized,
            'known_at': None,
            'source_id': f"{row['source_id']}+sina:qfq:anchor={anchor}",
        })
    return out


def _fetch_bytes(url: str, params: dict, timeout: int) -> bytes:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f'{url}?{query}',
        headers={'User-Agent': 'Mozilla/5.0 GP12-CANDIDATE-V1',
                 'Referer': 'https://finance.sina.com.cn/'},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _chunks(start: str, end: str, days: int = 90) -> list[tuple[str, str]]:
    begin = dt.date.fromisoformat(start)
    finish = dt.date.fromisoformat(end)
    if finish < begin or days < 1:
        raise ValueError('invalid Sohu date range')
    out = []
    cursor = begin
    while cursor <= finish:
        stop = min(finish, cursor + dt.timedelta(days=days - 1))
        out.append((cursor.isoformat(), stop.isoformat()))
        cursor = stop + dt.timedelta(days=1)
    return out


def fetch_sohu_raw_range(symbol: str, *, start: str, end: str,
                         timeout: int = 20, retries: int = 3) -> list[dict]:
    symbol = normalize_symbol(symbol)
    by_date = {}
    code = symbol.split('.')[0]
    for chunk_start, chunk_end in _chunks(start, end):
        last_error = None
        for attempt in range(retries):
            try:
                raw = _fetch_bytes(SOHU_URL, {
                    'code': f'cn_{code}',
                    'start': chunk_start.replace('-', ''),
                    'end': chunk_end.replace('-', ''),
                    'stat': '1', 'order': 'A', 'period': 'd',
                    'callback': 'historySearchHandler', 'rt': 'jsonp',
                }, timeout)
                rows = parse_sohu_hishq_bytes(symbol, raw)
                for row in rows:
                    if row['date'] in by_date and by_date[row['date']] != row:
                        raise ValueError(f'conflicting Sohu row {row["date"]}')
                    by_date[row['date']] = row
                break
            except Exception as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(0.5 * (attempt + 1))
        else:
            raise RuntimeError(
                f'Sohu range failed for {symbol} {chunk_start}..{chunk_end}: {last_error}') from last_error
    return [by_date[key] for key in sorted(by_date)]


def fetch_sina_factors(symbol: str, *, timeout: int = 20, retries: int = 3) -> list[dict]:
    symbol = normalize_symbol(symbol)
    code, exchange = symbol.split('.')
    sina_symbol = exchange.lower() + code
    url = SINA_URL.format(sina_symbol=sina_symbol)
    last_error = None
    for attempt in range(retries):
        try:
            return parse_sina_qfq_js(symbol, _fetch_bytes(url, {}, timeout))
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f'Sina qfq fetch failed for {symbol}: {last_error}') from last_error


def probe_symbol(symbol: str, *, start: str, end: str,
                 timeout: int = 20) -> dict:
    symbol = normalize_symbol(symbol)
    raw_rows = fetch_sohu_raw_range(symbol, start=start, end=end, timeout=timeout)
    factors = fetch_sina_factors(symbol, timeout=timeout)
    rows = materialize_qfq_rows(raw_rows, factors, anchor=end)
    return {
        'artifact': 'GP12_SOHU_SINA_QFQ_PROBE_V1',
        'symbol': symbol,
        'window': [start, end],
        'raw_rows': len(raw_rows),
        'qfq_rows': len(rows),
        'first_date': rows[0]['date'] if rows else None,
        'last_date': rows[-1]['date'] if rows else None,
        'factor_rows': len(factors),
        'factor_path_sha256': hashlib.sha256(
            json.dumps(factors, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'point_in_time_known_at': False,
        'real_feature_inputs_validated': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Probe Sohu RAW + Sina QFQ for GP12')
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = probe_symbol(args.symbol, start=args.start, end=args.end, timeout=args.timeout)
    pathlib.Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
