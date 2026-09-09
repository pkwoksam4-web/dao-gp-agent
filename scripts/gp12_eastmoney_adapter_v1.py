from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import urllib.parse
import urllib.request


KLINE_URL = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
FLOW_URL = 'https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get'
QUOTE_URL = 'https://push2.eastmoney.com/api/qt/stock/get'
INTERVAL_KLT = {'1d': '101', '15m': '15', '60m': '60'}
REQUIRED_FAMILIES = (
    'stock_adjusted_close', 'market_adjusted_close', 'sector_adjusted_close',
    'amount_turnover', 'main_net_flow', 'market_breadth', 'sector_breadth',
    'status', 'intraday_15m', 'intraday_60m',
)


def plan_date_chunks(start: str, end: str, *, max_calendar_days: int = 31) -> list[tuple[str, str]]:
    """Split an inclusive date range into bounded, adjacent calendar windows."""
    if max_calendar_days < 1:
        raise ValueError('max_calendar_days must be positive')
    begin = dt.date.fromisoformat(start)
    finish = dt.date.fromisoformat(end)
    if finish < begin:
        raise ValueError('end before start')
    chunks = []
    cursor = begin
    while cursor <= finish:
        stop = min(finish, cursor + dt.timedelta(days=max_calendar_days - 1))
        chunks.append((cursor.isoformat(), stop.isoformat()))
        cursor = stop + dt.timedelta(days=1)
    return chunks


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if '.' not in value:
        raise ValueError(f'exchange-qualified symbol required: {symbol!r}')
    code, exchange = value.split('.', 1)
    if len(code) != 6 or not code.isdigit() or exchange not in {'SZ', 'SH'}:
        raise ValueError(f'unsupported symbol: {symbol!r}')
    return f'{code}.{exchange}'


def symbol_to_secid(symbol: str) -> str:
    code, exchange = normalize_symbol(symbol).split('.')
    return f'{"0" if exchange == "SZ" else "1"}.{code}'


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be numeric') from exc
    if not math.isfinite(result):
        raise ValueError(f'{label} must be finite')
    return result


def _payload_klines(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError('Eastmoney payload must be an object')
    data = payload.get('data')
    if data is None:
        return []
    if not isinstance(data, dict) or not isinstance(data.get('klines'), list):
        raise ValueError('Eastmoney payload has no klines list')
    return data['klines']


def parse_kline_payload(symbol: str, payload: object, *, interval: str,
                        adjustment: str) -> list[dict]:
    symbol = normalize_symbol(symbol)
    if interval not in INTERVAL_KLT:
        raise ValueError(f'unsupported interval: {interval}')
    if adjustment not in {'raw', 'qfq'}:
        raise ValueError(f'unsupported adjustment: {adjustment}')
    source_id = f'eastmoney:kline:klt={INTERVAL_KLT[interval]}:fqt={1 if adjustment == "qfq" else 0}'
    rows = []
    for index, line in enumerate(_payload_klines(payload)):
        if not isinstance(line, str):
            raise ValueError(f'kline row {index} is not text')
        parts = line.split(',')
        if len(parts) < 11:
            raise ValueError(f'kline row {index} has fewer than 11 fields')
        timestamp = parts[0].strip()
        if not timestamp:
            raise ValueError(f'kline row {index} has no timestamp')
        values = [_finite(parts[offset], f'kline row {index} field {offset}')
                  for offset in range(1, 11)]
        open_, close, high, low, volume_lots, amount, _, _, _, turnover_pct = values
        if min(open_, close, high, low) <= 0 or volume_lots < 0 or amount < 0:
            raise ValueError(f'kline row {index} has invalid non-positive values')
        base = {
            'symbol': symbol,
            'adjustment': adjustment,
            'source_id': source_id,
            'open': open_,
            'close': close,
            'high': high,
            'low': low,
            'volume_lots': volume_lots,
            'volume_shares': volume_lots * 100.0,
            'amount_cny': amount,
            'turnover_ratio': turnover_pct / 100.0,
            'known_at': None,
        }
        if interval == '1d':
            base['date'] = timestamp[:10]
        else:
            base['closed_at'] = timestamp
        rows.append(base)
    return rows


def parse_flow_payload(symbol: str, payload: object) -> list[dict]:
    symbol = normalize_symbol(symbol)
    rows = []
    for index, line in enumerate(_payload_klines(payload)):
        if not isinstance(line, str):
            raise ValueError(f'flow row {index} is not text')
        parts = line.split(',')
        if len(parts) < 2:
            raise ValueError(f'flow row {index} has fewer than 2 fields')
        rows.append({
            'symbol': symbol,
            'date': parts[0].strip()[:10],
            'main_net_flow_cny': _finite(parts[1], f'flow row {index} main flow'),
            'source_id': 'eastmoney:flow:daykline',
        })
    return rows


def parse_quote_payload(symbol: str, payload: object) -> dict:
    symbol = normalize_symbol(symbol)
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), dict):
        raise ValueError('Eastmoney quote payload has no data object')
    data = payload['data']
    return {
        'symbol': symbol,
        'name': data.get('f58'),
        'industry_name': data.get('f127'),
        'region_name': data.get('f128'),
        'source_id': 'eastmoney:stock:get',
    }


def build_readiness_report(families: object) -> dict:
    if not isinstance(families, dict):
        families = {}
    missing = []
    statuses = {}
    for family in REQUIRED_FAMILIES:
        value = families.get(family)
        status = value.get('status') if isinstance(value, dict) else None
        rows = value.get('rows') if isinstance(value, dict) else None
        if status == 'PASS' and rows == 0:
            status = 'EMPTY'
        statuses[family] = status or 'MISSING'
        if status != 'PASS':
            missing.append(family)
    complete = not missing
    return {
        'required_families': list(REQUIRED_FAMILIES),
        'family_statuses': statuses,
        'missing_families': missing,
        'structural_feature_families_complete': complete,
        # A probe only proves that an endpoint responded and parsed. It does not
        # prove historical point-in-time availability or substantive provenance.
        'real_feature_inputs_validated': False,
        'source_ids_substantively_verified': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def _get_json(url: str, params: dict, timeout: int) -> object:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f'{url}?{query}',
        headers={'User-Agent': 'Mozilla/5.0 GP12-CANDIDATE-V1'},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def fetch_kline(symbol: str, *, interval: str, adjustment: str,
                begin: str, end: str, timeout: int = 20) -> list[dict]:
    return parse_kline_payload(
        symbol,
        _get_json(KLINE_URL, {
            'secid': symbol_to_secid(symbol),
            'klt': INTERVAL_KLT[interval],
            'fqt': '1' if adjustment == 'qfq' else '0',
            'beg': begin.replace('-', ''),
            'end': end.replace('-', ''),
            'lmt': '1000000',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        }, timeout),
        interval=interval,
        adjustment=adjustment,
    )


def fetch_kline_range(symbol: str, *, interval: str, adjustment: str,
                      begin: str, end: str, timeout: int = 20,
                      max_calendar_days: int = 31,
                      retries: int = 3) -> list[dict]:
    """Fetch and merge bounded windows so long Eastmoney requests do not 502."""
    by_timestamp = {}
    last_error = None
    for window_begin, window_end in plan_date_chunks(
            begin, end, max_calendar_days=max_calendar_days):
        for attempt in range(retries):
            try:
                rows = fetch_kline(
                    symbol, interval=interval, adjustment=adjustment,
                    begin=window_begin, end=window_end, timeout=timeout)
                for row in rows:
                    key = row.get('date', row.get('closed_at'))
                    if key in by_timestamp and by_timestamp[key] != row:
                        raise ValueError(f'conflicting duplicate kline row: {symbol} {key}')
                    by_timestamp[key] = row
                break
            except Exception as exc:
                last_error = exc
                if attempt + 1 < retries:
                    # Keep retries deterministic and short; the caller can still
                    # record a hard source failure after the final attempt.
                    import time
                    time.sleep(0.25 * (attempt + 1))
        else:
            raise RuntimeError(
                f'Eastmoney kline window failed for {symbol} '
                f'{window_begin}..{window_end}: {last_error}') from last_error
    return [by_timestamp[key] for key in sorted(by_timestamp)]


def fetch_flow(symbol: str, *, limit: int = 1000, timeout: int = 20) -> list[dict]:
    last_error = None
    for attempt in range(3):
        try:
            return parse_flow_payload(
                symbol,
                _get_json(FLOW_URL, {
                    'lmt': str(limit),
                    'klt': '101',
                    'secid': symbol_to_secid(symbol),
                    'fields1': 'f1,f2,f3,f7',
                    'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                }, timeout),
            )
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                import time
                time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f'Eastmoney flow request failed for {symbol}: {last_error}') from last_error


def fetch_quote(symbol: str, *, timeout: int = 20) -> dict:
    return parse_quote_payload(symbol, _get_json(QUOTE_URL, {
        'secid': symbol_to_secid(symbol),
        'fields': 'f57,f58,f84,f85,f127,f128,f136,f137,f138,f139,f140,f141',
    }, timeout))


def _attempt(fn, *, family: str) -> tuple[dict, object | None]:
    try:
        value = fn()
        return {'status': 'PASS', 'rows': len(value) if isinstance(value, list) else 1}, value
    except Exception as exc:  # probe must record source failure and continue
        return {'status': 'FAILED_SOURCE', 'error_type': type(exc).__name__,
                'error': str(exc), 'family': family}, None


def probe_symbol(symbol: str, *, begin: str = '2020-06-01',
                 end: str = '2026-04-17', timeout: int = 20) -> dict:
    symbol = normalize_symbol(symbol)
    daily_meta, daily = _attempt(
        lambda: fetch_kline_range(symbol, interval='1d', adjustment='qfq',
                                  begin=begin, end=end, timeout=timeout),
        family='stock_adjusted_close')
    flow_meta, flow = _attempt(
        lambda: fetch_flow(symbol, timeout=timeout), family='main_net_flow')
    market_meta, market = _attempt(
        lambda: fetch_kline_range('000001.SH', interval='1d', adjustment='qfq',
                                  begin=begin, end=end, timeout=timeout),
        family='market_adjusted_close')
    quote_meta, quote = _attempt(lambda: fetch_quote(symbol, timeout=timeout), family='status')
    families = {
        'stock_adjusted_close': daily_meta,
        'market_adjusted_close': market_meta,
        'amount_turnover': daily_meta if daily_meta['status'] == 'PASS' else {'status': 'MISSING'},
        'main_net_flow': flow_meta,
        'sector_adjusted_close': {'status': 'MISSING', 'reason': 'industry index mapping not verified'},
        'market_breadth': {'status': 'MISSING', 'reason': 'universe breadth source not connected'},
        'sector_breadth': {'status': 'MISSING', 'reason': 'PIT sector membership not connected'},
        'status': {'status': 'MISSING', 'reason': 'PIT ST/tradability overlay not joined'},
        'intraday_15m': {'status': 'MISSING', 'reason': 'historical intraday availability unverified'},
        'intraday_60m': {'status': 'MISSING', 'reason': 'historical intraday availability unverified'},
    }
    return {
        'artifact': 'GP12_EASTMONEY_SOURCE_PROBE_V1',
        'symbol': symbol,
        'formal_window': [begin, end],
        'quote': quote,
        'daily': daily_meta,
        'flow': flow_meta,
        'market': market_meta,
        'quote_probe': quote_meta,
        'readiness': build_readiness_report(families),
        'families': families,
        'parsed_rows_not_embedded': True,
        'oos_metrics_allowed': False,
        'model_freeze_allowed': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Probe Eastmoney inputs for GP12 candidate')
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--begin', default='2020-06-01')
    parser.add_argument('--end', default='2026-04-17')
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = probe_symbol(args.symbol, begin=args.begin, end=args.end,
                          timeout=args.timeout)
    pathlib.Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
