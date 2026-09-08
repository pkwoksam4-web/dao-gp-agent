from __future__ import annotations

import argparse
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from sohu_raw_v482 import fetch_symbol, normalize_symbol

RAW_FIELDS=['symbol','date','open','high','low','close','volume','amount','source']
EXPECTED_SYMBOL_N=847
EXPECTED_TRADE_ROWS=1_011_607
ZERO_TRADE_SYMBOLS={'600074.SH','600485.SH','600677.SH'}

# V4.82 correction overlay for five Baostock/PIT-ST false-zero trade-status rows.
# Four 2024-06-13 sessions and the 300356.SZ 2023-06-20 delisting-period
# opening session were independently verified as real positive-volume trading
# sessions. Keep this list exact and auditable; do not infer or broaden
# corrections from symbol class, delisting status, or date patterns.
PITST_TRADESTATUS_ONE_CORRECTIONS={
    ('002087.SZ','2024-06-13'),
    ('300356.SZ','2023-06-20'),
    ('600647.SH','2024-06-13'),
    ('600766.SH','2024-06-13'),
    ('603133.SH','2024-06-13'),
}


def select_shard(symbols:list[str],shard_index:int,shard_count:int)->list[str]:
    if shard_count<=0 or not (0<=shard_index<shard_count):
        raise ValueError('invalid shard index/count')
    return list(symbols)[shard_index::shard_count]


def apply_pitst_trade_corrections(pitst:pd.DataFrame,strict:bool=False)->pd.DataFrame:
    out=pitst.copy()
    out['symbol']=out['symbol'].astype(str).str.upper()
    out['date']=out['date'].astype(str).str[:10]
    out['tradestatus']=pd.to_numeric(out['tradestatus'],errors='coerce').fillna(0).astype(int)
    applied=[]
    for symbol,d in sorted(PITST_TRADESTATUS_ONE_CORRECTIONS):
        mask=(out['symbol']==symbol)&(out['date']==d)
        n=int(mask.sum())
        if strict and n!=1:
            raise ValueError(f'PIT-ST correction target must exist exactly once: {symbol} {d}; got {n}')
        if n:
            out.loc[mask,'tradestatus']=1
            applied.extend([(symbol,d)]*n)
    out.attrs['v482_trade_corrections']=applied
    return out


def expected_trade_dates(pitst:pd.DataFrame,symbol:str)->list[str]:
    s=normalize_symbol(symbol)
    g=pitst[(pitst['symbol'].astype(str).str.upper()==s)&(pd.to_numeric(pitst['tradestatus'],errors='coerce').fillna(0).astype(int)==1)]
    return sorted(g['date'].astype(str).str[:10].drop_duplicates().tolist())


def audit_trade_dates(symbol:str,expected_dates:list[str],rows:list[dict])->dict:
    s=normalize_symbol(symbol)
    exp=sorted(set(str(d)[:10] for d in expected_dates))
    got=sorted(set(str(r.get('date') or '')[:10] for r in rows if r.get('date')))
    missing=sorted(set(exp)-set(got)); extra=sorted(set(got)-set(exp))
    return {
        'symbol':s,'expected_trade_rows':len(exp),'raw_rows':len(rows),
        'missing_dates_n':len(missing),'extra_dates_n':len(extra),
        'missing_dates':missing,'extra_dates':extra,
        'status':'PASS_EXACT_TRADE_DATES' if not missing and not extra and len(rows)==len(got) else 'REVIEW_TRADE_DATES',
    }


def full_raw_global_gate(
    *,
    unique_symbol_n:int,
    symbol_list_n:int,
    raw_rows:int,
    duplicate_rows:int,
    missing_n:int,
    extra_n:int,
    bad_ohlc:int,
    bad_volume:int,
    bad_amount:int,
    shard_error:int,
)->bool:
    """Fail closed on current global RAW facts, not stale shard review diagnostics.

    A shard review can become stale when an exact PIT-ST correction is added after
    immutable RAW bytes were materialized. The merge step independently re-audits
    every symbol/date and every value under current semantics, so those global facts
    are authoritative. Fetch/materialization errors remain fail-closed.
    """
    return (
        int(unique_symbol_n)==EXPECTED_SYMBOL_N and
        int(symbol_list_n)==EXPECTED_SYMBOL_N and
        int(raw_rows)==EXPECTED_TRADE_ROWS and
        int(duplicate_rows)==0 and int(missing_n)==0 and int(extra_n)==0 and
        int(bad_ohlc)==0 and int(bad_volume)==0 and int(bad_amount)==0 and
        int(shard_error)==0
    )


def _read_pitst(path:pathlib.Path)->pd.DataFrame:
    df=pd.read_csv(path,usecols=['symbol','date','tradestatus','isST'])
    df['symbol']=df['symbol'].astype(str).str.upper()
    df['date']=df['date'].astype(str).str[:10]
    if df['symbol'].nunique()!=EXPECTED_SYMBOL_N:
        raise ValueError(f'PIT-ST universe must be {EXPECTED_SYMBOL_N}; got {df["symbol"].nunique()}')
    df=apply_pitst_trade_corrections(df,strict=True)
    return df


def _quality_audit(rows:list[dict])->dict:
    return {
        'bad_ohlc_rows':sum(1 for r in rows if min(float(r['open']),float(r['high']),float(r['low']),float(r['close']))<=0),
        'bad_volume_rows':sum(1 for r in rows if float(r['volume'])<=0),
        'bad_amount_rows':sum(1 for r in rows if float(r['amount'])<=0),
    }


def materialize_shard(
    pitst_path:pathlib.Path,
    shard_index:int,
    shard_count:int,
    out_dir:pathlib.Path,
    workers:int=2,
    timeout:int=20,
)->dict:
    pit=_read_pitst(pitst_path)
    symbols=sorted(pit['symbol'].drop_duplicates().tolist())
    selected=select_shard(symbols,shard_index,shard_count)
    expected={s:expected_trade_dates(pit,s) for s in selected}
    out_dir.mkdir(parents=True,exist_ok=True)
    all_rows=[]; audits=[]; errors=[]

    def one(s:str):
        exp=expected[s]
        if not exp:
            rows=[]; meta={
                'chunk_n':0,'chunk_nonempty_n':0,'max_chunk_rows':0,'empty_chunk_n':0,
                'split_recovery_n':0,'leaf_chunk_n':0,'leaf_nonempty_n':0,'max_leaf_rows':0,
            }
        else:
            rows,meta=fetch_symbol(s,start=exp[0],end=exp[-1],max_calendar_days=90,timeout=timeout,retries=3,delay=0.05)
        a=audit_trade_dates(s,exp,rows)
        a.update(meta)
        a.update(_quality_audit(rows))
        if any(a[k] for k in ('bad_ohlc_rows','bad_volume_rows','bad_amount_rows')):
            a['status']='REVIEW_BAD_RAW_VALUES'
        return rows,a

    with ThreadPoolExecutor(max_workers=max(1,int(workers))) as pool:
        fut={pool.submit(one,s):s for s in selected}
        for i,f in enumerate(as_completed(fut),1):
            s=fut[f]
            try:
                rows,a=f.result(); all_rows.extend(rows); audits.append(a)
                print(json.dumps({'progress':i,'total':len(selected),'symbol':s,'status':a['status'],'rows':len(rows)},ensure_ascii=False),flush=True)
            except Exception as exc:
                e={'symbol':s,'type':type(exc).__name__,'message':str(exc)}
                errors.append(e); print(json.dumps({'progress':i,'total':len(selected),**e},ensure_ascii=False),flush=True)

    audits.sort(key=lambda a:a['symbol']); errors.sort(key=lambda e:e['symbol'])
    frame=pd.DataFrame(all_rows,columns=RAW_FIELDS)
    if len(frame):
        frame=frame.sort_values(['symbol','date']).reset_index(drop=True)
    pq=out_dir/f'SOHU_RAW_SHARD_{shard_index:02d}_V482.parquet'
    frame.to_parquet(pq,index=False)
    pass_n=sum(a['status']=='PASS_EXACT_TRADE_DATES' for a in audits)
    review_n=len(audits)-pass_n
    report={
        'artifact':'SOHU_RAW_SHARD_V482','version':'V4.82',
        'shard_index':shard_index,'shard_count':shard_count,
        'symbols_selected':len(selected),'symbol_list':selected,
        'expected_trade_rows':sum(len(expected[s]) for s in selected),
        'raw_rows':len(frame),'pass_n':pass_n,'review_n':review_n,'error_n':len(errors),
        'pitst_trade_corrections':sorted([list(x) for x in PITST_TRADESTATUS_ONE_CORRECTIONS]),
        'audits':audits,'errors':errors,
        'formal_admission':False,'oos_metrics_allowed':False,
    }
    (out_dir/f'SOHU_RAW_SHARD_{shard_index:02d}_AUDIT_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('shard_index','symbols_selected','expected_trade_rows','raw_rows','pass_n','review_n','error_n')},ensure_ascii=False,indent=2))
    return report


def merge_shards(shards_dir:pathlib.Path,pitst_path:pathlib.Path,out_dir:pathlib.Path)->dict:
    pit=_read_pitst(pitst_path)
    expected=pit[pd.to_numeric(pit['tradestatus'],errors='coerce').fillna(0).astype(int)==1][['symbol','date']].copy()
    expected=expected.drop_duplicates().sort_values(['symbol','date']).reset_index(drop=True)
    if len(expected)!=EXPECTED_TRADE_ROWS:
        raise ValueError(f'PIT-ST expected trade rows {len(expected)} != {EXPECTED_TRADE_ROWS}')

    audit_files=sorted(shards_dir.rglob('SOHU_RAW_SHARD_*_AUDIT_V482.json'))
    parquet_files=sorted(shards_dir.rglob('SOHU_RAW_SHARD_*_V482.parquet'))
    if not audit_files or not parquet_files:
        raise FileNotFoundError('missing shard artifacts')
    audits=[json.loads(p.read_text(encoding='utf-8')) for p in audit_files]
    shard_ids=[int(a['shard_index']) for a in audits]
    shard_counts={int(a['shard_count']) for a in audits}
    if len(shard_counts)!=1 or sorted(shard_ids)!=list(range(next(iter(shard_counts)))):
        raise ValueError(f'incomplete shard partition: ids={shard_ids} counts={shard_counts}')

    symbol_lists=[s for a in audits for s in a['symbol_list']]
    unique_symbols=set(symbol_lists)
    frames=[pd.read_parquet(p) for p in parquet_files]
    raw=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=RAW_FIELDS)
    if len(raw):
        raw['symbol']=raw['symbol'].astype(str).str.upper(); raw['date']=raw['date'].astype(str).str[:10]
        raw=raw.sort_values(['symbol','date']).reset_index(drop=True)
    duplicate_rows=int(raw.duplicated(['symbol','date']).sum()) if len(raw) else 0

    actual=raw[['symbol','date']].drop_duplicates() if len(raw) else pd.DataFrame(columns=['symbol','date'])
    z=expected.merge(actual,on=['symbol','date'],how='outer',indicator=True)
    missing=z[z['_merge']=='left_only'][['symbol','date']]
    extra=z[z['_merge']=='right_only'][['symbol','date']]
    bad_ohlc=int(((raw[['open','high','low','close']]<=0).any(axis=1)).sum()) if len(raw) else 0
    bad_volume=int((raw['volume']<=0).sum()) if len(raw) else 0
    bad_amount=int((raw['amount']<=0).sum()) if len(raw) else 0
    shard_review=sum(int(a['review_n']) for a in audits)
    shard_error=sum(int(a['error_n']) for a in audits)

    global_pass=full_raw_global_gate(
        unique_symbol_n=len(unique_symbols),
        symbol_list_n=len(symbol_lists),
        raw_rows=len(raw),
        duplicate_rows=duplicate_rows,
        missing_n=len(missing),
        extra_n=len(extra),
        bad_ohlc=bad_ohlc,
        bad_volume=bad_volume,
        bad_amount=bad_amount,
        shard_error=shard_error,
    )
    status='PASS_FULL_RAW_V482' if global_pass else 'REVIEW_FULL_RAW_V482'
    out_dir.mkdir(parents=True,exist_ok=True)
    full_pq=out_dir/'SOHU_RAW_FULL_V482.parquet'; raw.to_parquet(full_pq,index=False)
    report={
        'artifact':'SOHU_RAW_FULL_V482','version':'V4.82','status':status,
        'symbol_n':len(unique_symbols),'expected_symbol_n':EXPECTED_SYMBOL_N,
        'raw_rows':len(raw),'expected_trade_rows':EXPECTED_TRADE_ROWS,
        'duplicate_symbol_dates':duplicate_rows,
        'missing_trade_dates_n':len(missing),'extra_trade_dates_n':len(extra),
        'missing_trade_dates':missing.head(200).to_dict('records'),
        'extra_trade_dates':extra.head(200).to_dict('records'),
        'bad_ohlc_rows':bad_ohlc,'bad_volume_rows':bad_volume,'bad_amount_rows':bad_amount,
        'shard_review_n':shard_review,'shard_error_n':shard_error,
        'global_reaudit_pass':global_pass,
        'shard_review_is_diagnostic_only':True,
        'pitst_trade_corrections':sorted([list(x) for x in PITST_TRADESTATUS_ONE_CORRECTIONS]),
        'zero_trade_symbols':sorted(set(pit['symbol'])-set(raw['symbol'])) if len(raw) else sorted(set(pit['symbol'])),
        'formal_admission':False,'oos_metrics_allowed':False,
    }
    (out_dir/'SOHU_RAW_FULL_AUDIT_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','symbol_n','raw_rows','missing_trade_dates_n','extra_trade_dates_n','shard_review_n','shard_error_n','zero_trade_symbols')},ensure_ascii=False,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('shard'); s.add_argument('--pitst',required=True); s.add_argument('--shard-index',type=int,required=True); s.add_argument('--shard-count',type=int,required=True); s.add_argument('--out-dir',required=True); s.add_argument('--workers',type=int,default=2); s.add_argument('--timeout',type=int,default=20)
    m=sub.add_parser('merge'); m.add_argument('--pitst',required=True); m.add_argument('--shards-dir',required=True); m.add_argument('--out-dir',required=True)
    a=ap.parse_args()
    if a.cmd=='shard':
        materialize_shard(pathlib.Path(a.pitst),a.shard_index,a.shard_count,pathlib.Path(a.out_dir),a.workers,a.timeout)
    else:
        merge_shards(pathlib.Path(a.shards_dir),pathlib.Path(a.pitst),pathlib.Path(a.out_dir))

if __name__=='__main__':
    main()
