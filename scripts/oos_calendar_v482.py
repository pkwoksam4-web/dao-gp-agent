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
OFFICIAL_EVIDENCE_SHA256 = '082ce4579a5d526faaa01249babef41dccd79caee6f35a2fa383ea62a6ef2f87'
EXPECTED_FORMAL_DATE_N = 1426
EXPECTED_OOS_DATE_N = 98
EXPECTED_TOTAL_DATE_N = 1524
SSE_URL = 'https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml'
SZSE_URL = 'https://investor.szse.cn/disclosure/notice/general/t20251222_618087.html'
SHA_RE = re.compile(r'^[0-9a-f]{64}$')

LABOUR_MARKER = '5月1日（星期五）至5月5日（星期二）休市，5月6日（星期三）起照常开市'
DRAGON_MARKER = '6月19日（星期五）至6月21日（星期日）休市，6月22日（星期一）起照常开市'
EXPECTED_SCHEDULE = {
    'labor_day': {
        'closed_start': '2026-05-01',
        'closed_end': '2026-05-05',
        'reopens': '2026-05-06',
    },
    'dragon_boat': {
        'closed_start': '2026-06-19',
        'closed_end': '2026-06-21',
        'reopens': '2026-06-22',
    },
}
EVIDENCE_KEYS = {'artifact', 'version', 'captured_on', 'sources'}
SOURCE_KEYS = {
    'exchange', 'title', 'url', 'published_on', 'document_no',
    'labor_day', 'dragon_boat',
}
HOLIDAY_KEYS = {'closed_start', 'closed_end', 'reopens'}
EXPECTED_SOURCE_META = {
    'SSE': {
        'title': '关于上海证券交易所2026年部分节假日休市安排的通知',
        'url': SSE_URL,
        'published_on': '2025-12-22',
        'document_no': '上证公告〔2025〕45号',
    },
    'SZSE': {
        'title': '关于2026年部分节假日休市安排的通知',
        'url': SZSE_URL,
        'published_on': '2025-12-22',
        'document_no': '深证会〔2025〕481号',
    },
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')
    ).encode('utf-8')


def _canonical_json_sha256(obj: object) -> str:
    return _sha256_bytes(_canonical_json_bytes(obj))


def _normalize_visible_text(raw_html: str) -> str:
    if not isinstance(raw_html, str) or not raw_html.strip():
        raise ValueError('official schedule source missing')
    text = re.sub(r'(?is)<script.*?</script>|<style.*?</style>', '', raw_html)
    text = re.sub(r'(?s)<[^>]+>', '', text)
    text = html.unescape(text)
    return re.sub(r'\s+', '', text)


def _interval_weekday_closures(start: str, end: str) -> list[str]:
    try:
        start_date = dt.date.fromisoformat(start)
        end_date = dt.date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise ValueError('holiday interval invalid') from exc
    if end_date < start_date:
        raise ValueError('holiday interval invalid')
    out: list[str] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += dt.timedelta(days=1)
    return out


def _weekday_holiday_closures(raw_html: str) -> list[str]:
    text = _normalize_visible_text(raw_html)
    if '2026' not in text:
        raise ValueError('official schedule year missing')
    for marker in (LABOUR_MARKER, DRAGON_MARKER):
        if marker not in text:
            raise ValueError('official schedule marker missing')
    closures: list[str] = []
    for holiday in ('labor_day', 'dragon_boat'):
        schedule = EXPECTED_SCHEDULE[holiday]
        closures.extend(_interval_weekday_closures(
            schedule['closed_start'], schedule['closed_end']
        ))
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


def _calendar_core(closures: list[str]) -> dict:
    dates = _business_weekdays(OOS_START, OOS_END, set(closures))
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
        'weekday_holiday_closures': closures,
        'source_agreement': True,
        'dates': dates,
    }


def build_oos_calendar(sse_html: str, szse_html: str) -> dict:
    sse_closed = _weekday_holiday_closures(sse_html)
    szse_closed = _weekday_holiday_closures(szse_html)
    if sse_closed != szse_closed:
        raise ValueError('exchange holiday schedule mismatch')
    out = _calendar_core(sse_closed)
    out['sse_source'] = {
        'url': SSE_URL,
        'sha256': _sha256_bytes(sse_html.encode('utf-8')),
    }
    out['szse_source'] = {
        'url': SZSE_URL,
        'sha256': _sha256_bytes(szse_html.encode('utf-8')),
    }
    return out


def _validate_holiday_object(value: object, holiday: str) -> dict:
    if not isinstance(value, dict) or set(value) != HOLIDAY_KEYS:
        raise ValueError('official evidence holiday schema invalid')
    expected = EXPECTED_SCHEDULE[holiday]
    if value != expected:
        raise ValueError('official evidence holiday schedule mismatch')
    for field in ('closed_start', 'closed_end', 'reopens'):
        try:
            dt.date.fromisoformat(str(value[field]))
        except ValueError as exc:
            raise ValueError('official evidence holiday date invalid') from exc
    if value['reopens'] <= value['closed_end']:
        raise ValueError('official evidence reopen date invalid')
    return value


def _validate_source_record(source: object) -> tuple[dict, list[str]]:
    if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
        raise ValueError('official evidence source schema invalid')
    exchange = source.get('exchange')
    if exchange not in EXPECTED_SOURCE_META:
        raise ValueError('official evidence exchange invalid')
    expected_meta = EXPECTED_SOURCE_META[exchange]
    for key, expected in expected_meta.items():
        if source.get(key) != expected:
            raise ValueError(f'official evidence source metadata mismatch: {exchange}:{key}')
    _validate_holiday_object(source.get('labor_day'), 'labor_day')
    _validate_holiday_object(source.get('dragon_boat'), 'dragon_boat')
    closures: list[str] = []
    for holiday in ('labor_day', 'dragon_boat'):
        schedule = source[holiday]
        closures.extend(_interval_weekday_closures(
            schedule['closed_start'], schedule['closed_end']
        ))
    return source, closures


def build_oos_calendar_from_evidence(evidence: dict) -> dict:
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_KEYS:
        raise ValueError('official evidence schema invalid')
    if evidence.get('artifact') != 'OOS_CALENDAR_OFFICIAL_EVIDENCE_V482':
        raise ValueError('official evidence artifact invalid')
    if evidence.get('version') != VERSION or evidence.get('captured_on') != '2026-09-08':
        raise ValueError('official evidence version/capture invalid')
    sources = evidence.get('sources')
    if not isinstance(sources, list) or len(sources) != 2:
        raise ValueError('official evidence source count invalid')

    validated: list[dict] = []
    closure_sets: list[list[str]] = []
    for source in sources:
        record, closures = _validate_source_record(source)
        validated.append(record)
        closure_sets.append(closures)
    if [source['exchange'] for source in validated] != ['SSE', 'SZSE']:
        raise ValueError('official evidence source order/independence invalid')
    if validated[0]['url'] == validated[1]['url']:
        raise ValueError('official evidence sources not independent')
    if closure_sets[0] != closure_sets[1]:
        raise ValueError('exchange holiday schedule mismatch')

    evidence_sha = _canonical_json_sha256(evidence)
    if evidence_sha != OFFICIAL_EVIDENCE_SHA256:
        raise ValueError('official evidence canonical hash mismatch')

    out = _calendar_core(closure_sets[0])
    out['official_evidence_sha256'] = evidence_sha
    out['official_sources'] = [
        {
            'exchange': source['exchange'],
            'title': source['title'],
            'url': source['url'],
            'published_on': source['published_on'],
            'document_no': source['document_no'],
            'evidence_sha256': _canonical_json_sha256(source),
        }
        for source in validated
    ]
    return out


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


def _validate_manifest_sources(manifest: dict) -> None:
    if manifest.get('official_evidence_sha256') is not None:
        if manifest.get('official_evidence_sha256') != OFFICIAL_EVIDENCE_SHA256:
            raise ValueError('official calendar evidence hash invalid')
        sources = manifest.get('official_sources')
        if not isinstance(sources, list) or len(sources) != 2:
            raise ValueError('official calendar sources invalid')
        if [source.get('exchange') for source in sources] != ['SSE', 'SZSE']:
            raise ValueError('official calendar sources invalid')
        for source in sources:
            expected = EXPECTED_SOURCE_META[source['exchange']]
            if source.get('url') != expected['url'] or source.get('published_on') != expected['published_on']:
                raise ValueError('official calendar source invalid')
            if source.get('document_no') != expected['document_no'] or not _sha_ok(source.get('evidence_sha256')):
                raise ValueError('official calendar source invalid')
        return

    for source_key, expected_url in (('sse_source', SSE_URL), ('szse_source', SZSE_URL)):
        source = manifest.get(source_key)
        if not isinstance(source, dict) or source.get('url') != expected_url or not _sha_ok(source.get('sha256')):
            raise ValueError('official calendar source invalid')


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
    _validate_manifest_sources(manifest)

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
