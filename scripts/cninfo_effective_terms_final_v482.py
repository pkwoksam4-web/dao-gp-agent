from __future__ import annotations

import re

import cninfo_effective_terms_v481 as legacy
import effective_term_closure_v482 as closure


def _norm(text: str) -> str:
    s = str(text or '')
    s = s.replace('\u3000', ' ').replace('\xa0', ' ')
    s = re.sub(r'\s+', '', s)
    s = s.replace('，', ',').replace('。', '.')
    return s


def _set_cash(out: dict, value: float, kind: str) -> None:
    value = float(value)
    old = out.get('cash_per_share')
    if old is not None and abs(float(old) - value) > 1e-7:
        raise ValueError(f'conflicting final explicit cash values: old={old}, new={value}')
    out['cash_per_share'] = value
    out['cash_evidence_kind'] = kind
    candidates = list(out.get('cash_candidates') or [])
    if not any(abs(float(x.get('value')) - value) <= 1e-7 and x.get('kind') == kind for x in candidates):
        candidates.append({'value': value, 'kind': kind})
    out['cash_candidates'] = candidates


def _set_cap(out: dict, value: float, kind: str, *, allow_formula_rescale: bool = False) -> None:
    value = float(value)
    old = out.get('cap_ratio')
    if old is not None and abs(float(old) - value) > 1e-7:
        if not allow_formula_rescale:
            raise ValueError(f'conflicting final explicit cap values: old={old}, new={value}')
        old_kind = str(out.get('cap_evidence_kind') or '')
        if 'FORMULA' not in old_kind:
            raise ValueError(f'cannot rescale non-formula cap evidence: {old_kind}')
    out['cap_ratio'] = value
    out['cap_evidence_kind'] = kind
    candidates = list(out.get('cap_candidates') or [])
    candidates.append({'value': value, 'kind': kind})
    out['cap_candidates'] = candidates


def extract_effective_terms(text: str) -> dict:
    """V4.82 final guarded parser layered over the frozen legacy parser.

    New evidence is promoted only from explicit ex-right/ex-dividend calculation text.
    The formula_share_change_ratio field represents the *total* share-change ratio in
    an official numerical denominator ``1+n`` and therefore must replace, not add to,
    nominal stock/capitalization ratios in corrected_event_ratio().
    """
    out = dict(legacy.extract_effective_terms(text))
    s = _norm(text)

    # A/B-share issuers may print the A-share effective cash only in the final A-share
    # ex-dividend-price equation. This is stronger evidence than the nominal dividend.
    for m in re.finditer(
        r'A股除权除息(?:价格|参考价)(?:计算)?[^。;；]{0,260}?='
        r'股权登记日A股收盘价[-－﹣]([0-9]+(?:\.[0-9]+)?)元/股',
        s,
    ):
        _set_cash(out, float(m.group(1)), 'EXPLICIT_A_SHARE_FINAL_EXRIGHT_CASH_V482')

    # Repurchase-adjusted cash-only notices often publish the final effective amount
    # per 10 shares. Convert only the explicit "应以 X 元计算" ex-right wording.
    for m in re.finditer(r'每10股现金红利应以([0-9]+(?:\.[0-9]+)?)元计算', s):
        prior = s[max(0, m.start() - 700):m.start()]
        after = s[m.end():m.end() + 500]
        if '除权' not in prior + after and '除息' not in prior + after:
            continue
        _set_cash(out, float(m.group(1)) / 10.0, 'EXPLICIT_EFFECTIVE_CASH_PER10_V482')

    # Official numerical denominator with a percent sign: legacy regex captures the
    # printed percentage as a unitless ratio (e.g. 19.842072 instead of 0.19842072).
    # Scale it explicitly and record it as the total formula share-change ratio.
    percent_matches = []
    for m in re.finditer(r'(?:/|÷)[（(]?1\+([0-9]+(?:\.[0-9]+)?)%[）)]?', s):
        prior = s[max(0, m.start() - 600):m.start()]
        if '除权' not in prior and '除息' not in prior:
            continue
        percent_matches.append(float(m.group(1)) / 100.0)
    if percent_matches:
        values = []
        for v in percent_matches:
            if not any(abs(v - x) <= 1e-9 for x in values):
                values.append(v)
        if len(values) != 1:
            raise ValueError(f'conflicting percent formula share-change ratios: {values}')
        v = values[0]
        _set_cap(out, v, 'EXPLICIT_PERCENT_FORMULA_SHARE_CHANGE_V482', allow_formula_rescale=True)
        out['formula_share_change_ratio'] = v
        out['formula_share_change_evidence_kind'] = 'EXPLICIT_PERCENT_FORMULA_SHARE_CHANGE_V482'
    else:
        # Non-percent explicit denominator. Keep legacy cap output for backwards
        # compatibility, but also mark the number as the total formula share-change
        # ratio so stock dividends are not double-counted as stock+cap.
        vals = []
        for m in re.finditer(r'(?:/|÷)[（(]?1\+([0-9]+(?:\.[0-9]+)?)[）)]?', s):
            # Do not accept the numeric prefix of a percentage expression.
            tail = s[m.end():m.end() + 1]
            if tail == '%':
                continue
            prior = s[max(0, m.start() - 600):m.start()]
            if '除权' not in prior and '除息' not in prior:
                continue
            v = float(m.group(1))
            if not any(abs(v - x) <= 1e-9 for x in vals):
                vals.append(v)
        if vals:
            if len(vals) != 1:
                raise ValueError(f'conflicting formula share-change ratios: {vals}')
            out['formula_share_change_ratio'] = vals[0]
            out['formula_share_change_evidence_kind'] = 'EXPLICIT_FORMULA_TOTAL_SHARE_CHANGE_V482'
        else:
            out['formula_share_change_ratio'] = None
            out['formula_share_change_evidence_kind'] = None

    return out


def corrected_event_ratio(event: dict, terms: dict) -> float:
    formula_change = terms.get('formula_share_change_ratio')
    if formula_change is None:
        return closure.corrected_event_ratio(event, terms)

    prev = closure._positive(event.get('prev_actual_close'), 'prev_actual_close')
    cash = terms.get('cash_per_share')
    if cash is None:
        cash = float(event.get('cash_per_share_nominal') or 0.0)
    cash = float(cash)
    share_change = float(formula_change)
    rights = float(event.get('rights_ratio') or 0.0)
    rights_price = event.get('rights_price')
    if min(cash, share_change, rights) < 0:
        raise ValueError('negative distribution/formula term')
    if rights > 0 and rights_price in (None, ''):
        raise ValueError('rights issue missing price')
    rights_term = 0.0 if rights == 0 else rights * closure._positive(rights_price, 'rights_price')
    # The announcement's explicit denominator is already the TOTAL share-change
    # ratio. Do not add nominal stock_ratio/capitalization_ratio again.
    shares = 1.0 + share_change
    ex_ref = (prev - cash + rights_term) / shares
    if ex_ref <= 0:
        raise ValueError('invalid corrected ex-right reference price')
    return ex_ref / prev
