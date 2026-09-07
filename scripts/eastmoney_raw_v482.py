from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
from typing import Iterable

import requests

BASE='https://push2his.eastmoney.com/api/qt/stock/kline/get'
FORMAL_BEG='20200601'
FORMAL_END='20260417'


def normalize_symbol(symbol:str)->str:
    s=str(symbol).strip().upper()
    if '.' not in s:
        raise ValueError(f'exchange-qualified symbol required: {symbol!r}')
    code,ex=s.split('.',1)
    if ex not in {'SZ','SH'} or not code.isdigit():
        raise ValueError(f'unsupported symbol: {symbol!r}')
    return f'{code.zfill(6)}.{ex}'


def symbol_to_secid(symbol:str)->str:
    s=normalize_symbol(symbol)
    code,ex=s.split('.')
    return ('0.' if ex=='SZ' else '1.')+code


def parse_payload(symbol:str,payload:dict)->list[dict]:
    s=normalize_symbol(symbol)
    data=(payload or {}).get('data') if isinstance(payload,dict) else None
    klines=(data or {}).get('klines') if isinstance(data,dict) else None
    if not klines:
        return []
    rows=[]
    for line in klines:
        p=str(line).split(',')
        if len(p)<7:
            continue
        try:
            rows.append({
                'symbol':s,'date':p[0],
                'open':float(p[1]),'close':float(p[2]),'high':float(p[3]),'low':float(p[4]),
                # Eastmoney daily kline volume is 100-share lots; normalize to shares.
                'volume':float(p[5])*100.0,
                'amount':float(p[6]),
                'source':'EASTMONEY_FQT0_RAW',
            })
        except (TypeError,ValueError):
            continue
    return rows


def fetch_symbol(symbol:str,beg:str=FORMAL_BEG,end:str=FORMAL_END,timeout:int=30,retries:int=3)->list[dict]:
    s=normalize_symbol(symbol)
    params={
        'secid':symbol_to_secid(s),'klt':'101','fqt':'0','beg':beg,'end':end,'lmt':'1000000',
        'fields1':'f1,f2,f3,f4,f5,f6',
        'fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
    }
    last=None
    for attempt in range(retries):
        try:
            r=requests.get(BASE,params=params,headers={'User-Agent':'Mozilla/5.0 GP-V4.82'},timeout=timeout)
            r.raise_for_status()
            return parse_payload(s,r.json())
        except Exception as exc:
            last=exc
            if attempt+1<retries:
                time.sleep(1.0*(attempt+1))
    raise RuntimeError(f'Eastmoney fetch failed for {s}: {last}')


def sha256_file(path:pathlib.Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def audit_rows(symbol:str,rows:list[dict])->dict:
    s=normalize_symbol(symbol)
    dates=[r['date'] for r in rows]
    dup_n=len(dates)-len(set(dates))
    bad_ohlc=sum(1 for r in rows if min(r['open'],r['high'],r['low'],r['close'])<=0)
    bad_volume=sum(1 for r in rows if r['volume']<=0)
    bad_amount=sum(1 for r in rows if r['amount']<=0)
    return {
        'symbol':s,'rows':len(rows),
        'first_date':min(dates) if dates else None,
        'last_date':max(dates) if dates else None,
        'duplicate_dates':dup_n,
        'bad_ohlc_rows':bad_ohlc,'bad_volume_rows':bad_volume,'bad_amount_rows':bad_amount,
        'status':'PASS_NONEMPTY_RAW' if rows and dup_n==0 and bad_ohlc==0 else ('EMPTY' if not rows else 'REVIEW'),
    }


def write_csv(path:pathlib.Path,rows:list[dict]):
    import csv
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=['symbol','date','open','high','low','close','volume','amount','source']
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k) for k in fields})


def run_probe(symbols:Iterable[str],out_dir:pathlib.Path,timeout:int=30)->dict:
    out_dir.mkdir(parents=True,exist_ok=True)
    audits=[]; errors=[]
    for symbol in symbols:
        s=normalize_symbol(symbol)
        try:
            rows=fetch_symbol(s,timeout=timeout)
            fp=out_dir/f'{s}.csv'
            write_csv(fp,rows)
            a=audit_rows(s,rows); a['csv']=fp.name; a['sha256']=sha256_file(fp)
            audits.append(a)
            print(json.dumps(a,ensure_ascii=False),flush=True)
        except Exception as exc:
            e={'symbol':s,'type':type(exc).__name__,'message':str(exc)}
            errors.append(e); print(json.dumps(e,ensure_ascii=False),flush=True)
    summary={
        'artifact':'EASTMONEY_RAW_PROBE_V482','version':'V4.82','fqt':0,'klt':101,
        'formal_window':['2020-06-01','2026-04-17'],
        'volume_normalization':'lots_x100_to_shares','amount_unit':'CNY',
        'symbols_requested':len(list(symbols)) if not isinstance(symbols,list) else len(symbols),
        'symbols_fetched':len(audits),'errors':len(errors),
        'nonempty_pass':sum(a['status']=='PASS_NONEMPTY_RAW' for a in audits),
        'audits':audits,'error_details':errors,
        'formal_admission':False,'oos_metrics_allowed':False,
    }
    (out_dir/'EASTMONEY_RAW_PROBE_V482.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--symbol',action='append',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--timeout',type=int,default=30)
    a=ap.parse_args()
    run_probe(a.symbol,pathlib.Path(a.out_dir),a.timeout)

if __name__=='__main__':
    main()
