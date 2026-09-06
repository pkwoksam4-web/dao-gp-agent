from __future__ import annotations

import json
import pathlib


def eastmoney_report_coverage(raw: bytes) -> str:
    try:
        obj = json.loads(raw.decode('utf-8'))
    except Exception:
        return 'FAILED'
    try:
        code = int(obj.get('code', -1))
    except Exception:
        return 'FAILED'
    if obj.get('success') is True and code == 0:
        return 'EXPLICIT_SUCCESS'
    if code == 9201:
        return 'EMPTY_UNPROVEN'
    return 'FAILED'


def sina_formal_event_dates(rows, formal_beg: str, formal_end: str):
    return sorted({str(r.get('date', ''))[:10] for r in (rows or []) if formal_beg < str(r.get('date', ''))[:10] <= formal_end})


def find_sina_raw(root: pathlib.Path, symbol: str) -> pathlib.Path:
    root = pathlib.Path(root)
    name = symbol.replace('.', '_') + '_sina_qfq.js'
    direct = [root / 'raw' / name, root / 'downloads' / 'raw' / name]
    hits = [p for p in direct if p.is_file()]
    if not hits:
        hits = [p for p in root.rglob(name) if p.is_file()]
    unique = []
    seen = set()
    for p in hits:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    if not unique:
        raise FileNotFoundError(f'missing corrected Sina raw for {symbol} under {root}')
    if len(unique) > 1:
        raise RuntimeError(f'ambiguous corrected Sina raw for {symbol}: {[str(p) for p in unique]}')
    return unique[0]


def classify_nominal_symbol(
    *,
    formal_row_n: int,
    event_count: int,
    factor_compare_status: str | None,
    sharebonus_coverage: str,
    rights_coverage: str,
    sina_formal_event_n: int,
) -> str:
    if formal_row_n <= 0:
        return 'NOT_APPLICABLE_NO_FORMAL_ROWS'
    coverages = {sharebonus_coverage, rights_coverage}
    if 'FAILED' in coverages:
        return 'BLOCKED_EVENT_SOURCE'
    explicit = sharebonus_coverage == 'EXPLICIT_SUCCESS' and rights_coverage == 'EXPLICIT_SUCCESS'
    if event_count <= 0:
        if sina_formal_event_n > 0:
            return 'REVIEW_MISSING_EVENT_SOURCE_MATCH'
        if not explicit:
            return 'UNKNOWN_NEGATIVE_EVENT_COVERAGE'
        if factor_compare_status not in {None, 'PASS'}:
            return 'REVIEW_REQUIRED_EXACT_CORPORATE_ACTION_TERMS'
        return 'PASS_PROVEN_NO_FORMAL_ACTIONS'
    if not explicit:
        return 'BLOCKED_EVENT_SOURCE'
    if factor_compare_status == 'PASS':
        return 'PASS_NOMINAL_EVENT_FACTOR'
    if factor_compare_status == 'FAIL':
        return 'REVIEW_REQUIRED_EXACT_CORPORATE_ACTION_TERMS'
    return 'REVIEW_REQUIRED_FACTOR_COMPARISON'
