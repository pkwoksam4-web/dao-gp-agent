from __future__ import annotations
from dataclasses import dataclass
import json, math, re
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class Action:
    symbol: str
    ex_date: str
    cash_per_share: float = 0.0
    stock_ratio: float = 0.0
    cap_ratio: float = 0.0
    rights_ratio: float = 0.0
    rights_price: float | None = None
    source: str = ''


def _num(v, default=0.0):
    if v in (None, '', '-', '--'):
        return default
    x=float(v)
    if not math.isfinite(x):
        raise ValueError(f'non-finite numeric value: {v!r}')
    return x


def _date(v) -> str:
    s=str(v or '')[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        raise ValueError(f'invalid date: {v!r}')
    date.fromisoformat(s)
    return s


def normalize_sharebonus_rows(symbol: str, rows: Iterable[dict]) -> list[Action]:
    out=[]
    for r in rows:
        if not r.get('EX_DIVIDEND_DATE'):
            continue
        cash=_num(r.get('PRETAX_BONUS_RMB'))/10.0
        stock=_num(r.get('BONUS_RATIO'))/10.0
        cap=_num(r.get('IT_RATIO'))/10.0
        if min(cash,stock,cap) < 0:
            raise ValueError('negative share-bonus term')
        if cash==0 and stock==0 and cap==0:
            continue
        out.append(Action(symbol=symbol, ex_date=_date(r['EX_DIVIDEND_DATE']), cash_per_share=cash,
                          stock_ratio=stock, cap_ratio=cap, source='EASTMONEY_RPT_SHAREBONUS_DET'))
    return out


def normalize_rights_rows(symbol: str, rows: Iterable[dict]) -> list[Action]:
    out=[]
    for r in rows:
        if not r.get('EX_DIVIDEND_DATE'):
            continue
        ratio=_num(r.get('PLACING_RATIO'))/10.0
        if ratio < 0:
            raise ValueError('negative rights ratio')
        if ratio == 0:
            continue
        price=r.get('ISSUE_PRICE')
        if price in (None,'','-','--'):
            raise ValueError('rights issue requires ISSUE_PRICE')
        price=_num(price)
        if price <= 0:
            raise ValueError('rights issue requires positive ISSUE_PRICE')
        out.append(Action(symbol=symbol, ex_date=_date(r['EX_DIVIDEND_DATE']), rights_ratio=ratio,
                          rights_price=price, source='EASTMONEY_RPT_IPO_ALLOTMENT'))
    return out


def merge_actions(actions: Iterable[Action]) -> list[Action]:
    by={}
    for a in actions:
        k=(a.symbol,a.ex_date)
        if k not in by:
            by[k]={'cash':0.0,'stock':0.0,'cap':0.0,'rights':0.0,'prices':set(),'sources':set()}
        x=by[k]
        x['cash'] += a.cash_per_share
        x['stock'] += a.stock_ratio
        x['cap'] += a.cap_ratio
        x['rights'] += a.rights_ratio
        if a.rights_ratio:
            if a.rights_price is None:
                raise ValueError('rights issue missing price')
            x['prices'].add(round(float(a.rights_price),12))
        if a.source: x['sources'].add(a.source)
    out=[]
    for (symbol,ex),x in sorted(by.items(), key=lambda kv: kv[0][1]):
        if len(x['prices']) > 1:
            raise ValueError(f'ambiguous rights prices {symbol} {ex}: {x["prices"]}')
        price=next(iter(x['prices'])) if x['prices'] else None
        out.append(Action(symbol=symbol,ex_date=ex,cash_per_share=x['cash'],stock_ratio=x['stock'],cap_ratio=x['cap'],
                          rights_ratio=x['rights'],rights_price=price,source='+'.join(sorted(x['sources']))))
    return out


def parse_sohu_history_bytes(raw: bytes) -> list[dict]:
    text=None
    for enc in ('utf-8','gb18030'):
        try:
            text=raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        raise ValueError('Sohu payload decode failed')
    m=re.match(r'^\s*historySearchHandler\((.*)\)\s*;?\s*$', text, re.S)
    if not m:
        raise ValueError('Sohu JSONP wrapper mismatch')
    payload=json.loads(m.group(1))
    if not isinstance(payload,list) or not payload:
        raise ValueError('Sohu payload missing list')
    block=payload[0]
    if int(block.get('status',-1)) != 0 or not isinstance(block.get('hq'),list):
        raise ValueError(f'Sohu status/data invalid: {block.get("status")}')
    rows=[]
    for r in block['hq']:
        if not isinstance(r,list) or len(r)<3:
            continue
        d=_date(r[0]); close=_num(r[2], None)
        if close is None or close <= 0: raise ValueError(f'invalid Sohu close {d}')
        rows.append({'date':d,'open':_num(r[1]),'close':close,
                     'low':_num(r[5]) if len(r)>5 else None,
                     'high':_num(r[6]) if len(r)>6 else None})
    rows.sort(key=lambda x:x['date'])
    return rows


def prev_close_before(rows: list[dict], ex_date: str) -> float:
    ex=_date(ex_date); found=None
    for r in rows:
        if r['date'] < ex:
            found=float(r['close'])
        else:
            break
    if found is None:
        raise ValueError(f'NO_ACTUAL_PREV_CLOSE before {ex}')
    return found


def parse_sina_qfq(raw: bytes) -> list[dict]:
    text=raw.decode('utf-8',errors='strict')
    m=re.search(r'=\s*(\{.*\})\s*;?\s*(?:/\*.*)?$', text, re.S)
    if not m:
        raise ValueError('Sina qfq JS object not found')
    obj=json.loads(m.group(1))
    data=obj.get('data')
    if not isinstance(data,list) or not data:
        raise ValueError('Sina qfq missing data[]')
    out=[]
    for r in data:
        d=_date(r.get('d') if isinstance(r,dict) else r[0])
        f=_num(r.get('f') if isinstance(r,dict) else r[1])
        if f<=0: raise ValueError('Sina divisor must be positive')
        out.append({'date':d,'factor':f})
    out.sort(key=lambda x:x['date'])
    return out


def factor_for_date(factors: list[dict], d: str) -> float:
    d=_date(d); out=None
    for r in factors:
        if r['date'] <= d:
            out=float(r['factor'])
        else:
            break
    if out is None:
        raise ValueError(f'no Sina factor covering {d}')
    return out


def sina_normalized_for_date(factors: list[dict], d: str, anchor: str) -> float:
    return factor_for_date(factors,anchor)/factor_for_date(factors,d)


def event_ratio(action: Action, prev_close: float) -> float:
    p=float(prev_close)
    if p<=0: raise ValueError('prev_close must be positive')
    if action.rights_ratio>0 and action.rights_price is None:
        raise ValueError('rights issue missing price')
    rights_term=0.0 if action.rights_ratio==0 else action.rights_ratio*float(action.rights_price)
    shares=1.0+action.stock_ratio+action.cap_ratio+action.rights_ratio
    ex_ref=(p-action.cash_per_share+rights_term)/shares
    if shares<=0 or ex_ref<=0:
        raise ValueError('invalid ex-right reference price')
    return ex_ref/p


def expected_factor_for_date(d: str, actions: list[Action], ratios: dict[str,float], anchor: str) -> float:
    d=_date(d); anchor=_date(anchor); out=1.0
    for a in actions:
        if d < a.ex_date <= anchor:
            out *= float(ratios[a.ex_date])
    return out


def compare_factor_path(rows: list[dict], expected: dict[str,float], actual: dict[str,float], threshold_bp: float=5.0) -> dict:
    diffs=[]; details=[]
    for r in rows:
        d=r['date']
        if d not in expected or d not in actual: continue
        e=float(expected[d]); a=float(actual[d])
        if e<=0 or a<=0: raise ValueError('factor must be positive')
        bp=abs(a/e-1.0)*10000.0
        diffs.append(bp); details.append({'date':d,'expected_factor':e,'sina_factor':a,'diff_bp':bp})
    if not diffs:
        raise ValueError('no comparable factor rows')
    mx=max(diffs)
    return {'status':'PASS' if mx<=threshold_bp else 'FAIL','threshold_bp':threshold_bp,
            'rows':len(diffs),'max_diff_bp':mx,'mean_diff_bp':sum(diffs)/len(diffs),
            'worst_rows':sorted(details,key=lambda x:x['diff_bp'],reverse=True)[:10]}


def parse_eastmoney_report(raw: bytes) -> tuple[list[dict], int]:
    obj=json.loads(raw.decode('utf-8'))
    if obj.get('success') is True and int(obj.get('code',0)) == 0:
        result=obj.get('result') or {}
        rows=result.get('data') or []
        if not isinstance(rows,list):
            raise ValueError('Eastmoney report data is not list')
        pages=int(result.get('pages') or (1 if rows else 0))
        return rows,pages
    if int(obj.get('code',-1)) == 9201:
        return [],0
    raise ValueError(f"Eastmoney report error code={obj.get('code')} message={obj.get('message')}")
