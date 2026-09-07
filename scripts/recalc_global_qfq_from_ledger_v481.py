from __future__ import annotations

from collections import defaultdict


def rows_by_security_code(rows):
    """Group global-ledger rows by six-digit SECURITY_CODE without collapsing duplicates."""
    out = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            raise ValueError('ledger row must be a dict')
        code = str(row.get('SECURITY_CODE') or '').strip()
        if len(code) != 6 or not code.isdigit():
            raise ValueError(f'invalid SECURITY_CODE: {code!r}')
        out[code].append(row)
    return dict(out)


def classify_result(
    formal_row_n: int,
    event_count: int,
    factor_compare_status: str | None,
    ledger_event_dates,
    sina_event_dates,
) -> str:
    """Fail-closed classification for the complete-global-ledger recalc stage."""
    if formal_row_n <= 0:
        return 'NOT_APPLICABLE_NO_FORMAL_ROWS'

    ledger_dates = sorted(set(ledger_event_dates or []))
    sina_dates = sorted(set(sina_event_dates or []))

    # Event-date disagreement is a provenance problem even if a numeric comparison
    # happens to look small on the remaining rows.
    if ledger_dates != sina_dates:
        return 'REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH'

    if factor_compare_status is None:
        return 'REVIEW_GLOBAL_LEDGER_FACTOR_COMPARISON'

    if factor_compare_status == 'PASS':
        if event_count <= 0:
            return 'PASS_GLOBAL_LEDGER_PROVEN_NO_ACTION'
        return 'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR'

    if factor_compare_status == 'FAIL':
        return 'REVIEW_GLOBAL_LEDGER_EXACT_TERMS'

    return 'REVIEW_GLOBAL_LEDGER_FACTOR_COMPARISON'
