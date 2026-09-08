from __future__ import annotations

import argparse
import json
import pathlib

import pandas as pd

from liquidity_replay_v482 import (
    EXPECTED_CALENDAR,
    MIN_ACTUAL_BEFORE,
    evaluate_one_calendar_series,
)
from sohu_full_panel_v482 import (
    EXPECTED_SYMBOL_N,
    EXPECTED_TRADE_ROWS,
    apply_pitst_trade_corrections,
)

THRESHOLD_CNY=80_000_000.0
EXPECTED_PANEL_ROWS=EXPECTED_SYMBOL_N*EXPECTED_CALENDAR
EXPECTED_PITST_SOURCE_ROWS=1_022_100


def apply_frozen_80m_one_symbol(x:pd.DataFrame)->pd.DataFrame:
    """Apply the already-frozen V3.70/V4.82 80M rule to one full market-calendar series.

    This is intentionally a thin adapter around liquidity_replay_v482 so the 847
    validation universe cannot drift from the 5,322-symbol frozen replay semantics.
    """
    z=evaluate_one_calendar_series(
        x,
        threshold=THRESHOLD_CNY,
        variant='market_day_zero',
        min_actual_before=MIN_ACTUAL_BEFORE,
        actual_gate='prior',
    ).copy()
    z=z.rename(columns={'eligible':'liquidity_80m_pre_st'})
    return z


def apply_non_st_overlay(df:pd.DataFrame)->pd.DataFrame:
    out=df.copy()
    pre=out['liquidity_80m_pre_st'].fillna(False).astype(bool)
    # Lifecycle-unobserved rows retain isST=NaN and are conservatively ineligible.
    non_st=pd.to_numeric(out['isST'],errors='coerce').fillna(1).astype(int).eq(0)
    out['eligible_non_st']=pre&non_st
    return out


def _normalize_pitst(pitst:pd.DataFrame)->pd.DataFrame:
    p=apply_pitst_trade_corrections(pitst,strict=False)
    p=p.copy()
    p['symbol']=p['symbol'].astype(str).str.upper()
    p['date']=p['date'].astype(str).str[:10]
    p['tradestatus']=pd.to_numeric(p['tradestatus'],errors='coerce').fillna(0).astype(int)
    p['isST']=pd.to_numeric(p['isST'],errors='coerce').fillna(0).astype(int)
    return p


def _normalize_raw(raw:pd.DataFrame)->pd.DataFrame:
    r=raw.copy()
    r['symbol']=r['symbol'].astype(str).str.upper()
    r['date']=r['date'].astype(str).str[:10]
    for c in ('amount','volume'):
        if c in r.columns:
            r[c]=pd.to_numeric(r[c],errors='coerce')
    return r


def expand_pitst_to_market_calendar(
    pitst:pd.DataFrame,
    symbols:list[str],
    calendar:list[str],
)->pd.DataFrame:
    """Expand lifecycle-sparse authoritative PIT-ST rows to a market-calendar grid.

    V4.80 PIT-ST is intentionally materialized only over each security's lifecycle.
    The frozen liquidity rule, however, is defined on market days. We therefore pad
    lifecycle-exterior dates only at the application layer. Padded rows are marked
    pitst_observed=False, tradestatus=0, and keep isST unknown (NaN); no ST state is
    invented and such rows cannot become eligible because current-day traded=False.
    """
    p=_normalize_pitst(pitst)
    if p.duplicated(['symbol','date']).any():
        raise ValueError('duplicate PIT-ST symbol/date rows before calendar expansion')
    syms=sorted({str(s).upper() for s in symbols})
    cal=sorted({str(d)[:10] for d in calendar})
    grid=pd.MultiIndex.from_product([syms,cal],names=['symbol','date']).to_frame(index=False)
    src=p[['symbol','date','tradestatus','isST']].copy()
    src['pitst_observed']=True
    out=grid.merge(src,on=['symbol','date'],how='left',validate='one_to_one')
    out['pitst_observed']=out['pitst_observed'].fillna(False).astype(bool)
    out['tradestatus']=pd.to_numeric(out['tradestatus'],errors='coerce').fillna(0).astype(int)
    # Deliberately do not fill isST on lifecycle-padding rows.
    out['isST']=pd.to_numeric(out['isST'],errors='coerce')
    return out


def audit_raw_vs_pitst(raw:pd.DataFrame,pitst:pd.DataFrame)->dict:
    r=_normalize_raw(raw)
    p=_normalize_pitst(pitst)
    dup=int(r.duplicated(['symbol','date']).sum())
    expected=p[p['tradestatus'].eq(1)][['symbol','date']].drop_duplicates()
    actual=r[['symbol','date']].drop_duplicates()
    z=expected.merge(actual,on=['symbol','date'],how='outer',indicator=True)
    missing=z[z['_merge'].eq('left_only')][['symbol','date']]
    extra=z[z['_merge'].eq('right_only')][['symbol','date']]
    bad_amount=int((pd.to_numeric(r.get('amount'),errors='coerce').fillna(0)<=0).sum()) if 'amount' in r else len(r)
    bad_volume=int((pd.to_numeric(r.get('volume'),errors='coerce').fillna(0)<=0).sum()) if 'volume' in r else len(r)
    status='PASS_EXACT_RAW_PITST' if dup==0 and len(missing)==0 and len(extra)==0 and bad_amount==0 and bad_volume==0 else 'REVIEW_RAW_PITST'
    return {
        'status':status,
        'expected_trade_rows':len(expected),
        'raw_trade_rows':len(r),
        'duplicate_raw_symbol_dates':dup,
        'missing_trade_dates_n':len(missing),
        'extra_trade_dates_n':len(extra),
        'bad_amount_rows':bad_amount,
        'bad_volume_rows':bad_volume,
        'missing_trade_dates':missing.head(200).to_dict('records'),
        'extra_trade_dates':extra.head(200).to_dict('records'),
    }


def build_eligibility_panel(raw:pd.DataFrame,pitst:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    r=_normalize_raw(raw)
    p=_normalize_pitst(pitst)
    audit=audit_raw_vs_pitst(r,p)
    if audit['status']!='PASS_EXACT_RAW_PITST':
        raise ValueError(f'RAW/PIT-ST exact-date gate failed: {audit}')

    symbols=sorted(p['symbol'].drop_duplicates().tolist())
    calendar=sorted(p['date'].drop_duplicates().tolist())
    if len(symbols)!=EXPECTED_SYMBOL_N:
        raise ValueError(f'symbol universe {len(symbols)} != {EXPECTED_SYMBOL_N}')
    if len(calendar)!=EXPECTED_CALENDAR:
        raise ValueError(f'market calendar {len(calendar)} != {EXPECTED_CALENDAR}')
    pitst_source_rows=len(p.drop_duplicates(['symbol','date']))
    if pitst_source_rows!=EXPECTED_PITST_SOURCE_ROWS:
        raise ValueError(f'PIT-ST source rows {pitst_source_rows} != {EXPECTED_PITST_SOURCE_ROWS}')

    r2=r[['symbol','date','amount','volume']].copy()
    p2=expand_pitst_to_market_calendar(p,symbols,calendar)
    if len(p2)!=EXPECTED_PANEL_ROWS:
        raise ValueError(f'expanded PIT-ST rows {len(p2)} != {EXPECTED_PANEL_ROWS}')
    panel=p2.merge(r2,on=['symbol','date'],how='left',validate='one_to_one')
    parts=[]
    for symbol,g in panel.groupby('symbol',sort=True):
        g=g.sort_values('date').reset_index(drop=True)
        base=pd.DataFrame({
            'date':pd.to_datetime(g['date']),
            'amount':g['amount'],
            'traded':g['tradestatus'].eq(1),
        })
        liq=apply_frozen_80m_one_symbol(base)
        g['median_amount20']=liq['median_amount20'].to_numpy()
        g['trade_density20']=liq['trade_density20'].to_numpy()
        g['actual_traded_cum']=liq['actual_traded_cum'].to_numpy()
        g['liquidity_80m_pre_st']=liq['liquidity_80m_pre_st'].to_numpy(dtype=bool)
        g=apply_non_st_overlay(g)
        parts.append(g)
    out=pd.concat(parts,ignore_index=True).sort_values(['symbol','date']).reset_index(drop=True)

    if len(out)!=EXPECTED_PANEL_ROWS:
        raise ValueError(f'eligibility panel rows {len(out)} != {EXPECTED_PANEL_ROWS}')
    current_trade_violation=int((out['liquidity_80m_pre_st']&~out['tradestatus'].eq(1)).sum())
    st_overlay_violation=int((out['eligible_non_st']&pd.to_numeric(out['isST'],errors='coerce').fillna(1).ne(0)).sum())
    observed_rows=int(out['pitst_observed'].sum())
    report={
        'artifact':'LIQUIDITY_80M_APPLY_V482',
        'version':'V4.82',
        'threshold_cny':int(THRESHOLD_CNY),
        'frozen_variant':'market_day_zero_prior120_positive_summary',
        'frozen_semantics':{
            'rolling_window_market_days':20,
            'nontraded_amount_in_median':0.0,
            'min_trade_density20':0.8,
            'minimum_prior_actual_traded_days':120,
            'current_day_must_be_traded':True,
        },
        'symbol_n':len(symbols),
        'calendar_days':len(calendar),
        'panel_rows':len(out),
        'pitst_source_rows':pitst_source_rows,
        'pitst_observed_rows':observed_rows,
        'lifecycle_padding_rows':len(out)-observed_rows,
        'corrected_trade_rows':int(p['tradestatus'].eq(1).sum()),
        'raw_trade_rows':len(r),
        'liquidity_pre_st_true_rows':int(out['liquidity_80m_pre_st'].sum()),
        'eligible_non_st_true_rows':int(out['eligible_non_st'].sum()),
        'symbols_ever_liquidity_pre_st':int(out.groupby('symbol')['liquidity_80m_pre_st'].any().sum()),
        'symbols_ever_eligible_non_st':int(out.groupby('symbol')['eligible_non_st'].any().sum()),
        'latest_date':calendar[-1],
        'latest_liquidity_pre_st_n':int(out.loc[out['date'].eq(calendar[-1]),'liquidity_80m_pre_st'].sum()),
        'latest_eligible_non_st_n':int(out.loc[out['date'].eq(calendar[-1]),'eligible_non_st'].sum()),
        'raw_pitst_audit':audit,
        'current_trade_violation_n':current_trade_violation,
        'st_overlay_violation_n':st_overlay_violation,
        'formal_admission':False,
        'oos_metrics_allowed':False,
    }
    if report['corrected_trade_rows']!=EXPECTED_TRADE_ROWS:
        raise ValueError(f'corrected trade rows {report["corrected_trade_rows"]} != {EXPECTED_TRADE_ROWS}')
    if current_trade_violation or st_overlay_violation:
        raise ValueError(f'eligibility invariant violation: {report}')
    return out,report


def run(raw_path:pathlib.Path,pitst_path:pathlib.Path,out_dir:pathlib.Path)->dict:
    raw=pd.read_parquet(raw_path)
    pit=pd.read_csv(pitst_path,usecols=['symbol','date','tradestatus','isST'])
    panel,report=build_eligibility_panel(raw,pit)
    out_dir.mkdir(parents=True,exist_ok=True)
    panel.to_parquet(out_dir/'LIQUIDITY_80M_PANEL_V482.parquet',index=False)
    (out_dir/'LIQUIDITY_80M_APPLY_AUDIT_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw',required=True)
    ap.add_argument('--pitst',required=True)
    ap.add_argument('--out-dir',required=True)
    a=ap.parse_args()
    run(pathlib.Path(a.raw),pathlib.Path(a.pitst),pathlib.Path(a.out_dir))


if __name__=='__main__':
    main()
