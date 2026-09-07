from __future__ import annotations

import math
import re

EXPECTED_SPECIAL_N = 11


def _key(row: dict) -> tuple[str, str]:
    symbol = str(row.get('symbol') or '').upper()
    ex_date = str(row.get('ex_date') or '')[:10]
    if not symbol or len(ex_date) != 10:
        raise ValueError('special row missing symbol/ex_date')
    return symbol, ex_date


def _sha_ok(value) -> bool:
    return bool(re.fullmatch(r'[0-9a-fA-F]{64}', str(value or '')))


def enrich_special_rows(special_rows: list[dict], provenance_report: dict, expected_n: int = EXPECTED_SPECIAL_N) -> list[dict]:
    n = int(expected_n)
    if len(special_rows or []) != n:
        raise ValueError(f'expected {n} special closure rows; got {len(special_rows or [])}')
    if int(provenance_report.get('target_n') or 0) != n:
        raise ValueError('special provenance target partition mismatch')
    if int(provenance_report.get('materialized_n') or 0) != n or int(provenance_report.get('unresolved_n') or 0) != 0:
        raise ValueError('special provenance is not fully materialized')
    by = {}
    for row in provenance_report.get('records') or []:
        key = _key(row)
        if key in by:
            raise ValueError(f'duplicate special provenance row: {key}')
        by[key] = row
    if len(by) != n:
        raise ValueError(f'expected {n} special provenance records; got {len(by)}')
    out = []
    seen = set()
    for raw in special_rows:
        row = dict(raw)
        key = _key(row)
        if key in seen:
            raise ValueError(f'duplicate special closure row: {key}')
        seen.add(key)
        item = by.get(key)
        if item is None or item.get('status') != 'PASS_CNINFO_MATERIALIZED':
            raise ValueError(f'{key}: missing materialized provenance')
        a = float(row.get('adjusted_reference_price'))
        b = float(item.get('adjusted_reference_price'))
        if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > 1e-6:
            raise ValueError(f'{key}: adjusted reference price mismatch')
        prov = item.get('provenance') or {}
        if prov.get('source') != 'CNINFO_OFFICIAL_PDF':
            raise ValueError(f'{key}: provenance source is not CNINFO_OFFICIAL_PDF')
        aid = str(prov.get('announcement_id') or '').strip()
        sha = str(prov.get('materialized_sha256') or '').lower()
        if not aid or not _sha_ok(sha):
            raise ValueError(f'{key}: missing announcement id/materialized SHA')
        row['announcement_id'] = aid
        row['materialized_sha256'] = sha
        row['materialized_source'] = 'CNINFO_OFFICIAL_PDF'
        out.append(row)
    return sorted(out, key=_key)
