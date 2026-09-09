from __future__ import annotations

import hashlib
import json
import math
import re
import time
from bisect import bisect_right
from datetime import date
from typing import Any

import requests


VERSION = '1.0'
FORMAL_END = '2026-04-17'
UNIVERSE_SHA256 = 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb'
SOURCE_ENDPOINT_FAMILY = 'SINA_STOCKSERVICE_SHARE_AMOUNT'
SOURCE_URL = (
    'https://stock.finance.sina.com.cn/stock/api/jsonp.php/'
    'var%20KKE_ShareAmount_{symbol}=/StockService.getAmountBySymbol?_=20&symbol={symbol}'
)
DATE_SEMANTICS_KEYS = {
    'source', 'evidence_type', 'verified', 'source_identity',
}


def normalize_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper()
    if '.' not in s:
        raise ValueError('exchange-qualified symbol required')
    code, exchange = s.split('.', 1)
    if exchange not in {'SH', 'SZ'} or not code.isdigit() or len(code) > 6:
        raise ValueError(f'unsupported symbol: {symbol!r}')
    return f'{code.zfill(6)}.{exchange}'


def to_sina_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split('.')
    return ('sh' if exchange == 'SH' else 'sz') + code


def _canonical_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError('share record date must be a string')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('share record date must be ISO YYYY-MM-DD') from exc
    if parsed.isoformat() != value:
        raise ValueError('share record date must be canonical ISO YYYY-MM-DD')
    return value


def _positive_finite(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('share amount must be numeric') from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError('share amount must be finite and positive')
    return numeric


def _extract_payload(raw: bytes) -> list:
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise ValueError('empty Sina share payload')
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            text = bytes(raw).decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise ValueError('Sina share payload decode failed')
    start = text.find('[')
    end = text.rfind(']')
    if start < 0 or end < start:
        raise ValueError('Sina share JSONP wrapper mismatch')
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError('Sina share JSON payload invalid') from exc
    if not isinstance(value, list) or not value:
        raise ValueError('Sina share payload empty')
    return value


def parse_share_amount_bytes(symbol: str, raw: bytes) -> list[dict]:
    normalized = normalize_symbol(symbol)
    values = _extract_payload(raw)
    rows: list[dict] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, list) or len(item) < 2:
            raise ValueError('Sina share record invalid')
        record_date = _canonical_date(str(item[0]))
        if record_date in seen:
            raise ValueError('duplicate Sina share record date')
        seen.add(record_date)
        units_10k = _positive_finite(item[1])
        rows.append({
            'symbol': normalized,
            'record_date': record_date,
            'outstanding_share_shares': units_10k * 10_000.0,
        })
    rows.sort(key=lambda row: row['record_date'])
    return rows


def resolve_share_state(records: list[dict], trade_date: str) -> dict | None:
    target = _canonical_date(trade_date)
    if not isinstance(records, list):
        raise ValueError('share records must be a list')
    normalized: list[dict] = []
    previous = None
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError('share record must be an object')
        record_date = _canonical_date(raw.get('record_date'))
        shares = _positive_finite(raw.get('outstanding_share_shares'))
        if previous is not None and record_date <= previous:
            raise ValueError('share records must be strictly increasing')
        previous = record_date
        item = dict(raw)
        item['record_date'] = record_date
        item['outstanding_share_shares'] = shares
        normalized.append(item)
    dates = [item['record_date'] for item in normalized]
    idx = bisect_right(dates, target) - 1
    if idx < 0:
        return None
    return dict(normalized[idx])


def build_symbol_evidence(
    symbol: str,
    raw: bytes,
    fetched_at: str,
    http_status: int,
) -> dict:
    normalized = normalize_symbol(symbol)
    rows = parse_share_amount_bytes(normalized, raw)
    formal_rows = [dict(row) for row in rows if row['record_date'] <= FORMAL_END]
    raw_sha256 = hashlib.sha256(bytes(raw)).hexdigest()
    for row in formal_rows:
        row['share_raw_sha256'] = raw_sha256
    if not formal_rows:
        raise ValueError('Sina share coverage contains no Formal-era record')
    return {
        'symbol': normalized,
        'sina_symbol': to_sina_symbol(normalized),
        'status': 'FETCHED',
        'http_status': int(http_status),
        'fetched_at': str(fetched_at),
        'raw_sha256': raw_sha256,
        'raw_byte_n': len(raw),
        'source_endpoint_family': SOURCE_ENDPOINT_FAMILY,
        'normalized_record_count': len(formal_rows),
        'post_formal_record_n': len(rows) - len(formal_rows),
        'record_start': formal_rows[0]['record_date'],
        'record_end': formal_rows[-1]['record_date'],
        'records': formal_rows,
        'blockers': [],
    }


def _date_semantics_verified(value: dict | None) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == DATE_SEMANTICS_KEYS
        and value.get('source') == 'SINA_STOCK_STRUCTURE_HISTORY'
        and value.get('evidence_type') == 'EFFECTIVE_HISTORICAL_SHARE_STATE'
        and value.get('verified') is True
        and isinstance(value.get('source_identity'), str)
        and bool(value.get('source_identity').strip())
    )


def build_share_manifest(
    symbol_evidence: list[dict],
    universe_sha256: str,
    date_semantics_evidence: dict | None,
) -> dict:
    if universe_sha256 != UNIVERSE_SHA256:
        raise ValueError('UNIVERSE_BINDING_INVALID')
    if not isinstance(symbol_evidence, list):
        raise ValueError('symbol_evidence must be a list')
    blockers: set[str] = set()
    fetched = 0
    failed = 0
    raw_response_count = 0
    normalized_record_count = 0
    normalized_items: list[dict] = []
    seen_symbols: set[str] = set()
    for raw in symbol_evidence:
        if not isinstance(raw, dict):
            raise ValueError('symbol evidence must be an object')
        item = dict(raw)
        symbol = normalize_symbol(item.get('symbol'))
        if symbol in seen_symbols:
            raise ValueError('duplicate symbol evidence')
        seen_symbols.add(symbol)
        item['symbol'] = symbol
        status = item.get('status')
        if status == 'FETCHED':
            fetched += 1
            raw_response_count += 1
            normalized_record_count += int(item.get('normalized_record_count', 0))
        else:
            failed += 1
            blockers.update(item.get('blockers') or ['SINA_SHARE_SOURCE_UNAVAILABLE'])
        normalized_items.append(item)
    if failed:
        blockers.add('SINA_SHARE_COVERAGE_INCOMPLETE')
    if not _date_semantics_verified(date_semantics_evidence):
        blockers.add('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED')
    normalized_items.sort(key=lambda item: item['symbol'])
    return {
        'artifact': 'SINA_SHARE_AMOUNT_MANIFEST_GP12_V1',
        'version': VERSION,
        'formal_end': FORMAL_END,
        'universe_sha256': universe_sha256,
        'symbol_n': len(normalized_items),
        'symbols_fetched': fetched,
        'symbols_failed': failed,
        'raw_response_count': raw_response_count,
        'normalized_record_count': normalized_record_count,
        'parser_version': VERSION,
        'source_endpoint_family': SOURCE_ENDPOINT_FAMILY,
        'share_date_semantics_evidence': date_semantics_evidence,
        'symbol_evidence': normalized_items,
        'blockers': sorted(blockers),
        'formal_admission': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def fetch_share_amount(
    session: requests.Session,
    symbol: str,
    timeout: int = 20,
    retries: int = 3,
) -> tuple[bytes | None, dict]:
    normalized = normalize_symbol(symbol)
    sina_symbol = to_sina_symbol(normalized)
    url = SOURCE_URL.format(symbol=sina_symbol)
    last_error = None
    for attempt in range(1, max(1, int(retries)) + 1):
        try:
            response = session.get(
                url,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36',
                    'Referer': f'https://finance.sina.com.cn/realstock/company/{sina_symbol}/nc.shtml',
                    'Accept': '*/*',
                    'Connection': 'close',
                },
            )
            response.raise_for_status()
            raw = bytes(response.content)
            if not raw:
                raise ValueError('empty Sina share response')
            return raw, {
                'symbol': normalized,
                'sina_symbol': sina_symbol,
                'status': 'FETCHED',
                'http_status': int(response.status_code),
                'raw_sha256': hashlib.sha256(raw).hexdigest(),
                'raw_byte_n': len(raw),
                'request_identity': url,
                'blockers': [],
            }
        except Exception as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            if attempt < max(1, int(retries)):
                time.sleep(min(2.0, 0.5 * attempt))
    return None, {
        'symbol': normalized,
        'sina_symbol': sina_symbol,
        'status': 'BLOCKED',
        'http_status': None,
        'raw_sha256': None,
        'raw_byte_n': 0,
        'request_identity': url,
        'error': last_error,
        'blockers': ['SINA_SHARE_SOURCE_UNAVAILABLE'],
    }
