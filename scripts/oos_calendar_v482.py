from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re


VERSION = 'V4.82'
FORMAL_END = '2026-04-17'
OOS_START = '2026-04-18'
OOS_END = '2026-09-08'
FORMAL_CALENDAR_SHA256 = '5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7'
OOS_CALENDAR_SHA256 = '897a76ff4a857c9712f98877491f03e975f0ee591025cfa543e1a618b240b992'
FULL_CALENDAR_SHA256 = 'e60deef5c885b36b99fe8dd1cbd6d5763a2f945f123e9fd5f60ce07c907c5019'
EXPECTED_FORMAL_DATE_N = 1426
EXPECTED_OOS_DATE_N = 98
EXPECTED_TOTAL_DATE_N = 1524
SSE_URL = 'https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml'
SZSE_URL = 'https://www.szse.cn/disclosure/notice/general/t20251222_618087.html'
SHA_RE = re.compile(r'^[0-9a-f]{64}$')

LABOUR_MARKER = '5月1日（星期五）至5月5日（星期二）休市，5月6日（星期三）起照常开市'
DRAGON_MARKER = '6月19日（星期五）至6月21日（星期日）休市，6月22日（星期一）起照常开市'
HOLIDAY_INTERVALS = (
    (dt.date(2026, 5, 1), dt.date(2026, 5, 5)),
    (dt.date(2026, 6, 19), dt.date(2026, 6, 21)),
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_visible_text(raw_html: str) -> str:
    if not isinstance(raw_html, str) or not raw_html.strip():
        raise ValueError('official schedule source missing')
    text = re.sub(r'(?is)<script.*?</script>|<style.*?</style>', '', raw_html)
    text = re.sub(r'(?s)<[^>]+>', '', text)
    text = html.unescape(text)
    return re.sub(r'\s+', '', text)


def _weekday_holiday_closures(raw_html: str) -> list[str]:
    text = _normalize_visible_text(raw_html)
    if '2026' not in text:
        raise ValueError('official schedule year missing')
    for marker in (LABOUR_MARKER, DRAGON_MARKER):
        if marker not in text:
            raise ValueError('official schedule marker missing')

    closures: list[str] = []
    for start, end in HOLIDAY_INTERVALS:
        current = start
        while current <= end:
            if current.weekday() < 5:
                closures.append(current.isoformat())
            current += dt.timedelta(days=1)
    return closures


def _business_weekdays(start: str, end: str, closed: set[str]) -> list[str]:
    start_date = dt.date.fromisoformat(start)
    end_date = dt.date.fromisoformat(end)
    if end_date < start_date:
        raise ValueError('calendar range invalid')
    out: list[str] = []
    current = start_date
    while current <= end_date:
        iso = current.isoformat()
        if current.weekday() < 5 and iso not in closed:
            out.append(iso)
        current += dt.timedelta(days=1)
    return out


def _dates_sha256(dates: list[str]) -> str:
    if not dates:
        raise ValueError('calendar dates empty')
    return _sha256_bytes('\n'.join(dates).encode('ascii'))


def build_oos_calendar(sse_html: str, szse_html: str) -> dict:
    sse_closed = _weekday_holiday_closures(sse_html)
    szse_closed = _weekday_holiday_closures(szse_html)
    if sse_closed != szse_closed:
        raise ValueError('exchange holiday schedule mismatch')

    dates = _business_weekdays(OOS_START, OOS_END, set(sse_closed))
    digest = _dates_sha256(dates)
    if len(dates) != EXPECTED_OOS_DATE_N:
        raise ValueError('OOS calendar count mismatch')
    if dates[0] != '2026-04-20' or dates[-1] != OOS_END:
        raise ValueError('OOS calendar bounds mismatch')
    if digest != OOS_CALENDAR_SHA256:
        raise ValueError('OOS calendar hash mismatch')

    return {
        'artifact': 'OOS_CALENDAR_V482',
        'version': VERSION,
        'status': 'OOS_CALENDAR_READY_V482',
        'formal_end': FORMAL_END,
        'oos_start': OOS_START,
        'oos_end': OOS_END,
        'first_oos_trade_date': dates[0],
        'last_oos_trade_date': dates[-1],
        'oos_date_n': len(dates),
        'oos_calendar_sha256': digest,
        'weekday_holiday_closures': sse_closed,
        'source_agreement': True,
        'sse_source': {
            'url': SSE_URL,
            'sha256': _sha256_bytes(sse_html.encode('utf-8')),
        },
        'szse_source': {
            'url': SZSE_URL,
            'sha256': _sha256_bytes(szse_html.encode('utf-8')),
        },
        'dates': dates,
    }


def bind_extended_calendar(formal_dates: list[str], oos_dates: list[str]) -> dict:
    if not formal_dates or not oos_dates:
        raise ValueError('calendar segment missing')
    if formal_dates != sorted(formal_dates) or len(set(formal_dates)) != len(formal_dates):
        raise ValueError('formal calendar ordering invalid')
    if oos_dates != sorted(oos_dates) or len(set(oos_dates)) != len(oos_dates):
        raise ValueError('OOS calendar ordering invalid')
    if formal_dates[-1] != FORMAL_END:
        raise ValueError('formal calendar end mismatch')
    if oos_dates[0] <= FORMAL_END or oos_dates[-1] != OOS_END:
        raise ValueError('OOS calendar bounds invalid')
    combined = formal_dates + oos_dates
    return {
        'formal_date_n': len(formal_dates),
        'oos_date_n': len(oos_dates),
        'total_date_n': len(combined),
        'first_date': combined[0],
        'last_date': combined[-1],
        'formal_calendar_sha256': _dates_sha256(formal_dates),
        'oos_calendar_sha256': _dates_sha256(oos_dates),
        'calendar_sha256': _dates_sha256(combined),
        'dates': combined,
    }


def _sha_ok(value: object) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def bind_oos_calendar_checkpoint(checkpoint: dict, manifest: dict) -> dict:
    if not isinstance(checkpoint, dict) or checkpoint.get('artifact') != 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482':
        raise ValueError('recovery checkpoint invalid')
    if checkpoint.get('version') != VERSION:
        raise ValueError('recovery checkpoint invalid')
    if not isinstance(manifest, dict):
        raise ValueError('OOS calendar manifest invalid')

    required = {
        'artifact': 'OOS_CALENDAR_V482',
        'version': VERSION,
        'status': 'OOS_CALENDAR_READY_V482',
        'formal_end': FORMAL_END,
        'oos_start': OOS_START,
        'oos_end': OOS_END,
        'first_oos_trade_date': '2026-04-20',
        'last_oos_trade_date': OOS_END,
        'oos_date_n': EXPECTED_OOS_DATE_N,
        'oos_calendar_sha256': OOS_CALENDAR_SHA256,
        'source_agreement': True,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise ValueError(f'OOS calendar manifest mismatch: {key}')

    formal_sha = checkpoint.get('formal_calendar_sha256')
    if manifest.get('formal_calendar_sha256') != formal_sha:
        raise ValueError('OOS calendar formal binding mismatch')
    if formal_sha != FORMAL_CALENDAR_SHA256:
        raise ValueError('formal calendar hash mismatch')
    if manifest.get('formal_date_n') != EXPECTED_FORMAL_DATE_N:
        raise ValueError('formal calendar count mismatch')
    if manifest.get('total_date_n') != EXPECTED_TOTAL_DATE_N:
        raise ValueError('full calendar count mismatch')
    if manifest.get('calendar_sha256') != FULL_CALENDAR_SHA256:
        raise ValueError('full calendar hash mismatch')

    for source_key, expected_url in (('sse_source', SSE_URL), ('szse_source', SZSE_URL)):
        source = manifest.get(source_key)
        if not isinstance(source, dict) or source.get('url') != expected_url or not _sha_ok(source.get('sha256')):
            raise ValueError('official calendar source invalid')

    out = json.loads(json.dumps(checkpoint, ensure_ascii=False))
    blockers = [b for b in out.get('blockers', []) if b != 'OOS_CALENDAR_COVERAGE_MISSING']
    blockers = sorted(set(blockers))
    out['blockers'] = blockers
    out['calendar_sha256'] = FULL_CALENDAR_SHA256
    out['oos_calendar_sha256'] = OOS_CALENDAR_SHA256
    out.setdefault('recoverable', {})['oos_calendar'] = True
    out.setdefault('evidence', {})['oos_calendar'] = {
        key: value for key, value in manifest.items() if key != 'dates'
    }
    complete = not blockers
    out['status'] = 'MODEL_ASSETS_COMPLETE_V482' if complete else 'MODEL_ASSETS_INCOMPLETE_V482'
    out['model_freeze_allowed'] = complete
    return out
