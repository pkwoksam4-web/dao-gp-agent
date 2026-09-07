from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Iterable

import requests

BASE_HTTPS='https://q.stock.sohu.com/hisHq'
BASE_HTTP='http://q.stock.sohu.com/hisHq'
FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'


def normalize_symbol(symbol:str)->str:
    s=str(symbol).strip().upper()
    if '.' not in s:
        raise ValueError(f'exchange-qualified symbol required: {symbol!r}')
    code,ex=s.split('.',1)
    if ex not in {'SZ','SH'} or not code.isdigit():
        raise ValueError(f'unsupported symbol: {symbol!r}')
    return f'{code.zfill(6)}.{ex}'


def plan_chunks(start:str,end:str,max_calendar_days:int=90)->list[tuple[str,str]]:
    if max_calendar_days < 1:
        raise ValueError('max_calendar_days must be positive')
    a=date.fromisoformat(start); b=date.fromisoformat(end)
    if b<a:
        raise ValueError('end before start')
    out=[]; cur=a
    while cur<=b:
        stop=min(b,cur+timedelta(days=max_calendar_days-1))
        out.append((cur.isoformat(),stop.isoformat()))
        cur=stop+timedelta(days=1)
    return out


def _decode(raw:bytes)->str:
    for enc in ('utf-8-sig','gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    raise ValueError('Sohu payload decode failed')


def parse_hishq_bytes(symbol:str,raw:bytes)->list[dict]:
    s=normalize_symbol(symbol)
    text=_decode(raw).strip()
    m=re.match(r'^\s*historySearchHandler\((.*)\)\s*;?\s*$',text,re.S)
    if not m:
        raise ValueError('Sohu JSONP wrapper mismatch')
    obj=json.loads(m.group(1))
    if not isinstance(obj,list) or not obj:
        return []
    block=obj[0]
    if not isinstance(block,dict) or int(block.get('status',-1)) != 0:
        return []
    hq=block.get('hq') or []
    if not isinstance(hq,list):
        return []
    rows=[]
    for p in hq:
        if not isinstance(p,list) or len(p)<9:
            continue
        try:
            # Sohu hq columns:
            # date, open, close, chg, pct, low, high, volume(lots), amount(10k CNY), turnover.
            rows.append({
                'symbol':s,'date':str(p[0])[:10],
                'open':float(p[1]),'close':float(p[2]),
                'low':float(p[5]),'high':float(p[6]),
                'volume':float(p[7])*100.0,
                'amount':float(p[8])*10_000.0,
                'source':'SOHU_HISHQ_RAW',
            })
        except (TypeError,ValueError):
            continue
    rows.sort(key=lambda r:r['date'])
    return rows


def _request_once(session:requests.Session,symbol:str,start:str,end:str,timeout:int,base:str)->list[dict]:
    code=normalize_symbol(symbol).split('.')[0]
    params={
        'code':f'cn_{code}',
        'start':start.replace('-',''),
        'end':end.replace('-',''),
        'stat':'1','order':'A','period':'d',
        'callback':'historySearchHandler','rt':'jsonp',
    }
    r=session.get(base,params=params,timeout=timeout,headers={
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36',
        'Referer':f'https://q.stock.sohu.com/cn/{code}/lshq.shtml',
        'Connection':'close',
        'Accept':'*/*',
    })
    r.raise_for_status()
    return parse_hishq_bytes(symbol,r.content)


def fetch_chunk(session:requests.Session,symbol:str,start:str,end:str,timeout:int=20,retries:int=3)->list[dict]:
    last=None
    for attempt in range(1,retries+1):
        for base in (BASE_HTTPS,BASE_HTTP):
            try:
                return _request_once(session,symbol,start,end,timeout,base)
            except Exception as exc:
                last=exc
        if attempt<retries:
            time.sleep(0.8*attempt)
    raise RuntimeError(f'Sohu fetch failed for {normalize_symbol(symbol)} {start}..{end}: {last}')


def fetch_symbol(
    symbol:str,
    start:str=FORMAL_BEG,
    end:str=FORMAL_END,
    max_calendar_days:int=90,
    timeout:int=20,
    retries:int=3,
    delay:float=0.05,
)->tuple[list[dict],dict]:
    s=normalize_symbol(symbol)
    session=requests.Session()
    by_date={}; chunk_rows=[]
    chunks=plan_chunks(start,end,max_calendar_days)
    try:
        for a,b in chunks:
            rows=fetch_chunk(session,s,a,b,timeout=timeout,retries=retries)
            chunk_rows.append(len(rows))
            if len(rows)>=80:
                raise RuntimeError(f'Sohu chunk may be truncated ({len(rows)} rows) {s} {a}..{b}')
            for r in rows:
                d=r['date']
                if d in by_date and by_date[d] != r:
                    raise RuntimeError(f'conflicting duplicate Sohu row {s} {d}')
                by_date[d]=r
            if delay>0:
                time.sleep(delay)
    finally:
        session.close()
    rows=[by_date[d] for d in sorted(by_date)]
    meta={
        'chunk_n':len(chunks),'chunk_nonempty_n':sum(n>0 for n in chunk_rows),
        'max_chunk_rows':max(chunk_rows) if chunk_rows else 0,
        'empty_chunk_n':sum(n==0 for n in chunk_rows),
    }
    return rows,meta


def sha256_file(path:pathlib.Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def write_csv(path:pathlib.Path,rows:list[dict])->None:
    fields=['symbol','date','open','high','low','close','volume','amount','source']
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k) for k in fields})


def audit_rows(symbol:str,rows:list[dict],meta:dict)->dict:
    s=normalize_symbol(symbol); dates=[r['date'] for r in rows]
    dup_n=len(dates)-len(set(dates))
    bad_ohlc=sum(1 for r in rows if min(r['open'],r['high'],r['low'],r['close'])<=0)
    bad_volume=sum(1 for r in rows if r['volume']<=0)
    bad_amount=sum(1 for r in rows if r['amount']<=0)
    return {
        'symbol':s,'rows':len(rows),'first_date':min(dates) if dates else None,
        'last_date':max(dates) if dates else None,'duplicate_dates':dup_n,
        'bad_ohlc_rows':bad_ohlc,'bad_volume_rows':bad_volume,'bad_amount_rows':bad_amount,
        **meta,
        'status':'PASS_NONEMPTY_RAW' if rows and dup_n==0 and bad_ohlc==0 else ('EMPTY' if not rows else 'REVIEW'),
    }


def run_probe(symbols:Iterable[str],out_dir:pathlib.Path,workers:int=2,timeout:int=20)->dict:
    syms=[normalize_symbol(s) for s in symbols]
    out_dir.mkdir(parents=True,exist_ok=True)
    audits=[]; errors=[]

    def one(s):
        rows,meta=fetch_symbol(s,timeout=timeout)
        fp=out_dir/f'{s}.csv'; write_csv(fp,rows)
        a=audit_rows(s,rows,meta); a['csv']=fp.name; a['sha256']=sha256_file(fp)
        return a

    with ThreadPoolExecutor(max_workers=max(1,int(workers))) as pool:
        fut={pool.submit(one,s):s for s in syms}
        for f in as_completed(fut):
            s=fut[f]
            try:
                a=f.result(); audits.append(a); print(json.dumps(a,ensure_ascii=False),flush=True)
            except Exception as exc:
                e={'symbol':s,'type':type(exc).__name__,'message':str(exc)}
                errors.append(e); print(json.dumps(e,ensure_ascii=False),flush=True)
    audits.sort(key=lambda a:a['symbol']); errors.sort(key=lambda e:e['symbol'])
    summary={
        'artifact':'SOHU_RAW_PROBE_V482','version':'V4.82',
        'formal_window':[FORMAL_BEG,FORMAL_END],
        'chunk_calendar_days':90,'volume_normalization':'lots_x100_to_shares',
        'amount_normalization':'10k_cny_x10000_to_cny',
        'symbols_requested':len(syms),'symbols_fetched':len(audits),'errors':len(errors),
        'nonempty_pass':sum(a['status']=='PASS_NONEMPTY_RAW' for a in audits),
        'audits':audits,'error_details':errors,
        'formal_admission':False,'oos_metrics_allowed':False,
    }
    (out_dir/'SOHU_RAW_PROBE_V482.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--symbol',action='append',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--timeout',type=int,default=20)
    a=ap.parse_args()
    run_probe(a.symbol,pathlib.Path(a.out_dir),workers=a.workers,timeout=a.timeout)

if __name__=='__main__':
    main()
