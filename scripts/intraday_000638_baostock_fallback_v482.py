from __future__ import annotations

import pandas as pd

TARGET_SYMBOL = '000638.SZ'
TARGET_DATE = '2026-04-13'
TARGET_CODE = 'sz.000638'
TARGET_PROVIDER = 'BaoStock'
TARGET_ADJUSTFLAG = '3'

SINA_RUN_ID = 34444014051
SINA_ARTIFACT_ID = 10138954337
SINA_ARTIFACT_ZIP_SHA256 = 'a42b71995fdc355a920dc062a40c6294db129c2c41f3dbdc29b2d8a80fb5a7eb'
SINA_TARGET_ROWS_SHA256 = '72eac61af5dcd6b9d35e890f26f122e30905db1459da1f91d8557857de2faacc'

BAOSTOCK_RUN_ID = 34452654219
BAOSTOCK_ARTIFACT_ID = 10142164418
BAOSTOCK_ARTIFACT_ZIP_SHA256 = 'eaf42fa65436c874e252fc7426612f40b46597f6be2c1738fb2bfc3fbb823e60'
BAOSTOCK_5M_CANONICAL_SHA256 = '6cb7243bf6b535a6dd3ef9991025a1394a2c1913f5ae963c06c63f139e6347db'
BAOSTOCK_15M_CANONICAL_SHA256 = 'f4aaa1728793a02b3e8804789ec0cee1ca1c1e15d7bdda1a22247ac295e6420c'
BAOSTOCK_60M_CANONICAL_SHA256 = 'f6ef9280856e0946d1970ea13f680fff14139a258a6aaf9b811fb2da0a4cc6d7'

PRIMARY_VALID_DAYS = 1_011_606
REQUIRED_DAYS = 1_011_607
REQUIRED_OVERLAY_DAYS = 1

BAR_COLUMNS = [
    'symbol', 'trade_date', 'session', 'interval_minutes', 'source_start',
    'bar_end', 'source_rows', 'open', 'high', 'low', 'close', 'volume', 'turnover',
]

_EXPECTED_TIMES = {
    '15': ['0945', '1000', '1015', '1030', '1045', '1100', '1115', '1130',
           '1315', '1330', '1345', '1400', '1415', '1430', '1445', '1500'],
    '60': ['1030', '1130', '1400', '1500'],
}
_EXPECTED_COUNTS = {'5': 48, '15': 16, '60': 4}
_EXPECTED_HASHES = {
    '5': BAOSTOCK_5M_CANONICAL_SHA256,
    '15': BAOSTOCK_15M_CANONICAL_SHA256,
    '60': BAOSTOCK_60M_CANONICAL_SHA256,
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_baostock_probe_identity(probe: dict) -> None:
    _require(probe.get('artifact') == 'INTRADAY_000638_BAOSTOCK_PROBE_V482', 'artifact mismatch')
    _require(probe.get('version') == 'V4.82', 'version mismatch')
    _require(probe.get('symbol') == TARGET_SYMBOL, 'symbol mismatch')
    _require(probe.get('date') == TARGET_DATE, 'date mismatch')
    _require(probe.get('provider') == TARGET_PROVIDER, 'provider mismatch')
    _require(probe.get('query_code') == TARGET_CODE, 'query code mismatch')
    _require(str(probe.get('adjustflag')) == TARGET_ADJUSTFLAG, 'adjustflag mismatch')
    _require(probe.get('formal_fill_allowed') is False, 'upstream probe must remain non-promotional')
    _require(probe.get('minute_byte_coverage_verified') is False, 'minute coverage must remain false')

    freqs = probe.get('frequencies') or {}
    for freq in ('5', '15', '60'):
        item = freqs.get(freq) or {}
        _require(str(item.get('error_code')) == '0', f'{freq}m source error')
        _require(int(item.get('count', -1)) == _EXPECTED_COUNTS[freq], f'{freq}m count mismatch')
        _require(item.get('response_canonical_sha256') == _EXPECTED_HASHES[freq], f'{freq}m canonical hash mismatch')

    for freq in ('15', '60'):
        rows = freqs[freq].get('rows') or []
        _require(len(rows) == _EXPECTED_COUNTS[freq], f'{freq}m row payload count mismatch')
        got_times = []
        for row in rows:
            _require(row.get('date') == TARGET_DATE, f'{freq}m date mismatch')
            _require(row.get('code') == TARGET_CODE, f'{freq}m code mismatch')
            _require(str(row.get('adjustflag')) == TARGET_ADJUSTFLAG, f'{freq}m row adjustflag mismatch')
            raw_time = str(row.get('time', ''))
            _require(raw_time.startswith('20260413') and len(raw_time) >= 12, f'{freq}m timestamp mismatch')
            got_times.append(raw_time[8:12])
        _require(got_times == _EXPECTED_TIMES[freq], f'{freq}m bar grid mismatch')


def _native_bars(rows: list[dict], interval_minutes: int) -> pd.DataFrame:
    result = []
    for row in rows:
        raw_time = str(row['time'])
        bar_end = pd.to_datetime(raw_time[:12], format='%Y%m%d%H%M')
        result.append({
            'symbol': TARGET_SYMBOL,
            'trade_date': pd.Timestamp(TARGET_DATE),
            'session': 'AM' if bar_end.hour < 12 else 'PM',
            'interval_minutes': interval_minutes,
            # This is one native BaoStock aggregate record, not reconstructed minute rows.
            'source_start': bar_end,
            'bar_end': bar_end,
            'source_rows': 1,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(float(row['volume'])),
            'turnover': float(row['amount']),
        })
    return pd.DataFrame(result, columns=BAR_COLUMNS)


def build_overlay(probe: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_baostock_probe_identity(probe)
    b15 = _native_bars(probe['frequencies']['15']['rows'], 15)
    b60 = _native_bars(probe['frequencies']['60']['rows'], 60)
    _require(len(b15) == 16 and len(b60) == 4, 'overlay row count mismatch')
    return b15, b60


def coverage_flags_after_exact_overlay(*, primary_valid_days: int, required_days: int, overlay_days: int) -> dict:
    _require(primary_valid_days == PRIMARY_VALID_DAYS, 'primary valid-day cardinality mismatch')
    _require(required_days == REQUIRED_DAYS, 'required-day cardinality mismatch')
    _require(overlay_days == REQUIRED_OVERLAY_DAYS, 'overlay cardinality mismatch')
    _require(primary_valid_days + overlay_days == required_days, 'overlay does not exactly close aggregate coverage')
    return {
        'status': 'PASS_FORMAL847_AGGREGATE_BAR_COVERAGE_WITH_EXACT_SINGLE_DAY_FALLBACK',
        'formal_847_15m_coverage_verified': True,
        'formal_847_60m_coverage_verified': True,
        'formal_847_minute_byte_coverage_verified': False,
        'historical_gp_intraday_resampling_contract_recovered': False,
        'factor_formula_recovered': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
