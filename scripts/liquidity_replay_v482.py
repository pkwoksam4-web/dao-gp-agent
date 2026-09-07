from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

import numpy as np
import pandas as pd

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
WINDOW=20
MIN_PERIODS=20
MIN_DENSITY=0.8
MIN_ACTUAL_BEFORE=120
THRESHOLDS=[30_000_000,50_000_000,60_000_000,70_000_000,80_000_000,100_000_000]
EXPECTED_ROWS=6_006_046
EXPECTED_SYMBOLS=5_322
EXPECTED_CALENDAR=1_426
EXPECTED_KLINE002_SHA256='f7e09d35183863f66ac5f72edf28135d59a0eb6577ca12720acfaf1855cc800e'
EXPECTED={
  30_000_000:(4590,4204,4200,99.9049,3215.0,2482.5,2898.0,4360.5,2178,4321),
  50_000_000:(4581,4204,4194,99.7621,2543.5,1959.0,2278.5,3857.0,1720,3729),
  60_000_000:(4571,4204,4186,99.5718,2300.0,1757.0,2055.25,3605.0,1563,3444),
  70_000_000:(4554,4204,4175,99.3102,2106.5,1615.5,1864.25,3377.0,1422,3206),
  80_000_000:(4532,4204,4164,99.0485,1938.5,1481.0,1693.0,3164.5,1315,2977),
 100_000_000:(4479,4204,4122,98.0495,1666.0,1263.0,1432.0,2798.0,1091,2660),
}


def sha256_file(path:pathlib.Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def _rolling_components(x:pd.DataFrame,variant:str,min_actual_before:int=MIN_ACTUAL_BEFORE):
    z=x.copy().sort_values('date').reset_index(drop=True)
    traded=z['traded'].fillna(False).astype(bool)
    if variant=='market_day_zero':
        amount=pd.to_numeric(z['amount'],errors='coerce').where(traded,0.0).fillna(0.0)
    elif variant=='market_day_nan':
        amount=pd.to_numeric(z['amount'],errors='coerce').where(traded,np.nan)
    else:
        raise ValueError(f'unknown variant {variant}')
    median20=amount.rolling(WINDOW,min_periods=MIN_PERIODS).median()
    density20=traded.astype(float).rolling(WINDOW,min_periods=MIN_PERIODS).mean()
    cum=traded.astype(int).cumsum()
    base=(density20>=MIN_DENSITY)&(cum>=int(min_actual_before))&traded
    return z,traded,median20,density20,cum,base


def evaluate_one_calendar_series(x:pd.DataFrame, threshold:float, variant:str, min_actual_before:int=MIN_ACTUAL_BEFORE)->pd.DataFrame:
    z,traded,median20,density20,cum,base=_rolling_components(x,variant,min_actual_before)
    z['median_amount20']=median20
    z['trade_density20']=density20
    z['actual_traded_cum']=cum
    z['eligible']=base&(median20>=float(threshold))
    return z


def _load_astock(root:pathlib.Path)->pd.DataFrame:
    files=sorted(root.glob('kline_*.parquet'))
    files=[p for p in files if p.name!='kline_other.parquet']+([root/'kline_other.parquet'] if (root/'kline_other.parquet').exists() else [])
    if not files:
        raise FileNotFoundError('no kline_*.parquet')
    parts=[]
    for p in files:
        q=pd.read_parquet(p,columns=['code','date','volume','amount'])
        parts.append(q)
    df=pd.concat(parts,ignore_index=True)
    df['code']=df['code'].astype(str).str.replace(r'\.0$','',regex=True).str.zfill(6)
    # Reproduce V3.70 source behavior. Only the dedicated 399 index family was
    # excluded; historical kline_000 ambiguity is intentionally left untouched.
    df=df[~df['code'].str.startswith('399')].copy()
    df['date']=pd.to_datetime(df['date']).dt.normalize()
    df=df[(df['date']>=FORMAL_BEG)&(df['date']<=FORMAL_END)].copy()
    df['volume']=pd.to_numeric(df['volume'],errors='coerce')
    df['amount']=pd.to_numeric(df['amount'],errors='coerce')
    return df


def _metrics_for_variant(df:pd.DataFrame,variant:str)->dict:
    calendar=pd.DatetimeIndex(sorted(df['date'].dropna().unique()))
    if len(calendar)!=EXPECTED_CALENDAR:
        raise ValueError(f'calendar {len(calendar)} != {EXPECTED_CALENDAR}')
    daily={t:np.zeros(len(calendar),dtype=np.int32) for t in THRESHOLDS}
    ever={t:0 for t in THRESHOLDS}
    mature_ever={t:0 for t in THRESHOLDS}
    mature=0
    for _,g in df.groupby('code',sort=False):
        g=g.sort_values('date').drop_duplicates('date',keep='last').set_index('date')
        gg=g.reindex(calendar)
        amount=pd.to_numeric(gg['amount'],errors='coerce')
        traded=(pd.to_numeric(gg['volume'],errors='coerce').fillna(0)>0)&(amount.fillna(0)>0)
        base_df=pd.DataFrame({'date':calendar,'amount':amount.to_numpy(),'traded':traded.to_numpy()})
        _,_,median20,_,_,base=_rolling_components(base_df,variant,MIN_ACTUAL_BEFORE)
        med=median20.to_numpy()
        b=base.to_numpy(dtype=bool)
        actual_n=int(traded.sum())
        is_mature=actual_n>=843
        if is_mature:
            mature+=1
        for t in THRESHOLDS:
            e=b & (med>=float(t))
            daily[t]+=e.astype(np.int32)
            if e.any():
                ever[t]+=1
                if is_mature:
                    mature_ever[t]+=1
    out=[]
    for t in THRESHOLDS:
        c=daily[t]
        nz=c[c>0]
        out.append({
            'min_liq_amount_cny':t,
            'symbols_ever_passing':ever[t],
            'mature_symbols_ge843':mature,
            'mature_symbols_ge843_and_ever_passing':mature_ever[t],
            'mature_retention_pct':round(100.0*mature_ever[t]/mature,4),
            'median_daily_passing_pre_st':float(np.median(c)),
            'p10_daily_passing_pre_st':float(np.percentile(c,10)),
            'p25_daily_passing_pre_st':float(np.percentile(c,25)),
            'p90_daily_passing_pre_st':float(np.percentile(c,90)),
            'min_daily_passing_when_base_nonzero':int(nz.min()) if len(nz) else 0,
            'latest_day_passing_pre_st':int(c[-1]),
        })
    return {'variant':variant,'results':out}


def _compare(replay:dict)->dict:
    fields=['symbols_ever_passing','mature_symbols_ge843','mature_symbols_ge843_and_ever_passing','mature_retention_pct','median_daily_passing_pre_st','p10_daily_passing_pre_st','p25_daily_passing_pre_st','p90_daily_passing_pre_st','min_daily_passing_when_base_nonzero','latest_day_passing_pre_st']
    mismatches=[]
    for r in replay['results']:
        exp=EXPECTED[int(r['min_liq_amount_cny'])]
        for i,f in enumerate(fields):
            if abs(float(r[f])-float(exp[i]))>1e-6:
                mismatches.append({'threshold':r['min_liq_amount_cny'],'field':f,'actual':r[f],'expected':exp[i]})
    return {'exact_match':not mismatches,'mismatch_n':len(mismatches),'mismatches':mismatches}


def replay(root:pathlib.Path,out_dir:pathlib.Path)->dict:
    sha=sha256_file(root/'kline_002.parquet')
    df=_load_astock(root)
    base={
        'source_commit':'0babe4cf6c1a175c6b84add10803b4b1f9c6000c',
        'kline_002_sha256':sha,
        'kline_002_sha_match':sha==EXPECTED_KLINE002_SHA256,
        'rows_read':len(df),
        'symbols':df['code'].nunique(),
        'calendar_days':df['date'].nunique(),
    }
    variants=[]
    for v in ('market_day_zero','market_day_nan'):
        r=_metrics_for_variant(df,v)
        r['comparison_to_v370']=_compare(r)
        variants.append(r)
    exact=[v['variant'] for v in variants if v['comparison_to_v370']['exact_match']]
    report={
        'artifact':'LIQUIDITY_REPLAY_V482','version':'V4.82','source':base,
        'expected_source_shape':{'rows':EXPECTED_ROWS,'symbols':EXPECTED_SYMBOLS,'calendar_days':EXPECTED_CALENDAR},
        'variants':variants,'exact_matching_variants':exact,
        'frozen_semantics_status':'CLOSED_REPRODUCED_V370' if len(exact)==1 else 'OPEN_NEEDS_DIAGNOSIS',
        'formal_ready':False,'oos_metrics_allowed':False,
    }
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'LIQUIDITY_REPLAY_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source':base,'exact_matching_variants':exact,'mismatch_counts':{v['variant']:v['comparison_to_v370']['mismatch_n'] for v in variants}},ensure_ascii=False,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--astock-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    a=ap.parse_args()
    replay(pathlib.Path(a.astock_dir),pathlib.Path(a.out_dir))

if __name__=='__main__':
    main()
