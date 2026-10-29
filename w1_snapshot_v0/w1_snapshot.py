"""W1 close snapshot v0: read-only, memory-only pending W6 ADR-004.

No storage of prices, raw responses or digests; no production or credential writes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

CHINA = ZoneInfo('Asia/Shanghai')
SUNSET_HOLDOUT_LABEL = 'RULE_FREEZE_BEFORE_NO_VIEW'
HOLDOUT_START = '2026-04-18'
CORE13 = ('000063.SZ','000636.SZ','000938.SZ','000977.SZ',
          '002138.SZ','002156.SZ','600392.SH','600487.SH',
          '600522.SH','600667.SH','600703.SH','601991.SH','605358.SH')
REQUIRED_BAO = ('date','code','open','high','low','close','preclose',
                'volume','amount','adjustflag','tradestatus','isST')
BAO_FIELDS = ','.join(REQUIRED_BAO)

def _decimal(value: object, field: str) -> str:
    try:
        d = Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError) as exc:
        raise ValueError(f'invalid {field}') from exc
    if not d.is_finite() or d < 0:
        raise ValueError(f'invalid {field}')
    return format(d,'f')

def to_bao_symbol(symbol: str) -> str:
    code,market = symbol.split('.')
    if len(code)!=6 or not code.isdigit() or market not in ('SH','SZ'):
        raise ValueError('unsupported stock symbol')
    return market.lower()+'.'+code

def normalize_bao_row(symbol: str,row: dict) -> dict:
    if any(k not in row for k in REQUIRED_BAO):
        raise ValueError('missing required BaoStock fields')
    if row['code']!=to_bao_symbol(symbol):
        raise ValueError('symbol/source mismatch')
    if row['adjustflag']!='3':
        raise ValueError('unadjusted required')
    if row['tradestatus'] not in ('0','1') or row['isST'] not in ('0','1'):
        raise ValueError('invalid ST/trade state')
    datetime.fromisoformat(row['date']).date()
    values={k:_decimal(row[k],k) for k in
            ('open','high','low','close','preclose','volume','amount')}
    if any(Decimal(values[k])>Decimal(values['high']) for k in ('open','close','low')):
        raise ValueError('invalid OHLC high')
    if any(Decimal(values[k])<Decimal(values['low']) for k in ('open','close','high')):
        raise ValueError('invalid OHLC low')
    if Decimal(values['volume'])!=Decimal(values['volume']).to_integral_value():
        raise ValueError('volume not integer shares')
    return {'trade_date':row['date'],'symbol':symbol,'source':'BaoStock',
            'adjustment':'none','open':values['open'],'high':values['high'],
            'low':values['low'],'close':values['close'],'preclose':values['preclose'],
            'volume_shares':values['volume'],'amount_cny':values['amount'],
            'tradestatus_raw':row['tradestatus'],'isST_raw':row['isST']}

def canonical_hash(rows: list[dict]) -> str:
    """Canonical normalized-row SHA-256; NOT provider raw-byte SHA-256."""
    keys=[(r['trade_date'],r['symbol']) for r in rows]
    if len(set(keys))!=len(keys):
        raise ValueError('duplicate symbol-date')
    payload={'schema':'w1-close-v0/1',
             'rows':sorted(rows,key=lambda r:(r['trade_date'],r['symbol']))}
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,
                   separators=(',',':'),allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def _local_dt(value: str) -> datetime:
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timezone required')
    return dt.astimezone(CHINA)

def derive_d_status(row: dict,known_at: str,official_up_limit: str|None=None,
                    verified_official_limit: bool=False,
                    d_isst_authority: bool=False) -> dict:
    """D semantics; BaoStock indicators are not the formal D PIT-ST authority."""
    dt=_local_dt(known_at)
    if dt.date().isoformat()!=row['trade_date'] or dt.time()<time(15):
        raise ValueError('known_at must be same-date after close')
    is_st=row['isST_raw']=='1'; tradable=row['tradestatus_raw']=='1'
    if not tradable:
        up=False; eligible=False
        source_state='D_SOURCE_UNBOUND' if not d_isst_authority else 'D_NONTRADABLE'
    elif not verified_official_limit or official_up_limit is None:
        up=None; eligible=None; source_state='D_UPPER_LIMIT_SOURCE_UNBOUND'
    else:
        up=Decimal(row['close'])==Decimal(_decimal(official_up_limit,'official_up_limit'))
        eligible=((not is_st) and (not up)) if d_isst_authority else None
        source_state='D_FULLY_BOUND' if d_isst_authority else 'D_ISST_AUTHORITY_UNBOUND'
    return {'known_at':dt.isoformat(),'is_st':is_st,'tradable':tradable,
            'upper_limit':up,'status_entry_eligible':eligible,'status_contract':source_state}

def compare_longbridge(row: dict,latest: dict) -> dict:
    """Only OHLC crosscheck. Do not assume source volume units are equivalent."""
    if latest.get('symbol') not in (None,row['symbol']):
        return {'status':'SYMBOL_MISMATCH'}
    date=_local_dt(latest['timestamp']).date().isoformat()
    if date!=row['trade_date']:
        return {'status':'STALE_DATE','local_trade_date':date}
    try:
        match=all(Decimal(row[k])==Decimal(_decimal(latest[k],k))
                  for k in ('open','high','low','close'))
    except (ValueError,KeyError):
        return {'status':'INVALID_CROSSCHECK','local_trade_date':date}
    return {'status':'MATCH' if match else 'MISMATCH','local_trade_date':date}

def expected_holdout_dates(market_sessions: list[str]) -> list[str]:
    return sorted(set(d for d in market_sessions if d>=HOLDOUT_START))

def make_snapshot(trade_date: str,universe: list[str],rows: list[dict],
                  collected_at: str,crosschecks: dict) -> dict:
    collected=_local_dt(collected_at)
    if collected.date().isoformat()!=trade_date or collected.time()<time(15):
        raise ValueError('must collect on trade date after close')
    pairs=[(r['symbol'],r['trade_date']) for r in rows]
    if len(pairs)!=len(set(pairs)):
        raise ValueError('duplicate symbol-date')
    if any(r['trade_date']!=trade_date or r['symbol'] not in universe for r in rows):
        raise ValueError('out of scope rows')
    missing=sorted(set(universe)-{r['symbol'] for r in rows})
    cross_bad=sorted(s for s in universe if crosschecks.get(s,{}).get('status')!='MATCH')
    complete=not missing and not cross_bad
    return {'schema':'w1-snapshot-metadata/v0','trade_date':trade_date,
            'universe':'Core13_PROVISIONAL','expected_symbols':len(universe),
            'bao_rows':len(rows),
            'longbridge_crosscheck_matches':len(universe)-len(cross_bad),
            'missing_symbols':missing,'crosscheck_missing_or_mismatch':cross_bad,
            'holdout':SUNSET_HOLDOUT_LABEL,
            'state':'READY_TO_SEAL_NOT_PERSISTED' if complete else 'INCOMPLETE',
            'storage_decision':'ADR-004_PENDING','official_d_status':'NOT_VERIFIED'}

def query_baostock_in_memory(symbol: str,start: str,end: str) -> list[dict]:
    """Anonymous BaoStock API only, optional package, never disk."""
    try:
        import baostock as bs
    except ImportError as exc:
        raise RuntimeError('BAOSTOCK_RUNTIME_UNAVAILABLE') from exc
    lg=bs.login()
    if lg.error_code!='0':
        raise RuntimeError('BAOSTOCK_LOGIN_FAILED')
    try:
        rs=bs.query_history_k_data_plus(to_bao_symbol(symbol),BAO_FIELDS,
             start_date=start,end_date=end,frequency='d',adjustflag='3')
        if rs.error_code!='0':
            raise RuntimeError('BAOSTOCK_QUERY_FAILED')
        rows=[]
        while rs.next():
            values=rs.get_row_data()
            rows.append(normalize_bao_row(symbol,dict(zip(rs.fields,values))))
        return rows
    finally:
        bs.logout()
