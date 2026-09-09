from __future__ import annotations

import hashlib
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

import requests

from gp12_sina_share_amount_v1 import normalize_symbol


VERSION = '1.0'
SOURCE_ENDPOINT_FAMILY = 'SINA_STOCK_STRUCTURE_HISTORY'
STOCK_STRUCTURE_URL = (
    'https://vip.stock.finance.sina.com.cn/corp/go.php/'
    'vCI_StockStructure/stockid/{code}.phtml'
)


class _TableRowParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_tr = False
        self._cell_depth = 0
        self._row: list[str] = []
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == 'tr':
            self._in_tr = True
            self._row = []
        elif self._in_tr and tag in {'td', 'th'}:
            self._cell_depth += 1
            if self._cell_depth == 1:
                self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._in_tr and tag in {'td', 'th'} and self._cell_depth:
            self._cell_depth -= 1
            if self._cell_depth == 0:
                text = ''.join(self._cell_parts).replace('\xa0', ' ').strip()
                self._row.append(text)
                self._cell_parts = []
        elif tag == 'tr' and self._in_tr:
            if self._row:
                self.rows.append(self._row)
            self._in_tr = False
            self._row = []
            self._cell_depth = 0
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_tr and self._cell_depth:
            self._cell_parts.append(data)


def _decode_html(raw: bytes) -> str:
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise ValueError('empty Sina StockStructure payload')
    for encoding in ('gb18030', 'utf-8-sig'):
        try:
            return bytes(raw).decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError('Sina StockStructure payload decode failed')


def _label(value: str) -> str:
    compact = re.sub(r'\s+', '', value or '')
    return compact.lstrip('·•')


def _iso_yyyymmdd(value: Any) -> str:
    text = re.sub(r'\s+', '', str(value or ''))
    if not re.fullmatch(r'\d{8}', text):
        raise ValueError('StockStructure date must be YYYYMMDD')
    try:
        parsed = date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError as exc:
        raise ValueError('StockStructure date invalid') from exc
    return parsed.isoformat()


def _display_amount(value: Any) -> tuple[str, int] | None:
    text = str(value or '').replace(',', '').strip()
    if text == '--':
        return None
    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*万股', text)
    if not match:
        raise ValueError('StockStructure circulating A-share value invalid')
    number_text = match.group(1)
    try:
        numeric = Decimal(number_text)
    except InvalidOperation as exc:
        raise ValueError('StockStructure circulating A-share value invalid') from exc
    if not numeric.is_finite() or numeric <= 0:
        raise ValueError('StockStructure circulating A-share value must be positive')
    scale = len(number_text.partition('.')[2]) if '.' in number_text else 0
    return number_text, scale


def _find_block_row(block: list[list[str]], target: str) -> list[str] | None:
    for row in block:
        if not row:
            continue
        label = _label(row[0])
        if target == 'circulating_a':
            if label.startswith('流通A股') and '历史记录' in label:
                return row
        elif label == target:
            return row
    return None


def parse_stock_structure_bytes(symbol: str, raw: bytes) -> list[dict]:
    normalized = normalize_symbol(symbol)
    parser = _TableRowParser()
    parser.feed(_decode_html(raw))
    parser.close()

    starts = [
        index for index, row in enumerate(parser.rows)
        if row and _label(row[0]) == '变动日期'
    ]
    if not starts:
        raise ValueError('StockStructure change-date row missing')

    candidates: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(parser.rows)
        block = parser.rows[start:end]
        change_row = block[0]
        announcement_row = _find_block_row(block, '公告日期')
        reason_row = _find_block_row(block, '变动原因')
        circulating_row = _find_block_row(block, 'circulating_a')
        if announcement_row is None:
            raise ValueError('StockStructure announcement row missing')
        if reason_row is None:
            raise ValueError('StockStructure change-reason row missing')
        if circulating_row is None:
            raise ValueError('StockStructure circulating A-share row missing')

        counts = {
            len(change_row) - 1,
            len(announcement_row) - 1,
            len(reason_row) - 1,
            len(circulating_row) - 1,
        }
        if len(counts) != 1 or not counts or next(iter(counts)) <= 0:
            raise ValueError('StockStructure column count mismatch')
        column_n = next(iter(counts))

        for offset in range(1, column_n + 1):
            change_date = _iso_yyyymmdd(change_row[offset])
            announcement_date = _iso_yyyymmdd(announcement_row[offset])
            amount = _display_amount(circulating_row[offset])
            reason = str(reason_row[offset] or '').strip()
            amount_key = '--' if amount is None else amount[0]
            key = (change_date, announcement_date, amount_key)
            if key in seen:
                raise ValueError('duplicate StockStructure normalized column')
            seen.add(key)
            candidates.append({
                'symbol': normalized,
                'change_date': change_date,
                'announcement_date': announcement_date,
                'change_reason': reason,
                '_amount': amount,
            })

    candidates.sort(
        key=lambda item: (
            item['change_date'],
            item['announcement_date'],
            '' if item['_amount'] is None else item['_amount'][0],
        )
    )

    normalized_rows: list[dict] = []
    valid_state_seen = False
    for item in candidates:
        amount = item['_amount']
        if amount is None:
            if valid_state_seen:
                raise ValueError(
                    'StockStructure circulating A-share placeholder after valid state')
            continue
        valid_state_seen = True
        amount_text, scale = amount
        normalized_rows.append({
            'symbol': item['symbol'],
            'change_date': item['change_date'],
            'announcement_date': item['announcement_date'],
            'change_reason': item['change_reason'],
            'circulating_a_10k_display': amount_text,
            'circulating_a_display_scale': scale,
        })

    if not normalized_rows:
        raise ValueError('StockStructure circulating A-share state missing')
    return normalized_rows


def fetch_stock_structure(
    session: requests.Session,
    symbol: str,
    timeout: int = 20,
    retries: int = 3,
) -> tuple[bytes | None, dict]:
    normalized = normalize_symbol(symbol)
    code = normalized.split('.')[0]
    url = STOCK_STRUCTURE_URL.format(code=code)
    last_error = None
    for attempt in range(1, max(1, int(retries)) + 1):
        try:
            response = session.get(
                url,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36',
                    'Referer': 'https://finance.sina.com.cn/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Connection': 'close',
                },
            )
            response.raise_for_status()
            raw = bytes(response.content)
            if not raw:
                raise ValueError('empty Sina StockStructure response')
            return raw, {
                'symbol': normalized,
                'status': 'FETCHED',
                'http_status': int(response.status_code),
                'raw_sha256': hashlib.sha256(raw).hexdigest(),
                'raw_byte_n': len(raw),
                'request_identity': url,
                'source_endpoint_family': SOURCE_ENDPOINT_FAMILY,
                'blockers': [],
            }
        except Exception as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            if attempt < max(1, int(retries)):
                time.sleep(min(2.0, 0.5 * attempt))
    return None, {
        'symbol': normalized,
        'status': 'BLOCKED',
        'http_status': None,
        'raw_sha256': None,
        'raw_byte_n': 0,
        'request_identity': url,
        'source_endpoint_family': SOURCE_ENDPOINT_FAMILY,
        'error': last_error,
        'blockers': ['SINA_STOCK_STRUCTURE_SOURCE_UNAVAILABLE'],
    }
