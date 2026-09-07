from __future__ import annotations

import argparse, csv, hashlib, json, pathlib, time
from collections import Counter, defaultdict

from sample50_validate import (
    Action, compare_factor_path, event_ratio, expected_factor_for_date, merge_actions,
    parse_sina_qfq, parse_sohu_history_bytes, prev_close_before, sina_normalized_for_date,
)
from missing_event_terms_v481 import parse_impl_plan_profile
from missing_event_factor_recalc_v481 import extract_f10_target_profile, classify_missing_event_recalc
from recalc_global_qfq_from_ledger_v481_fixed import sina_factor_change_dates

FORMAL_BEG='2020-06-01'; FORMAL_END='2026-04-17'; THRESHOLD_BP=5.0
ALREADY_RESOLVED_7={'000564.SZ','000981.SZ','002076.SZ','300117.SZ','300262.SZ','600070.SH','600190.SH'}
BASE_AFTER_7={'PASS':707,'EXACT_TERM_REVIEW':84,'MISSING_EVENT_REVIEW':53,'NOT_APPLICABLE':3,'REVIEW_TOTAL':137}


def sha256_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def action_from_base_event(symbol: str, ev: dict) -> Action:
    if not isinstance(ev,dict): raise ValueError('base event must be an object')
    d=str(ev.get('ex_date') or '')[:10]
    if len(d)!=10: raise ValueError('base event missing ex_date')
    return Action(
        symbol=str(symbol).upper(),ex_date=d,
        cash_per_share=float(ev.get('cash_per_share_nominal') or 0.0),
        stock_ratio=float(ev.get('stock_ratio') or 0.0),
        cap_ratio=float(ev.get('capitalization_ratio') or 0.0),
        rights_ratio=float(ev.get('rights_ratio') or 0.0),
        rights_price=None if ev.get('rights_price') in (None,'') else float(ev['rights_price']),
        source=str(ev.get('source') or 'GLOBAL_LEDGER_BASE_EVENT'),
    )


def _target_map(f10: dict) -> dict[str,dict]:
    out={}
    for t in f10.get('targets') or []:
        if not isinstance(t,dict): raise ValueError('F10 target must be object')
        d=str(t.get('date') or '')[:10]
        if len(d)!=10 or d in out: raise ValueError(f'invalid/duplicate F10 target {d!r}')
        out[d]=t
    return out


def build_combined_actions(symbol: str, base_record: dict, f10_record: dict) -> tuple[list[Action],dict]:
    symbol=str(symbol).upper()
    if str(base_record.get('symbol') or '').upper()!=symbol: raise ValueError('base record symbol mismatch')
    if str(f10_record.get('symbol') or '').upper()!=symbol: raise ValueError('F10 record symbol mismatch')
    missing=sorted(set(base_record.get('missing_in_ledger') or []))
    if not missing: raise ValueError(f'{symbol} has no missing event dates')
    targets=_target_map(f10_record)
    if sorted(targets)!=missing: raise ValueError(f'{symbol} F10 target partition mismatch')

    base_actions=[action_from_base_event(symbol,e) for e in (base_record.get('events') or [])]
    new=[]; profiles={}
    for d in missing:
        profile=extract_f10_target_profile(targets[d])
        t=parse_impl_plan_profile(profile); profiles[d]=profile
        new.append(Action(symbol=symbol,ex_date=d,cash_per_share=t['cash_per_share'],
                          stock_ratio=t['stock_ratio'],cap_ratio=t['capitalization_ratio'],
                          rights_ratio=t['rights_ratio'],rights_price=t['rights_price'],
                          source='EASTMONEY_F10_PAGEAJAX_IMPLEMENTED'))
    actions=merge_actions(base_actions+new)
    combined=sorted(a.ex_date for a in actions); sina=sorted(set(base_record.get('sina_event_dates') or []))
    return actions,{
        'coverage_complete':combined==sina,'new_profiles':profiles,
        'base_event_dates':sorted(a.ex_date for a in base_actions),
        'new_event_dates':sorted(a.ex_date for a in new),'combined_event_dates':combined,'sina_event_dates':sina,
    }


def select_remaining53(integrated_report: dict) -> list[dict]:
    rows=[r for r in (integrated_report.get('records') or []) if r.get('status')=='REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH']
    if len(rows)!=60: raise ValueError(f'expected 60 missing-event records, got {len(rows)}')
    out=sorted((r for r in rows if r.get('symbol') not in ALREADY_RESOLVED_7),key=lambda r:r['symbol'])
    if len(out)!=53: raise ValueError(f'expected remaining 53, got {len(out)}')
    return out


def summarize_checkpoint_after_53(statuses: list[str]) -> dict:
    if len(statuses)!=53: raise ValueError(f'expected 53 statuses, got {len(statuses)}')
    c=Counter(statuses)
    p=c.get('PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR',0)
    e=c.get('REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',0)
    blocked=53-p-e
    if blocked<0: raise ValueError('invalid status counts')
    unknown=[s for s in statuses if s not in {
        'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR','REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'
    } and not str(s).startswith('BLOCKED_')]
    if unknown: raise ValueError(f'unknown statuses: {sorted(set(unknown))}')
    out={'PASS':707+p,'EXACT_TERM_REVIEW':84+e,'MISSING_EVENT_REVIEW':blocked,'NOT_APPLICABLE':3}
    out['REVIEW_TOTAL']=out['EXACT_TERM_REVIEW']+out['MISSING_EVENT_REVIEW']
    return out


def find_unique(root: pathlib.Path,name: str) -> pathlib.Path:
    h=[p for p in root.rglob(name) if p.is_file()]
    if len(h)!=1: raise FileNotFoundError(f'expected one {name}, found {len(h)}')
    return h[0]


def basename_index(root: pathlib.Path,suffix: str):
    out=defaultdict(list)
    for p in root.rglob('*'+suffix):
        if p.is_file(): out[p.name].append(p)
    return out


def unique_index(idx,name):
    h=idx.get(name,[])
    if len(h)!=1: raise FileNotFoundError(f'expected one {name}, found {len(h)}')
    return h[0]


def load_base(integrated_dir: pathlib.Path):
    x=json.loads(find_unique(integrated_dir,'GLOBAL_QFQ_LEDGER_RECALC_V481.json').read_text(encoding='utf-8'))
    if x.get('scope_n')!=847 or x.get('record_n')!=847 or x.get('partition_exact') is not True:
        raise RuntimeError('integrated 847 invariant mismatch')
    rows=select_remaining53(x)
    return {r['symbol']:r for r in rows}


def load_f10(f10_dir: pathlib.Path,base: dict):
    x=json.loads(find_unique(f10_dir,'F10_MISSING_EVENT_COVERAGE_V481.json').read_text(encoding='utf-8'))
    if (x.get('symbol_n'),x.get('record_n'),x.get('target_date_n'))!=(60,60,105) or x.get('partition_exact') is not True:
        raise RuntimeError('all-60 F10 invariant mismatch')
    if (x.get('symbols_all_targets_hit_n'),x.get('symbols_with_any_unresolved_n'))!=(53,7):
        raise RuntimeError('F10 frozen split is not 53/7')
    by={r['symbol']:r for r in x.get('records',[])}; out={}; n=0
    for s,b in base.items():
        r=by.get(s)
        if not r: raise RuntimeError(f'{s} missing F10 evidence')
        targets=r.get('targets') or []
        if any(t.get('status')!='F10_PAGEAJAX_TARGET_DATE_HIT' for t in targets): raise RuntimeError(f'{s} not all-target HIT')
        raw=find_unique(f10_dir,r['raw_file']); data=raw.read_bytes()
        if sha256_bytes(data)!=r.get('sha256'): raise RuntimeError(f'{s} F10 SHA mismatch')
        if sorted(str(t.get('date') or '')[:10] for t in targets)!=sorted(set(b.get('missing_in_ledger') or [])):
            raise RuntimeError(f'{s} target dates mismatch')
        for t in targets: parse_impl_plan_profile(extract_f10_target_profile(t))
        out[s]=r; n+=len(targets)
    if len(out)!=53 or n!=93: raise RuntimeError(f'expected 53/93, got {len(out)}/{n}')
    return out


def recalc_one(symbol,base,f10,sina_idx,sohu_idx):
    rec={'symbol':symbol,'status':None,'coverage_complete':False,'base_event_dates':[],'missing_event_dates':[],
         'combined_event_dates':[],'new_profiles':{},'factor_validation':None,'events':[],'source_meta':{},'error':None,
         'formal_promotion':False,'validated_global_provenance_emitted':False}
    try:
        actions,e=build_combined_actions(symbol,base,f10)
        rec.update({'coverage_complete':e['coverage_complete'],'base_event_dates':e['base_event_dates'],
                    'missing_event_dates':e['new_event_dates'],'combined_event_dates':e['combined_event_dates'],'new_profiles':e['new_profiles']})
        if not rec['coverage_complete']:
            rec['status']='BLOCKED_MISSING_EVENT_COVERAGE'; return rec
        code,ex=symbol.split('.'); prefix=f'{code}_{ex}'
        sr=unique_index(sina_idx,prefix+'_sina_qfq.js').read_bytes(); rr=unique_index(sohu_idx,prefix+'_sohu_raw_history.js').read_bytes()
        factors=parse_sina_qfq(sr); raw=parse_sohu_history_bytes(rr); formal=[r for r in raw if FORMAL_BEG<=r['date']<=FORMAL_END]
        if not formal: raise ValueError('no Formal RAW rows')
        if sina_factor_change_dates(factors,FORMAL_BEG,FORMAL_END)!=rec['combined_event_dates']:
            raise ValueError('factor-change date mismatch')
        rec['source_meta']={'f10_raw_sha256':f10.get('sha256'),'f10_source':'F10 PageAjax run 34075413814',
                            'sina_raw_sha256':sha256_bytes(sr),'sina_source':'Sina census run 34009079533',
                            'sohu_raw_sha256':sha256_bytes(rr),'sohu_source':'Sohu RAW run 34009535349'}
        ratios={}; missing=set(rec['missing_event_dates'])
        for a in actions:
            pc=prev_close_before(raw,a.ex_date); ratio=event_ratio(a,pc); ratios[a.ex_date]=ratio
            rec['events'].append({'ex_date':a.ex_date,'event_role':'F10_MISSING_EVENT' if a.ex_date in missing else 'BASE_GLOBAL_LEDGER_EVENT',
                                  'profile':rec['new_profiles'].get(a.ex_date),'cash_per_share':a.cash_per_share,
                                  'stock_ratio':a.stock_ratio,'capitalization_ratio':a.cap_ratio,'rights_ratio':a.rights_ratio,
                                  'rights_price':a.rights_price,'prev_actual_close':pc,'event_ratio':ratio,'source':a.source})
        expected={r['date']:expected_factor_for_date(r['date'],actions,ratios,FORMAL_END) for r in formal}
        actual={r['date']:sina_normalized_for_date(factors,r['date'],FORMAL_END) for r in formal}
        cmp=compare_factor_path(formal,expected,actual,THRESHOLD_BP); rec['factor_validation']=cmp
        rec['status']=classify_missing_event_recalc(True,cmp['status']); return rec
    except Exception as exc:
        rec['status']='BLOCKED_MISSING_EVENT_FACTOR_COMPARISON'; rec['error']=f'{type(exc).__name__}: {exc}'; return rec


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--integrated-dir',required=True); ap.add_argument('--f10-dir',required=True)
    ap.add_argument('--source-census',required=True); ap.add_argument('--nominal-shards',required=True); ap.add_argument('--out-dir',required=True)
    a=ap.parse_args(); base=load_base(pathlib.Path(a.integrated_dir)); f10=load_f10(pathlib.Path(a.f10_dir),base)
    sina=basename_index(pathlib.Path(a.source_census),'_sina_qfq.js'); sohu=basename_index(pathlib.Path(a.nominal_shards),'_sohu_raw_history.js')
    records=[]
    for i,s in enumerate(sorted(base),1):
        r=recalc_one(s,base[s],f10[s],sina,sohu); records.append(r)
        if i%10==0 or i==53: print(json.dumps({'progress':i,'total':53,'symbol':s,'status':r['status']},ensure_ascii=False),flush=True)
    statuses=[r['status'] for r in records]; counts=Counter(statuses); checkpoint=summarize_checkpoint_after_53(statuses)
    blocked=checkpoint['MISSING_EVENT_REVIEW']
    report={'artifact':'MISSING_EVENT_FACTOR_RECALC_53_V481','version':'V4.81','generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'formal_window':[FORMAL_BEG,FORMAL_END],'threshold_bp':THRESHOLD_BP,'base_checkpoint_after_7':BASE_AFTER_7,
            'target_symbol_n':53,'target_missing_event_date_n':93,'status_counts':dict(sorted(counts.items())),
            'resolved_pass_n':counts.get('PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR',0),
            'resolved_to_exact_review_n':counts.get('REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',0),'blocked_n':blocked,
            'nominal_checkpoint_after_60':checkpoint,'formal_promotion':False,'validated_global_provenance_emitted':False,
            'formal_ready':False,'oos_metrics_allowed':False,'records':records}
    out=pathlib.Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'MISSING_EVENT_FACTOR_RECALC_53_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'MISSING_EVENT_FACTOR_RECALC_53_V481.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['symbol','status','coverage_complete','base_event_dates','missing_event_dates','combined_event_dates','max_diff_bp','error']); w.writeheader()
        for r in records:
            w.writerow({'symbol':r['symbol'],'status':r['status'],'coverage_complete':r['coverage_complete'],
                        'base_event_dates':'|'.join(r['base_event_dates']),'missing_event_dates':'|'.join(r['missing_event_dates']),
                        'combined_event_dates':'|'.join(r['combined_event_dates']),
                        'max_diff_bp':(r.get('factor_validation') or {}).get('max_diff_bp'),'error':r.get('error')})
    print(json.dumps({'status_counts':report['status_counts'],'blocked_n':blocked,'nominal_checkpoint_after_60':checkpoint},ensure_ascii=False,indent=2))
    if blocked: raise SystemExit(f'fail-closed: {blocked} of 53 remain blocked')

if __name__=='__main__': main()
