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


def _price_formula_terms(s: str) -> tuple[list[tuple[float,str]],list[tuple[float,str]]]:
    cash=[]
    cap=[]

    # A/B share issuers can publish two valid price formulas in one announcement.
    # Formal scope here is the A-share symbol, so an explicit A-share closing-price
    # formula takes precedence over the generic formula and the B-share formula.
    a_share=[]
    for m in re.finditer(r'(?:股权登记日)?A股收盘价[-－]([0-9]+(?:\.[0-9]+)?)(?:元/股|元)?',s):
        if '除权' in s[max(0,m.start()-300):m.start()]:
            a_share.append((float(m.group(1)),'EXPLICIT_A_SHARE_PRICE_FORMULA_CASH'))
    if a_share:
        cash.extend(a_share)
    else:
        # Require an explicit closing-price subtraction and nearby ex-right/ex-dividend
        # context. This intentionally does not match unrelated later formulas such as
        # repurchase-price-limit adjustments.
        for m in re.finditer(r'(?<!B股)(?:(?:股权登记日|除权前一交易日|前一交易日|前)?)收盘价[-－]([0-9]+(?:\.[0-9]+)?)(?:元/股|元)?',s):
            if '除权' in s[max(0,m.start()-300):m.start()]:
                cash.append((float(m.group(1)),'EXPLICIT_PRICE_FORMULA_CASH'))

    # Explicit divisor in an ex-right price formula. Percent form is converted to a
    # per-share capitalization ratio. The nearby "除权" guard prevents unrelated
    # accounting/valuation formulae elsewhere in the announcement from being promoted.
    for m in re.finditer(r'(?:/|÷)[（(]?1\+([0-9]+(?:\.[0-9]+)?)(%)?[）)]?',s):
        if '除权' not in s[max(0,m.start()-450):m.start()]:
            continue
        v=float(m.group(1))
        if m.group(2):
            v/=100.0
        cap.append((v,'EXPLICIT_PRICE_FORMULA_CAP_RATIO'))

    return cash,cap


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

    formula_cash,formula_cap=_price_formula_terms(s)
    cash.extend(formula_cash)
    cap.extend(formula_cap)

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
