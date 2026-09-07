from __future__ import annotations

import recalc_global_qfq_from_ledger_v481 as base

classify_result = base.classify_result
rows_by_security_code = base.rows_by_security_code
_ORIGINAL_RECALC_SYMBOL = base.recalc_symbol


def sina_factor_change_dates(factors, formal_beg: str, formal_end: str, rel_tol: float = 1e-12):
    """Return only dates where the Sina factor actually changes.

    qfq.js commonly contains a listing/baseline row whose factor is identical to
    the preceding 1900 sentinel. That row is metadata coverage, not a corporate
    action and must not be compared with the corporate-action ledger.
    """
    ordered = sorted(
        ({'date': str(r['date'])[:10], 'factor': float(r['factor'])} for r in (factors or [])),
        key=lambda r: r['date'],
    )
    out = []
    prev = None
    for row in ordered:
        factor = row['factor']
        if factor <= 0:
            raise ValueError('Sina factor must be positive')
        if prev is not None:
            changed = abs(factor / prev - 1.0) > rel_tol
            if changed and formal_beg < row['date'] <= formal_end:
                out.append(row['date'])
        prev = factor
    return sorted(set(out))


def recalc_symbol(*args, **kwargs):
    rec = _ORIGINAL_RECALC_SYMBOL(*args, **kwargs)
    if not isinstance(rec.get('factor_validation'), dict):
        return rec

    sina_meta = (rec.get('source_meta') or {}).get('sina') or {}
    path = sina_meta.get('path')
    if not path:
        rec['status'] = 'BLOCKED_GLOBAL_LEDGER_RAW_SOURCE'
        rec['error'] = 'corrected event semantics missing Sina provenance path'
        return rec

    try:
        factors = base.parse_sina_qfq(base.pathlib.Path(path).read_bytes())
        sina_dates = sina_factor_change_dates(factors, base.FORMAL_BEG, base.FORMAL_END)
    except Exception as e:
        rec['status'] = 'BLOCKED_GLOBAL_LEDGER_RAW_SOURCE'
        rec['error'] = f'{type(e).__name__}: {e}'
        return rec

    ledger_dates = sorted(set(rec.get('ledger_event_dates') or []))
    rec['sina_event_dates'] = sina_dates
    rec['missing_in_sina'] = sorted(set(ledger_dates) - set(sina_dates))
    rec['missing_in_ledger'] = sorted(set(sina_dates) - set(ledger_dates))
    rec['status'] = base.classify_result(
        int(rec.get('formal_rows') or 0),
        int(rec.get('event_count') or 0),
        rec['factor_validation'].get('status'),
        ledger_dates,
        sina_dates,
    )
    rec['sina_event_semantics'] = 'FACTOR_CHANGE_ONLY_EXCLUDES_EQUAL_LISTING_BASELINE'
    return rec


def main():
    base.recalc_symbol = recalc_symbol
    base.main()


if __name__ == '__main__':
    main()
