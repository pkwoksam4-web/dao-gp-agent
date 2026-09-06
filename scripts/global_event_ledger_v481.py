from __future__ import annotations

from collections import Counter


def validate_ledger_pages(page_docs, expected_report: str, formal_beg: str, formal_end: str) -> dict:
    docs = list(page_docs or [])
    if not docs:
        raise ValueError('no ledger pages')

    seen_pages = set()
    declared_pages = set()
    declared_counts = set()
    rows = []

    for doc in docs:
        if doc.get('report') != expected_report:
            raise ValueError(f'wrong report: {doc.get("report")}')
        page_number = int(doc.get('page_number') or 0)
        if page_number <= 0 or page_number in seen_pages:
            raise ValueError(f'invalid/duplicate page number: {page_number}')
        seen_pages.add(page_number)

        payload = doc.get('payload') or {}
        if payload.get('success') is not True or int(payload.get('code', -1)) != 0:
            raise ValueError(f'non-success page {page_number}: code={payload.get("code")}')
        result = payload.get('result') or {}
        pages = int(result.get('pages') or 0)
        count = int(result.get('count') or 0)
        data = result.get('data') or []
        if not isinstance(data, list):
            raise ValueError(f'page {page_number} data is not list')
        if pages <= 0 and count > 0:
            raise ValueError(f'page {page_number} invalid pages={pages} for count={count}')
        declared_pages.add(pages)
        declared_counts.add(count)

        for row in data:
            if not isinstance(row, dict):
                raise ValueError(f'page {page_number} contains non-object row')
            code = str(row.get('SECURITY_CODE') or '').strip()
            ex_date = str(row.get('EX_DIVIDEND_DATE') or '')[:10]
            if not code:
                raise ValueError(f'page {page_number} missing SECURITY_CODE')
            if len(ex_date) != 10 or not (formal_beg <= ex_date <= formal_end):
                raise ValueError(f'out-of-window or missing EX_DIVIDEND_DATE: {code} {ex_date!r}')
            rows.append(row)

    if len(declared_pages) != 1 or len(declared_counts) != 1:
        raise ValueError(f'inconsistent API declarations pages={declared_pages} counts={declared_counts}')
    page_count = next(iter(declared_pages))
    row_count_expected = next(iter(declared_counts))
    expected_pages = set(range(1, page_count + 1))
    if seen_pages != expected_pages:
        missing = sorted(expected_pages - seen_pages)
        extra = sorted(seen_pages - expected_pages)
        raise ValueError(f'page partition incomplete missing={missing[:10]} extra={extra[:10]}')
    if len(rows) != row_count_expected:
        raise ValueError(f'row count mismatch rows={len(rows)} api_count={row_count_expected}')

    code_counts = Counter(str(r.get('SECURITY_CODE')).strip() for r in rows)
    return {
        'status': 'GLOBAL_LEDGER_EXPLICIT_SUCCESS',
        'report': expected_report,
        'formal_window': [formal_beg, formal_end],
        'page_count': page_count,
        'row_count': len(rows),
        'api_count': row_count_expected,
        'unique_security_codes': len(code_counts),
        'rows': rows,
    }
