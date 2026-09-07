from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import time
from collections import Counter, defaultdict

from sample50_validate import (
    Action,
    compare_factor_path,
    event_ratio,
    expected_factor_for_date,
    merge_actions,
    parse_sina_qfq,
    parse_sohu_history_bytes,
    prev_close_before,
    sina_normalized_for_date,
)
from missing_event_terms_v481 import parse_impl_plan_profile
from missing_event_factor_recalc_v481 import (
    extract_f10_target_profile,
    classify_missing_event_recalc,
)
from recalc_global_qfq_from_ledger_v481_fixed import sina_factor_change_dates

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
THRESHOLD_BP=5.0
ALREADY_RESOLVED_7={
    '000564.SZ','000981.SZ','002076.SZ','300117.SZ','300262.SZ','600070.SH','600190.SH',
}
BASE_AFTER_7={
    'PASS':707,
    'EXACT_TERM_REVIEW':84,
    'MISSING_EVENT_REVIEW':53,
    'NOT_APPLICABLE':3,
    'REVIEW_TOTAL':137,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def action_from_base_event(symbol: str, ev: dict) -> Action:
    if not isinstance(ev, dict):
        raise ValueError('base event must be an object')
    ex_date=str(ev.get('ex_date') or '')[:10]
    if len(ex_date)!=10:
        raise ValueError('base event missing ex_date')
    return Action(
        symbol=str(symbol).upper(),
        ex_date=ex_date,
        cash_per_share=float(ev.get('cash_per_share_nominal') or 0.0),
        stock_ratio=float(ev.get('stock_ratio') or 0.0),
        cap_ratio=float(ev.get('capitalization_ratio') or 0.0),
        rights_ratio=float(ev.get('rights_ratio') or 0.0),
        rights_price=(None if ev.get('rights_price') in (None,'') else float(ev.get('rights_price'))),
        source=str(ev.get('source') or 'GLOBAL_LEDGER_BASE_EVENT'),
    )


def _target_map(f10_record: dict) -> dict[str,dict]:
    targets={}
    for target in f10_record.get('targets') or []:
        if not isinstance(target,dict):
            continue
        date=str(target.get('date') or '')[:10]
        if not date:
            continue
        if date in targets:
            raise ValueError(f'duplicate F10 target date {date}')
        targets[date]=target
    return targets


def build_combined_actions(symbol: str, base_record: dict, f10_record: dict) -> tuple[list[Action],dict]:
    symbol=str(symbol).upper()
    if str(base_record.get('symbol') or '').upper()!=symbol:
        raise ValueError('base record symbol mismatch')
    if str(f10_record.get('symbol') or '').upper()!=symbol:
        raise ValueError('F10 record symbol mismatch')

    missing_dates=sorted(set(base_record.get('missing_in_ledger') or []))
    if not missing_dates:
        raise ValueError(f'{symbol} has no missing event dates')

    targets=_target_map(f10_record)
    if set(targets)!=set(missing_dates):
        raise ValueError(
            f'{symbol} F10 target partition mismatch expected={missing_dates} actual={sorted(targets)}'
        )

    base_actions=[action_from_base_event(symbol,ev) for ev in (base_record.get('events') or [])]
    new_actions=[]
    new_profiles={}
    for date in missing_dates:
        target=targets[date]
        profile=extract_f10_target_profile(target)
        terms=parse_impl_plan_profile(profile)
        new_profiles[date]=profile
        new_actions.append(Action(
            symbol=symbol,
            ex_date=date,
            cash_per_share=terms['cash_per_share'],
            stock_ratio=terms['stock_ratio'],
            cap_ratio=terms['capitalization_ratio'],
            rights_ratio=terms['rights_ratio'],
            rights_price=terms['rights_price'],
            source='EASTMONEY_F10_PAGEAJAX_IMPLEMENTED',
        ))

    actions=merge_actions(base_actions+new_actions)
    combined_dates=sorted(a.ex_date for a in actions)
    sina_dates=sorted(set(base_record.get('sina_event_dates') or []))
    coverage_complete=(combined_dates==sina_dates)
    evidence={
        'coverage_complete':coverage_complete,
        'new_profiles':new_profiles,
        'base_event_dates':sorted(a.ex_date for a in base_actions),
        'new_event_dates':sorted(a.ex_date for a in new_actions),
        'combined_event_dates':combined_dates,
        'sina_event_dates':sina_dates,
    }
    return actions,evidence


def find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def build_basename_index(root: pathlib.Path, suffix: str) -> dict[str,list[pathlib.Path]]:
    out=defaultdict(list)
    for p in root.rglob('*'+suffix):
        if p.is_file(): out[p.name].append(p)
    return dict(out)


def unique_from_index(index: dict[str,list[pathlib.Path]], name: str) -> pathlib.Path:
    hits=index.get(name,[])
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def load_base_records(integrated_dir: pathlib.Path) -> dict[str,dict]:
    p=find_unique(integrated_dir,'GLOBAL_QFQ_LEDGER_RECALC_V481.json')
    x=json.loads(p.read_text(encoding='utf-8'))
    if x.get('scope_n')!=847 or x.get('record_n')!=847 or x.get('partition_exact') is not True:
        raise RuntimeError('integrated 847 checkpoint invariant mismatch')
    all_missing={r['symbol']:r for r in x.get('records',[]) if r.get('status')=='REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH'}
    if len(all_missing)!=60:
        raise RuntimeError(f'expected 60 base missing-event records, got {len(all_missing)}')
    remain={s:r for s,r in all_missing.items() if s not in ALREADY_RESOLVED_7}
    if len(remain)!=53:
        raise RuntimeError(f'expected exact remaining 53 symbols, got {len(remain)}')
    return remain


def load_f10_records(f10_dir: pathlib.Path, base_records: dict[str,dict]) -> dict[str,dict]:
    p=find_unique(f10_dir,'F10_MISSING_EVENT_COVERAGE_V481.json')
    x=json.loads(p.read_text(encoding='utf-8'))
    if x.get('symbol_n')!=60 or x.get('record_n')!=60 or x.get('partition_exact') is not True:
        raise RuntimeError('all-60 F10 coverage artifact invariant mismatch')
    if x.get('target_date_n')!=105 or x.get('symbols_all_targets_hit_n')!=53 or x.get('symbols_with_any_unresolved_n')!=7:
        raise RuntimeError('all-60 F10 frozen count contract mismatch')
    by={r['symbol']:r for r in x.get('records',[])}
    out={}; target_n=0
    for symbol,base in sorted(base_records.items()):
        r=by.get(symbol)
        if r is None:
            raise RuntimeError(f'{symbol} missing from F10 artifact')
        targets=r.get('targets') or []
        if not targets or any(t.get('status')!='F10_PAGEAJAX_TARGET_DATE_HIT' for t in targets):
            raise RuntimeError(f'{symbol} is not all-target positive in frozen F10 artifact')
        raw=find_unique(f10_dir,r['raw_file']); b=raw.read_bytes()
        if sha256_bytes(b)!=r.get('sha256'):
            raise RuntimeError(f'{symbol} F10 raw SHA mismatch')
        target_dates=sorted(str(t.get('date') or '')[:10] for t in targets)
        missing_dates=sorted(set(base.get('missing_in_ledger') or []))
        if target_dates!=missing_dates:
            raise RuntimeError(f'{symbol} F10 target dates do not equal base missing dates')
        for t in targets:
            parse_impl_plan_profile(extract_f10_target_profile(t))
        target_n+=len(targets); out[symbol]=r
    if len(out)!=53 or target_n!=93:
        raise RuntimeError(f'expected 53 symbols / 93 targets; got {len(out)} / {target_n}')
    return out


def recalc_one(symbol: str, base: dict, f10: dict, sina_index, sohu_index) -> dict:
    rec={
        'symbol':symbol,'status':None,'coverage_complete':False,
        'base_event_dates':[],'missing_event_dates':[],'combined_event_dates':[],
        'new_profiles':{},'factor_validation':None,'events':[],'source_meta':{},'error':None,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
    }
    try:
        actions,evidence=build_combined_actions(symbol,base,f10)
        rec['coverage_complete']=evidence['coverage_complete']
        rec['base_event_dates']=evidence['base_event_dates']
        rec['missing_event_dates']=evidence['new_event_dates']
        rec['combined_event_dates']=evidence['combined_event_dates']
        rec['new_profiles']=evidence['new_profiles']
        if not rec['coverage_complete']:
            rec['status']='BLOCKED_MISSING_EVENT_COVERAGE'
            return rec

        code,exch=symbol.split('.'); prefix=f'{code}_{exch}'
        sina_path=unique_from_index(sina_index,prefix+'_sina_qfq.js')
        sohu_path=unique_from_index(sohu_index,prefix+'_sohu_raw_history.js')
        sina_raw=sina_path.read_bytes(); sohu_raw=sohu_path.read_bytes()
        factors=parse_sina_qfq(sina_raw); raw_rows=parse_sohu_history_bytes(sohu_raw)
        formal_rows=[r for r in raw_rows if FORMAL_BEG<=r['date']<=FORMAL_END]
        if not formal_rows:
            raise ValueError('no Formal RAW rows')
        factor_dates=sina_factor_change_dates(factors,FORMAL_BEG,FORMAL_END)
        if factor_dates!=rec['combined_event_dates']:
            raise ValueError(f'factor-change dates disagree with combined actions: {factor_dates} vs {rec["combined_event_dates"]}')

        rec['source_meta']={
            'f10_raw_sha256':f10.get('sha256'),
            'f10_source':'EastMoney F10 PageAjax run 34075413814 artifact gp-f10-missing-event-v481',
            'sina_raw_sha256':sha256_bytes(sina_raw),
            'sina_source':'corrected V4.81 source census run 34009079533',
            'sohu_raw_sha256':sha256_bytes(sohu_raw),
            'sohu_source':'V4.81 nominal shard RAW run 34009535349',
        }

        ratios={}; missing=set(rec['missing_event_dates'])
        for a in actions:
            pc=prev_close_before(raw_rows,a.ex_date); ratio=event_ratio(a,pc); ratios[a.ex_date]=ratio
            rec['events'].append({
                'ex_date':a.ex_date,
                'event_role':'F10_MISSING_EVENT' if a.ex_date in missing else 'BASE_GLOBAL_LEDGER_EVENT',
                'profile':rec['new_profiles'].get(a.ex_date),
                'cash_per_share':a.cash_per_share,'stock_ratio':a.stock_ratio,'capitalization_ratio':a.cap_ratio,
                'rights_ratio':a.rights_ratio,'rights_price':a.rights_price,'prev_actual_close':pc,
                'event_ratio':ratio,'source':a.source,
            })
        expected={r['date']:expected_factor_for_date(r['date'],actions,ratios,FORMAL_END) for r in formal_rows}
        actual={r['date']:sina_normalized_for_date(factors,r['date'],FORMAL_END) for r in formal_rows}
        cmp=compare_factor_path(formal_rows,expected,actual,THRESHOLD_BP)
        rec['factor_validation']=cmp
        rec['status']=classify_missing_event_recalc(True,cmp['status'])
        return rec
    except Exception as e:
        rec['status']='BLOCKED_MISSING_EVENT_FACTOR_COMPARISON'
        rec['error']=f'{type(e).__name__}: {e}'
        return rec


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--integrated-dir',required=True)
    ap.add_argument('--f10-dir',required=True)
    ap.add_argument('--source-census',required=True)
    ap.add_argument('--nominal-shards',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()

    base_records=load_base_records(pathlib.Path(args.integrated_dir))
    f10_records=load_f10_records(pathlib.Path(args.f10_dir),base_records)
    sina_index=build_basename_index(pathlib.Path(args.source_census),'_sina_qfq.js')
    sohu_index=build_basename_index(pathlib.Path(args.nominal_shards),'_sohu_raw_history.js')

    records=[]
    for i,symbol in enumerate(sorted(base_records),1):
        r=recalc_one(symbol,base_records[symbol],f10_records[symbol],sina_index,sohu_index)
        records.append(r)
        if i%10==0 or i==53:
            print(json.dumps({'progress':i,'total':53,'symbol':symbol,'status':r['status']},ensure_ascii=False),flush=True)
    if len(records)!=53 or len({r['symbol'] for r in records})!=53:
        raise RuntimeError('remaining missing-event output is not exact 53 partition')

    counts=Counter(r['status'] for r in records)
    pass_n=counts.get('PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR',0)
    exact_n=counts.get('REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',0)
    blocked_n=53-pass_n-exact_n
    after={
        'PASS':BASE_AFTER_7['PASS']+pass_n,
        'EXACT_TERM_REVIEW':BASE_AFTER_7['EXACT_TERM_REVIEW']+exact_n,
        'MISSING_EVENT_REVIEW':0 if blocked_n==0 else blocked_n,
        'NOT_APPLICABLE':BASE_AFTER_7['NOT_APPLICABLE'],
    }
    after['REVIEW_TOTAL']=after['EXACT_TERM_REVIEW']+after['MISSING_EVENT_REVIEW']
    report={
        'artifact':'MISSING_EVENT_FACTOR_RECALC_53_V481','version':'V4.81',
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'formal_window':[FORMAL_BEG,FORMAL_END],'threshold_bp':THRESHOLD_BP,
        'base_checkpoint_after_7':BASE_AFTER_7,
        'target_symbol_n':53,'target_missing_event_date_n':93,
        'status_counts':dict(sorted(counts.items())),'resolved_pass_n':pass_n,
        'resolved_to_exact_review_n':exact_n,'blocked_n':blocked_n,
        'nominal_checkpoint_after_60':after,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
        'records':records,
    }
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'MISSING_EVENT_FACTOR_RECALC_53_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'MISSING_EVENT_FACTOR_RECALC_53_V481.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['symbol','status','coverage_complete','base_event_dates','missing_event_dates','combined_event_dates','max_diff_bp','error'])
        w.writeheader()
        for r in records:
            fv=r.get('factor_validation') or {}
            w.writerow({
                'symbol':r['symbol'],'status':r['status'],'coverage_complete':r['coverage_complete'],
                'base_event_dates':'|'.join(r['base_event_dates']),'missing_event_dates':'|'.join(r['missing_event_dates']),
                'combined_event_dates':'|'.join(r['combined_event_dates']),'max_diff_bp':fv.get('max_diff_bp'),'error':r.get('error'),
            })
    print(json.dumps({
        'status_counts':report['status_counts'],'resolved_pass_n':pass_n,
        'resolved_to_exact_review_n':exact_n,'blocked_n':blocked_n,
        'nominal_checkpoint_after_60':after,
    },ensure_ascii=False,indent=2))
    if blocked_n:
        raise SystemExit(f'fail-closed: {blocked_n} of 53 remaining missing-event symbols are blocked')

if __name__=='__main__':
    main()
