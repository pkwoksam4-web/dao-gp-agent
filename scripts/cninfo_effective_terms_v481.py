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


def _comma_int(s: str) -> int:
    return int(str(s).replace(',',''))


def _same_clause_prefix(s: str, start: int, window: int=260) -> str:
    prefix=s[max(0,start-window):start]
    cut=max(prefix.rfind('.'),prefix.rfind(';'),prefix.rfind('；'))
    return prefix[cut+1:]


def _in_repurchase_price_ceiling_context(s: str, start: int) -> bool:
    clause=_same_clause_prefix(s,start)
    return '回购' in clause and '价格上限' in clause


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
        if _in_repurchase_price_ceiling_context(s,m.start()):
            continue
        cash.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_FOLDED_CASH'))

    # V4.82 supplement: many implementation announcements state the final ex-right
    # formula explicitly as "record-date close - effective cash" but put the folded
    # cash calculation much earlier in the paragraph. Accept the numeric subtraction
    # only when nearby text is clearly about ex-right/ex-dividend pricing. If the
    # subtraction is followed by a non-trivial /(1+n) denominator, do not promote the
    # cash alone; that event requires a separately extracted capitalization ratio.
    # Some issuers write 收盘价格 instead of 收盘价; both are explicit formula terms.
    for m in re.finditer(r'(?:股权登记日|权益分派股权登记日|除权除息前一交易日|前)收盘价(?:格)?[-－]([0-9]+(?:\.[0-9]+)?)(?:元/股|元)?',s):
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
        if _in_repurchase_price_ceiling_context(s,m.start()):
            continue
        cash.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_FOLDED_CASH_V482'))

    # V4.82 supplement: an explicit total-cash / total-shares calculation is also a
    # valid effective per-share term when the final result is written in 元/股.
    for m in re.finditer(
        r'每股现金红利=本次实际现金分红总金额/(?:公司)?总股本'
        r'[^。;；]{0,280}?=([0-9]+(?:\.[0-9]+)?)元/股',s):
        cash.append((float(m.group(1)),'EXPLICIT_TOTAL_SHARE_CASH_CALC_V482'))

    # V4.82 secondary closure: a number of official implementation announcements use
    # the shorter guarded form "折算每股现金红利=...=X元/股". Promote only when the
    # nearby context explicitly discusses ex-right/ex-dividend pricing, so a nominal
    # distribution plan cannot match this rule.
    for m in re.finditer(
        r'折算(?:后的?)?每股现金(?:红利|分红)[^。;；]{0,360}?(?:=|≈)([0-9]+(?:\.[0-9]+)?)元/股',s):
        prior=s[max(0,m.start()-700):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        if _in_repurchase_price_ceiling_context(s,m.start()):
            continue
        cash.append((float(m.group(1)),'EXPLICIT_FOLDED_CASH_PER_SHARE_V482'))

    # Some A-share announcements publish the effective amount as a per-10-share
    # figure over the A-share ex-right total; convert that explicit folded value to
    # a per-share cash term. Nominal "每10股派X" plans do not match this guarded form.
    for m in re.finditer(
        r'按A股除权前总股本[^。;；]{0,260}?每10股派息(?:[（(]含税[）)])?[:：]?'
        r'([0-9]+(?:\.[0-9]+)?)元',s):
        cash.append((float(m.group(1))/10.0,'EXPLICIT_A_SHARE_FOLDED_CASH_PER10_V482'))

    # V4.82 secondary closure: some A/B-share issuers explicitly print the A-share
    # effective cash in the A-share ex-dividend-price section. This guarded A-share
    # wording prevents a B-share cash conversion elsewhere in the same notice from
    # being promoted into the A-share factor path.
    for m in re.finditer(
        r'A股除权除息价格计算时[^。;；]{0,220}?每股现金红利=现金分红总额/(?:公司)?总股本[,，]?(?:即|=)?'
        r'([0-9]+(?:\.[0-9]+)?)元/股',s):
        cash.append((float(m.group(1)),'EXPLICIT_A_SHARE_EFFECTIVE_CASH_V482'))

    # A/H-share issuers with repurchased A shares can keep the nominal per-share
    # distribution unchanged for participating holders while the A-share ex-dividend
    # price is calculated over all listed A shares. Derive the effective A-share cash
    # only when one implementation announcement supplies all four guarded inputs:
    # total company shares, participating A/H shares, and the nominal per-10 cash.
    if 'A股权益分派实施公告' in s and '回购股份不参与本次权益分派' in s:
        total_m=re.search(r'公司总股本未发生变化,?为([0-9][0-9,]*)股',s)
        part_m=re.search(r'总股份数为([0-9][0-9,]*)股,?其中A股([0-9][0-9,]*)股、H股([0-9][0-9,]*)股',s)
        cash_m=re.search(r'每10股派发现金红利(?:人民币)?([0-9]+(?:\.[0-9]+)?)元',s)
        if total_m and part_m and cash_m:
            total=_comma_int(total_m.group(1))
            participating_total=_comma_int(part_m.group(1))
            participating_a=_comma_int(part_m.group(2))
            participating_h=_comma_int(part_m.group(3))
            if participating_a+participating_h != participating_total:
                raise ValueError('A/H participating-share partition mismatch')
            all_a=total-participating_h
            if not (0 < participating_a <= all_a <= total):
                raise ValueError('invalid A-share fold denominator')
            nominal=float(cash_m.group(1))/10.0
            cash.append((nominal*participating_a/all_a,'DERIVED_A_SHARE_FOLDED_CASH_FROM_REPURCHASE_V482'))

    # V4.82 secondary closure: differential-dividend notices often state the final
    # computed virtual/effective cash as "(虚拟分派的)每股现金红利=...≈X元/股".
    # Require nearby differential-dividend plus ex-right/ex-dividend context.
    for m in re.finditer(
        r'(?:虚拟分派的)?每股现金红利=[^。;；]{0,520}?(?:=|≈)([0-9]+(?:\.[0-9]+)?)元/股',s):
        prior=s[max(0,m.start()-900):m.start()]
        if '差异化分红' not in prior:
            continue
        if '除权' not in prior and '除息' not in prior:
            continue
        cash.append((float(m.group(1)),'EXPLICIT_DIFFERENTIAL_FOLDED_CASH_V482'))

    # V4.82 secondary closure: some differential-dividend announcements publish the
    # folded value per 10 shares, not per share. The official formula may print the
    # computed value after a literal "即" inside parentheses; allow that form too.
    # Nominal per-10 distribution plans still do not match because "折算后的" and
    # ex-right/ex-dividend context are required.
    for m in re.finditer(
        r'折算后的?每10股现金(?:股利|红利|分红)[^。;；]{0,420}?(?:即|=|≈)([0-9]+(?:\.[0-9]+)?)元',s):
        prior=s[max(0,m.start()-800):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        cash.append((float(m.group(1))/10.0,'EXPLICIT_FOLDED_CASH_PER10_V482'))

    # Some official implementation notices state the subtraction symbolically and
    # then give the effective cash in parentheses: "每股派发现金红利金额（即X元）".
    for m in re.finditer(
        r'除权除息参考价(?:格)?=[^。;；]{0,260}?每股派发现金红利金额[（(]即'
        r'([0-9]+(?:\.[0-9]+)?)元(?:/股)?[）)]',s):
        cash.append((float(m.group(1)),'EXPLICIT_PARENTHETICAL_EFFECTIVE_CASH_V482'))

    # V4.82 supplement: when the implementation announcement prints the complete
    # numerical ex-right formula, cash and capitalization are a coupled evidence pair.
    # Both values are promoted together; symbolic-only formulae are deliberately ignored.
    coupled_pattern=(
        r'[（(]?(?:(?:股权登记日|除权除息前一交易日)(?:股票)?收盘价)'
        r'[-－﹣]([0-9]+(?:\.[0-9]+)?)(?:元/股)?[）)]?'
        r'(?:/|÷)[（(]?1\+([0-9]+(?:\.[0-9]+)?)[）)]?'
    )
    for m in re.finditer(coupled_pattern,s):
        prior=s[max(0,m.start()-500):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        cash.append((float(m.group(1)),'EXPLICIT_COUPLED_EXRIGHT_FORMULA_CASH_V482'))
        cap.append((float(m.group(2)),'EXPLICIT_COUPLED_EXRIGHT_FORMULA_CAP_V482'))

    # Cap-only numerical denominator in an explicit ex-right/ex-dividend formula.
    # This covers no-cash capitalization events such as record-date-close/(1+n).
    for m in re.finditer(r'(?:/|÷)[（(]?1\+([0-9]+(?:\.[0-9]+)?)[）)]?',s):
        prior=s[max(0,m.start()-500):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        cap.append((float(m.group(1)),'EXPLICIT_PRICE_FORMULA_CAP_RATIO_V482'))

    # Explicit effective per-share capitalization ratio used for ex-right pricing.
    for m in re.finditer(r'每股(?:资本公积金)?转增(?:股本)?比例应以([0-9]+(?:\.[0-9]+)?)计算',s):
        prior=s[max(0,m.start()-500):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        cap.append((float(m.group(1)),'EXPLICIT_EFFECTIVE_CAP_RATIO_V482'))

    # Some cash-only implementation announcements state the effective folded cash
    # in parentheses after a symbolic subtraction term.
    for m in re.finditer(r'每股现金(?:红利|分红)[（(]([0-9]+(?:\.[0-9]+)?)元/股[）)]',s):
        prior=s[max(0,m.start()-500):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        cash.append((float(m.group(1)),'EXPLICIT_PARENTHETICAL_FOLDED_CASH_V482'))

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
