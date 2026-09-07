from __future__ import annotations

import re


def _norm(text: str) -> str:
    s=str(text or '')
    s=s.replace('\u3000',' ').replace('\xa0',' ')
    s=re.sub(r'\s+','',s)
    s=s.replace('，',',').replace('。','.')
    return s


def _unique_value(candidates: list[tuple[float,str]], label: str) -> tuple[float|None,str|None,list[dict]]:
    if not candidates:
        return None,None,[]
    groups=[]
    for value,kind in candidates:
        if not any(abs(value-g[0])<=1e-7 for g in groups):
            groups.append((value,kind))
    if len(groups)!=1:
        raise ValueError(f'conflicting explicit {label} values: {[x[0] for x in groups]}')
    value=groups[0][0]
    kinds=sorted({kind for v,kind in candidates if abs(v-value)<=1e-7})
    return value,kinds[0],[{'value':v,'kind':k} for v,k in candidates]


def extract_effective_terms(text: str) -> dict:
    s=_norm(text)
    cash=[]
    cap=[]

    # Explicit effective cash used in ex-dividend price calculation.
    for m in re.finditer(r'每股现金红利应以([0-9]+(?:\.[0-9]+)?)元/股计算',s):
        cash.append((float(m.group(1)),'EXPLICIT_EFFECTIVE_CASH_PER_SHARE'))

    # Explicit cash folded over total shares; announcement often shows the formula
    # and the resulting effective per-share amount after repurchase shares are excluded.
    for m in re.finditer(r'按(?:公司)?总股本折算每股现金(?:分红|红利)比例[^。;；]*?=([0-9]+(?:\.[0-9]+)?)元/股',s):
        cash.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_FOLDED_CASH'))

    # V4.82 supplement: many implementation announcements state the final ex-right
    # formula explicitly as "record-date close - effective cash" but put the folded
    # cash calculation much earlier in the paragraph.  Accept the numeric subtraction
    # only when nearby text is clearly about ex-right/ex-dividend pricing.  If the
    # subtraction is followed by a non-trivial /(1+n) denominator, do not promote the
    # cash alone; that event requires a separately extracted capitalization ratio.
    for m in re.finditer(r'(?:股权登记日|权益分派股权登记日|前)收盘价[-－]([0-9]+(?:\.[0-9]+)?)(?:元/股|元)?',s):
        prior=s[max(0,m.start()-700):m.start()]
        after=s[m.end():m.end()+180]
        if '除权' not in prior and '除息' not in prior:
            continue
        if re.search(r'(?:/|÷)[（(]?1\+',after):
            continue
        cash.append((float(m.group(1)),'EXPLICIT_FINAL_EXRIGHT_CASH_SUBTRACTION'))

    # V4.82 supplement: folded per-share cash may omit the literal word "比例" and
    # may use "股权登记日的总股本" rather than "公司总股本".
    for m in re.finditer(
        r'按(?:股权登记日的|公司)?总股本(?:[（(]含回购股份[）)])?折算的?每股现金(?:分红|红利)'
        r'[^。;；]{0,280}?=([0-9]+(?:\.[0-9]+)?)元/股',s):
        cash.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_FOLDED_CASH_V482'))

    # V4.82 supplement: an explicit total-cash / total-shares calculation is also a
    # valid effective per-share term when the final result is written in 元/股.
    for m in re.finditer(
        r'每股现金红利=本次实际现金分红总金额/(?:公司)?总股本'
        r'[^。;；]{0,280}?=([0-9]+(?:\.[0-9]+)?)元/股',s):
        cash.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_CASH_CALC_V482'))

    # Some A-share announcements publish the effective amount as a per-10-share
    # figure over the A-share ex-right total; convert that explicit folded value to
    # a per-share cash term.  Nominal "每10股派X" plans do not match this guarded form.
    for m in re.finditer(
        r'按A股除权前总股本[^。;；]{0,260}?每10股派息(?:[（(]含税[）)])?[:：]?'
        r'([0-9]+(?:\.[0-9]+)?)元',s):
        cash.append((float(m.group(1))/10.0,'EXPLICIT_A_SHARE_FOLDED_CASH_PER10_V482'))

    # Formula parameter D is accepted only when the nearby announcement text calls it
    # virtual/effective distribution, so ordinary nominal D statements are not promoted.
    for m in re.finditer(r'D为每股派发现金红利([0-9]+(?:\.[0-9]+)?)元/股(?P<context>.{0,100})',s):
        if '虚拟分派' in m.group('context') or '虚拟现金' in m.group('context'):
            cash.append((float(m.group(1)),'EXPLICIT_VIRTUAL_CASH_PARAMETER'))

    # Explicit virtual/effective capitalization ratio n used in the ex-right formula.
    for m in re.finditer(r'n为每股(?:转增股本|分派的送转比例)([0-9]+(?:\.[0-9]+)?)股(?P<context>.{0,120})',s):
        if '虚拟流通股份变动比例' in m.group('context') or '虚拟' in m.group('context'):
            cap.append((float(m.group(1)),'EXPLICIT_VIRTUAL_CAP_RATIO'))

    for m in re.finditer(r'按(?:公司)?总股本折算每股(?:资本公积金)?转增(?:股本|股份)比例[^。;；]*?=([0-9]+(?:\.[0-9]+)?)股',s):
        cap.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_FOLDED_CAP_RATIO'))

    cash_v,cash_kind,cash_all=_unique_value(cash,'cash')
    cap_v,cap_kind,cap_all=_unique_value(cap,'capitalization')
    return {
        'cash_per_share':cash_v,
        'cap_ratio':cap_v,
        'cash_evidence_kind':cash_kind,
        'cap_evidence_kind':cap_kind,
        'cash_candidates':cash_all,
        'cap_candidates':cap_all,
    }
