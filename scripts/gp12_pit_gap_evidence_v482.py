from __future__ import annotations

import datetime as dt
import math
import re

import cninfo_effective_terms_final_v482 as final_terms
from cninfo_exact_term_v481 import is_distribution_implementation_title
from gp12_pit_adjusted_close_v482 import validate_event_availability


GAP_KEYS = (
    ('000564.SZ', '2021-12-31'),
    ('300117.SZ', '2020-07-20'),
    ('300117.SZ', '2021-08-20'),
    ('600070.SH', '2020-07-10'),
    ('600070.SH', '2021-07-07'),
    ('600190.SH', '2020-07-02'),
    ('600190.SH', '2021-06-25'),
    ('600190.SH', '2022-06-24'),
    ('600190.SH', '2024-06-26'),
)


def _announcement_date(announcement: dict) -> str:
    if not isinstance(announcement, dict):
        raise ValueError('announcement must be an object')
    ms = announcement.get('announcementTime')
    if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(float(ms)):
        raise ValueError('announcementTime must be finite milliseconds')
    return dt.datetime.fromtimestamp(float(ms) / 1000.0, tz=dt.timezone.utc).date().isoformat()


def _sha256(value: object) -> str:
    text = str(value or '').lower()
    if not re.fullmatch(r'[0-9a-f]{64}', text):
        raise ValueError('official PDF SHA256 is invalid')
    return text


def _normalize_event(event: dict) -> dict:
    if not isinstance(event, dict):
        raise ValueError('event must be an object')
    out = dict(event)
    if 'cash_per_share_nominal' not in out:
        out['cash_per_share_nominal'] = float(out.get('cash_per_share') or 0.0)
    if 'capitalization_ratio' not in out:
        out['capitalization_ratio'] = float(out.get('cap_ratio') or 0.0)
    return out


def _is_allowed_implementation_title(symbol: str, title: str) -> bool:
    if is_distribution_implementation_title(title):
        return True
    compact = re.sub(r'\s+', '', str(title or ''))
    return (
        symbol == '000564.SZ'
        and '重整计划' in compact
        and '资本公积金转增股本' in compact
        and '实施' in compact
        and '公告' in compact
    )


def validate_official_gap_record(
    event: dict,
    announcement: dict,
    pdf_sha256: str,
    terms: dict,
    threshold_bp: float = 5.0,
) -> dict:
    normalized = _normalize_event(event)
    symbol = str(normalized.get('symbol') or '').upper()
    ex_date = str(normalized.get('ex_date') or '')[:10]
    if (symbol, ex_date) not in GAP_KEYS:
        raise ValueError(f'unexpected PIT gap key: {symbol}/{ex_date}')

    title = str((announcement or {}).get('announcementTitle') or '')
    if not _is_allowed_implementation_title(symbol, title):
        raise ValueError('announcement is not an allowed implementation notice')
    announcement_id = str((announcement or {}).get('announcementId') or '').strip()
    if not announcement_id:
        raise ValueError('announcementId is required')
    availability_date = _announcement_date(announcement)
    digest = _sha256(pdf_sha256)

    frozen_ratio = float(normalized.get('event_ratio'))
    if not math.isfinite(frozen_ratio) or frozen_ratio <= 0:
        raise ValueError('frozen event_ratio must be positive finite')
    validate_event_availability({
        'symbol': symbol,
        'ex_date': ex_date,
        'availability_date': availability_date,
        'event_ratio': frozen_ratio,
    })

    official_ratio = float(final_terms.corrected_event_ratio(normalized, terms or {}))
    if not math.isfinite(official_ratio) or official_ratio <= 0:
        raise ValueError('official event ratio must be positive finite')
    threshold = float(threshold_bp)
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError('threshold_bp must be finite and nonnegative')
    diff_bp = abs(official_ratio / frozen_ratio - 1.0) * 10000.0
    if diff_bp > threshold:
        raise ValueError(f'OFFICIAL_EVENT_RATIO_MISMATCH:{symbol}:{ex_date}:{diff_bp:.12f}bp')

    return {
        'symbol': symbol,
        'ex_date': ex_date,
        'availability_date': availability_date,
        'announcement_id': announcement_id,
        'announcement_title': title,
        'pdf_sha256': digest,
        'frozen_event_ratio': frozen_ratio,
        'official_event_ratio': official_ratio,
        'event_diff_bp': diff_bp,
        'threshold_bp': threshold,
        'status': 'PASS_OFFICIAL_PIT_AVAILABILITY',
    }
