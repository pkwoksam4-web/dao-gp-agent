from __future__ import annotations


_SUPPLEMENTAL_PROFILES = {
    ('000564.SZ','2021-12-31'): '10转22.035714',
    ('000981.SZ','2022-02-25'): '10转14.82',
    ('002076.SZ','2022-12-21'): '10转4.58796',
    ('300117.SZ','2020-07-20'): '10派0.03元',
    ('300117.SZ','2021-08-20'): '10派0.13元',
    ('300262.SZ','2020-08-11'): '10派0.13元',
    ('600070.SH','2020-07-10'): '10派0.8元',
    ('600070.SH','2021-07-07'): '10派0.49元',
    ('600190.SH','2020-07-02'): '10派0.2元',
    ('600190.SH','2021-06-25'): '10派0.2元',
    ('600190.SH','2022-06-24'): '10派0.2元',
    ('600190.SH','2024-06-26'): '10派0.2元',
}


def canonical_supplemental_profile(symbol: str, date: str) -> str:
    return _SUPPLEMENTAL_PROFILES[(str(symbol).upper(), str(date))]


def extract_f10_target_profile(target: dict) -> str:
    if not isinstance(target, dict):
        raise ValueError('F10 target must be an object')
    date=str(target.get('date') or '')[:10]
    if len(date)!=10:
        raise ValueError('F10 target missing date')
    if target.get('status') != 'F10_PAGEAJAX_TARGET_DATE_HIT':
        raise ValueError('F10 target date is not positively evidenced')
    profiles=[]
    for hit in target.get('hits') or []:
        row=hit.get('row') if isinstance(hit,dict) else None
        if not isinstance(row,dict):
            continue
        if str(row.get('EX_DIVIDEND_DATE') or '')[:10] != date:
            continue
        if row.get('ASSIGN_PROGRESS') != '实施方案':
            continue
        profile=str(row.get('IMPL_PLAN_PROFILE') or '').strip()
        if profile:
            profiles.append(profile)
    uniq=sorted(set(profiles))
    if len(uniq) != 1:
        raise ValueError(f'expected one implemented profile for {date}; found={uniq}')
    return uniq[0]


def extract_supplemental_profile(symbol: str, date: str, records: list[dict]) -> str:
    symbol=str(symbol).upper(); date=str(date)[:10]
    matches=[]
    for r in records or []:
        if not isinstance(r,dict):
            continue
        if str(r.get('symbol') or '').upper()!=symbol or str(r.get('target_date') or '')[:10]!=date:
            continue
        if r.get('status')!='SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE':
            continue
        if r.get('target_date_found') is not True:
            continue
        if not (r.get('expected_term_found') is True or r.get('target_term_near') is True):
            continue
        matches.append(r)
    if len(matches)!=1:
        raise ValueError(f'expected one positive supplemental record for {symbol} {date}; found={len(matches)}')
    return canonical_supplemental_profile(symbol,date)


def extract_targeted_probe_profile(symbol: str, date: str, probe: dict) -> str:
    symbol=str(symbol).upper(); date=str(date)[:10]
    if not isinstance(probe,dict) or probe.get('artifact')!='MISSING_EVENT_300262_PROBE_V481':
        raise ValueError('unexpected targeted probe artifact')
    if str(probe.get('symbol') or '').upper()!=symbol or str(probe.get('target_date') or '')[:10]!=date:
        raise ValueError('targeted probe symbol/date mismatch')
    if probe.get('evidence_closed') is not True:
        raise ValueError('targeted probe evidence is not closed')
    profile=str(probe.get('profile') or '').strip()
    canonical=canonical_supplemental_profile(symbol,date)
    if profile!=canonical:
        raise ValueError(f'targeted probe profile mismatch: {profile!r} vs {canonical!r}')
    return profile


def resolve_target_profile(
    symbol: str,
    target: dict,
    supplemental_records: list[dict],
    targeted_probes: dict[tuple[str,str],dict],
) -> tuple[str,str]:
    symbol=str(symbol).upper()
    if not isinstance(target,dict):
        raise ValueError('target must be an object')
    date=str(target.get('date') or '')[:10]
    if target.get('status')=='F10_PAGEAJAX_TARGET_DATE_HIT':
        return extract_f10_target_profile(target),'F10_PAGEAJAX'
    key=(symbol,date)
    if key in (targeted_probes or {}):
        return extract_targeted_probe_profile(symbol,date,targeted_probes[key]),'TARGETED_PAGEAJAX_RETRY'
    return extract_supplemental_profile(symbol,date,supplemental_records),'SUPPLEMENTAL_EXACT_SOURCE'


def classify_missing_event_recalc(event_coverage_complete: bool, factor_compare_status: str | None) -> str:
    if not event_coverage_complete:
        return 'BLOCKED_MISSING_EVENT_COVERAGE'
    if factor_compare_status == 'PASS':
        return 'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR'
    if factor_compare_status == 'FAIL':
        return 'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'
    return 'BLOCKED_MISSING_EVENT_FACTOR_COMPARISON'
