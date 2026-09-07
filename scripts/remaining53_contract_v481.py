from __future__ import annotations

ALREADY_RESOLVED_7={
    '000564.SZ','000981.SZ','002076.SZ','300117.SZ','300262.SZ','600070.SH','600190.SH',
}
BASE_AFTER_7={
    'PASS':707,
    'EXACT_TERM_REVIEW':84,
    'MISSING_EVENT_REVIEW':53,
    'NOT_APPLICABLE':3,
}


def select_remaining53(integrated_report: dict) -> list[dict]:
    records=[
        r for r in (integrated_report.get('records') or [])
        if isinstance(r,dict) and r.get('status')=='REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH'
    ]
    if len(records)!=60 or len({r.get('symbol') for r in records})!=60:
        raise ValueError(f'expected exact 60 base missing-event records; got {len(records)}')
    selected=[r for r in records if r.get('symbol') not in ALREADY_RESOLVED_7]
    if len(selected)!=53 or len({r.get('symbol') for r in selected})!=53:
        raise ValueError(f'expected exact remaining 53 records; got {len(selected)}')
    return sorted(selected,key=lambda r:r['symbol'])


def summarize_checkpoint_after_53(statuses: list[str]) -> dict:
    if len(statuses)!=53:
        raise ValueError(f'expected 53 statuses; got {len(statuses)}')
    pass_name='PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR'
    exact_name='REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'
    pass_n=sum(s==pass_name for s in statuses)
    exact_n=sum(s==exact_name for s in statuses)
    blocked_n=53-pass_n-exact_n
    out={
        'PASS':BASE_AFTER_7['PASS']+pass_n,
        'EXACT_TERM_REVIEW':BASE_AFTER_7['EXACT_TERM_REVIEW']+exact_n,
        'MISSING_EVENT_REVIEW':blocked_n,
        'NOT_APPLICABLE':BASE_AFTER_7['NOT_APPLICABLE'],
    }
    out['REVIEW_TOTAL']=out['EXACT_TERM_REVIEW']+out['MISSING_EVENT_REVIEW']
    return out
