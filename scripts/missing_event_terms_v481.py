from __future__ import annotations

import math
import re


def _number(pattern: str, text: str) -> float:
    m=re.search(pattern,text)
    if not m:
        return 0.0
    x=float(m.group(1))
    if not math.isfinite(x) or x < 0:
        raise ValueError(f'invalid implementation term numeric value: {m.group(1)!r}')
    return x


def parse_impl_plan_profile(text: str) -> dict:
    """Parse implemented Chinese per-10-share bonus terms into per-share Action terms.

    Supported grammar is deliberately narrow: 10送X / 10转X / 派Y元, including
    combinations. Rights issues, non-allocation strings, and non-10 bases fail closed.
    """
    s=re.sub(r'\s+','',str(text or '').strip())
    if not s or not s.startswith('10'):
        raise ValueError(f'unsupported implementation profile: {text!r}')
    if any(token in s for token in ('配','不分配','不转增')):
        raise ValueError(f'unsupported implementation profile: {text!r}')

    stock=_number(r'送([0-9]+(?:\.[0-9]+)?)',s)
    cap=_number(r'转(?:增)?([0-9]+(?:\.[0-9]+)?)',s)
    cash=_number(r'派([0-9]+(?:\.[0-9]+)?)元',s)
    if stock==0 and cap==0 and cash==0:
        raise ValueError(f'unrecognized implementation profile: {text!r}')

    # Ensure no unrecognized action tokens remain hidden in otherwise parseable text.
    allowed=re.fullmatch(
        r'10(?:送[0-9]+(?:\.[0-9]+)?)?(?:股)?(?:转(?:增)?[0-9]+(?:\.[0-9]+)?)?(?:股)?(?:派[0-9]+(?:\.[0-9]+)?元)?(?:\(含税\))?',
        s,
    )
    if not allowed:
        raise ValueError(f'profile contains unsupported syntax: {text!r}')

    return {
        'cash_per_share':cash/10.0,
        'stock_ratio':stock/10.0,
        'capitalization_ratio':cap/10.0,
        'rights_ratio':0.0,
        'rights_price':None,
        'source_text':text,
    }
