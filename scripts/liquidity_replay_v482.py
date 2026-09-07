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
RESULT_FIELDS=[
    'symbols_ever_passing','mature_symbols_ge843','mature_symbols_ge843_and_ever_passing',
    'mature_retention_pct','median_daily_passing_pre_st','p10_daily_passing_pre_st',
    'p25_daily_passing_pre_st','p90_daily_passing_pre_st',
    'min_daily_passing_when_base_nonzero','latest_day_passing_pre_st',
]
QUANTILE_REPORT_FIELDS={
    'median_daily_passing_pre_st','p10_daily_passing_pre_st',
    'p25_daily_passing_pre_st','p90_daily_passing_pre_st',
}
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


def _rolling_components(
    x:pd.DataFrame,
    variant:str,
    min_actual_before:int=MIN_ACTUAL_BEFORE,
    actual_gate:str='current',
):
    z=x.copy().sort_values('date').reset_index(drop=True)
    traded=z['traded'].fillna(False).astype(bool)
    raw_amount=pd.to_numeric(z['amount'],errors='coerce')
    density20=traded.astype(float).rolling(WINDOW,min_periods=MIN_PERIODS).mean()
    cum=traded.astype(int).cumsum()

    if variant=='market_day_zero':
        amount=raw_amount.where(traded,0.0).fillna(0.0)
        median20=amount.rolling(WINDOW,min_periods=MIN_PERIODS).median()
    elif variant=='market_day_nan':
        amount=raw_amount.where(traded,np.nan)
        median20=amount.rolling(WINDOW,min_periods=MIN_PERIODS).median()
    elif variant=='market_day_positive':
        amount=raw_amount.where(traded,np.nan)
        median20=amount.rolling(WINDOW,min_periods=1).median()
    elif variant=='last20_traded':
        median20=pd.Series(np.nan,index=z.index,dtype=float)
        ti=np.flatnonzero(traded.to_numpy())
        vals=raw_amount.iloc[ti].astype(float).reset_index(drop=True)
        med=vals.rolling(WINDOW,min_periods=MIN_PERIODS).median().to_numpy()
        median20.iloc[ti]=med
    else:
        raise ValueError(f'unknown variant {variant}')

    if actual_gate=='current':
        enough_actual=cum>=int(min_actual_before)
    elif actual_gate=='prior':
        # V3.70 contract says actual traded days BEFORE daily evaluation.
        enough_actual=cum.shift(1,fill_value=0)>=int(min_actual_before)
    else:
        raise ValueError(f'unknown actual_gate {actual_gate}')

    base=(density20>=MIN_DENSITY)&enough_actual&traded
    return z,traded,median20,density20,cum,base


def evaluate_one_calendar_series(
    x:pd.DataFrame,
    threshold:float,
    variant:str,
    min_actual_before:int=MIN_ACTUAL_BEFORE,
    actual_gate:str='current',
)->pd.DataFrame:
    z,traded,median20,density20,cum,base=_rolling_components(
        x,variant,min_actual_before,actual_gate
    )
    z['median_amount20']=median20
    z['trade_density20']=density20
    z['actual_traded_cum']=cum
    z['eligible']=base&(median20>=float(threshold))
    return z


def summarize_daily_counts(counts, *, positive_days_only:bool=False)->dict:
    c=np.asarray(counts,dtype=float)
    nz=c[c>0]
    summary_base=nz if positive_days_only else c
    if len(summary_base)==0:
        median=p10=p25=p90=float('nan')
    else:
        median=float(np.median(summary_base))
        p10=float(np.percentile(summary_base,10))
        p25=float(np.percentile(summary_base,25))
        p90=float(np.percentile(summary_base,90))
    return {
        'median_daily_passing_pre_st':median,
        'p10_daily_passing_pre_st':p10,
        'p25_daily_passing_pre_st':p25,
        'p90_daily_passing_pre_st':p90,
        'min_daily_passing_when_base_nonzero':int(nz.min()) if len(nz) else 0,
        'latest_day_passing_pre_st':int(c[-1]) if len(c) else 0,
    }


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
    df=df[~df['code'].str.startswith('399')].copy()
    df['date']=pd.to_datetime(df['date']).dt.normalize()
    df=df[(df['date']>=FORMAL_BEG)&(df['date']<=FORMAL_END)].copy()
    df['volume']=pd.to_numeric(df['volume'],errors='coerce')
    df['amount']=pd.to_numeric(df['amount'],errors='coerce')
    return df


def _metrics_for_config(
    df:pd.DataFrame,
    *,
    name:str,
    variant:str,
    actual_gate:str,
    positive_days_only:bool,
)->dict:
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
        _,_,median20,_,_,base=_rolling_components(
            base_df,variant,MIN_ACTUAL_BEFORE,actual_gate
        )
        med=median20.to_numpy()
        b=base.to_numpy(dtype=bool)
        actual_n=int(traded.sum())
        is_mature=actual_n>=843
        if is_mature:
            mature+=1
        for t in THRESHOLDS:
            e=b&(med>=float(t))
            daily[t]+=e.astype(np.int32)
            if e.any():
                ever[t]+=1
                if is_mature:
                    mature_ever[t]+=1
    out=[]
    for t in THRESHOLDS:
        stats=summarize_daily_counts(daily[t],positive_days_only=positive_days_only)
        out.append({
            'min_liq_amount_cny':t,
            'symbols_ever_passing':ever[t],
            'mature_symbols_ge843':mature,
            'mature_symbols_ge843_and_ever_passing':mature_ever[t],
            'mature_retention_pct':round(100.0*mature_ever[t]/mature,4),
            **stats,
        })
    return {
        'variant':name,
        'median_semantics':variant,
        'actual_gate':actual_gate,
        'positive_days_only_summary':positive_days_only,
        'results':out,
    }


def _compare(replay:dict)->dict:
    mismatches=[]
    for r in replay['results']:
        exp=EXPECTED[int(r['min_liq_amount_cny'])]
        for i,f in enumerate(RESULT_FIELDS):
            delta=float(r[f])-float(exp[i])
            if abs(delta)>1e-6:
                mismatches.append({'threshold':r['min_liq_amount_cny'],'field':f,'actual':r[f],'expected':exp[i],'delta':delta})
    return {'exact_match':not mismatches,'mismatch_n':len(mismatches),'mismatches':mismatches}


def _threshold_row_exact(variant:dict, threshold:int)->bool:
    row=next((r for r in variant.get('results',[]) if int(r['min_liq_amount_cny'])==int(threshold)),None)
    if row is None:
        return False
    exp=EXPECTED[int(threshold)]
    return all(abs(float(row[f])-float(exp[i]))<=1e-6 for i,f in enumerate(RESULT_FIELDS))


def assess_frozen_80m_replay(variants:list[dict])->dict:
    qualified=[]
    for v in variants:
        mismatches=v.get('comparison_to_v370',{}).get('mismatches',[])
        eligibility_residuals=[m for m in mismatches if m.get('field') not in QUANTILE_REPORT_FIELDS]
        if _threshold_row_exact(v,80_000_000) and not eligibility_residuals:
            qualified.append((v,eligibility_residuals,mismatches))
    if len(qualified)==1:
        v,eligibility_residuals,mismatches=qualified[0]
        return {
            'frozen_80m_status':'CLOSED_REPRODUCED_V370_80M',
            'frozen_80m_variant':v['variant'],
            'eligibility_logic_residual_n':len(eligibility_residuals),
            'six_threshold_reporting_residual_n':len(mismatches),
            'six_threshold_reporting_residuals':mismatches,
        }
    return {
        'frozen_80m_status':'OPEN_NEEDS_DIAGNOSIS',
        'frozen_80m_variant':None,
        'eligibility_logic_residual_n':None,
        'six_threshold_reporting_residual_n':None,
        'qualified_variant_n':len(qualified),
    }


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
    configs=[
        ('market_day_zero','market_day_zero','current',False),
        ('market_day_zero_prior120_positive_summary','market_day_zero','prior',True),
        ('market_day_zero_current120_positive_summary','market_day_zero','current',True),
        ('market_day_nan','market_day_nan','current',False),
        ('market_day_positive','market_day_positive','current',False),
        ('last20_traded','last20_traded','current',False),
    ]
    variants=[]
    for name,median_semantics,actual_gate,positive_summary in configs:
        r=_metrics_for_config(
            df,name=name,variant=median_semantics,
            actual_gate=actual_gate,positive_days_only=positive_summary,
        )
        r['comparison_to_v370']=_compare(r)
        variants.append(r)
    exact=[v['variant'] for v in variants if v['comparison_to_v370']['exact_match']]
    frozen80=assess_frozen_80m_replay(variants)
    report={
        'artifact':'LIQUIDITY_REPLAY_V482','version':'V4.82','source':base,
        'expected_source_shape':{'rows':EXPECTED_ROWS,'symbols':EXPECTED_SYMBOLS,'calendar_days':EXPECTED_CALENDAR},
        'contract_reference':{
            'metric':'rolling 20-market-day median daily amount/turnover CNY',
            'threshold_cny':80_000_000,
            'rolling_window_market_days':20,
            'min_periods':20,'min_trade_density20':0.8,
            'minimum_actual_traded_days_before_daily_liquidity_evaluation':120,
            'current_day_must_be_traded':True,
        },
        'resolved_eligibility_semantics':{
            'nontraded_amount_in_20_market_day_median':0.0,
            'minimum_actual_traded_days_gate':'120 PRIOR traded days; current day excluded from prior count',
            'current_day_must_be_traded':True,
            'trade_density20_min':0.8,
        } if frozen80['frozen_80m_status']=='CLOSED_REPRODUCED_V370_80M' else None,
        'variants':variants,
        'exact_matching_variants':exact,
        'six_threshold_full_report_status':'CLOSED_EXACT' if len(exact)==1 else 'OPEN_REPORTING_QUANTILE_RESIDUALS',
        **frozen80,
        'formal_ready':False,
        'oos_metrics_allowed':False,
    }
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'LIQUIDITY_REPLAY_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({
        'source':base,
        'exact_matching_variants':exact,
        'frozen_80m_status':report['frozen_80m_status'],
        'frozen_80m_variant':report['frozen_80m_variant'],
        'eligibility_logic_residual_n':report['eligibility_logic_residual_n'],
        'six_threshold_reporting_residual_n':report['six_threshold_reporting_residual_n'],
        'mismatch_counts':{v['variant']:v['comparison_to_v370']['mismatch_n'] for v in variants},
    },ensure_ascii=False,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--astock-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    a=ap.parse_args()
    replay(pathlib.Path(a.astock_dir),pathlib.Path(a.out_dir))

if __name__=='__main__':
    main()
