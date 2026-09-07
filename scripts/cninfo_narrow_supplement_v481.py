from __future__ import annotations

import argparse
import copy
from collections import Counter
import hashlib
import json
import pathlib
import time

from cninfo_exact_term_v481 import event_query_window, query_cninfo, resolve_orgid
from collect_cninfo_exact_term_indices_v481 import match_announcements_to_events

VERSION='V4.81'


def select_unmatched_targets(base: dict) -> dict[str,list[str]]:
    out={}
    for r in base.get('records') or []:
        symbol=str(r.get('symbol') or '')
        dates=[str(d)[:10] for d in (r.get('event_dates') or [])]
        if not symbol or not dates:
            continue
        if r.get('error'):
            missing=dates
        else:
            matches=r.get('matches') or {}
            missing=[d for d in dates if not matches.get(d)]
        if missing:
            out[symbol]=sorted(dict.fromkeys(missing))
    return dict(sorted(out.items()))


def shard_targets(targets: dict[str,list[str]], shard_index: int, shard_count: int) -> dict[str,list[str]]:
    if shard_count < 1 or not (0 <= shard_index < shard_count):
        raise ValueError(f'invalid shard {shard_index}/{shard_count}')
    items=sorted(targets.items())
    return dict(items[shard_index::shard_count])


def replay_saved_query_raw(symbol: str, ex_date: str, raw: bytes, raw_file: str) -> dict:
    if not isinstance(raw,(bytes,bytearray)) or not raw:
        raise ValueError('saved CNINFO raw must be non-empty bytes')
    symbol=str(symbol or '').strip(); ex_date=str(ex_date or '')[:10]
    if not symbol or len(ex_date)!=10:
        raise ValueError('invalid symbol/ex_date for saved raw replay')
    try:
        obj=json.loads(bytes(raw).decode('utf-8'))
    except Exception as e:
        raise ValueError(f'invalid saved CNINFO JSON: {e}') from e
    items=(obj or {}).get('announcements') or []
    match=match_announcements_to_events([ex_date],items,max_prior_days=45)[ex_date]
    return {
        'symbol':symbol,'ex_date':ex_date,'match':match,'error':None,
        'replay_provenance':{
            'method':'SAVED_CNINFO_RAW_REPLAY_CURRENT_MATCHER',
            'raw_file':str(raw_file),'sha256':hashlib.sha256(bytes(raw)).hexdigest(),
            'bytes':len(raw),'announcement_n':len(items),
        },
    }


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _base_index_file(root: pathlib.Path) -> pathlib.Path:
    for name in ('CNINFO_STANDARD_EXACT_TERM_INDEX_MERGED_V481.json','CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json'):
        hits=[p for p in root.rglob(name) if p.is_file()]
        if len(hits)==1:
            return hits[0]
    raise FileNotFoundError('cannot locate unique V4.81 CNINFO base index')


def collect_symbol(symbol: str, dates: list[str], raw_dir: pathlib.Path,
                   timeout: int=15, attempts: int=4, sleep_between: float=0.25) -> list[dict]:
    code=symbol.split('.')[0]
    out=[]
    try:
        org=resolve_orgid(code)
        orgid=org['orgid']
        org_raw=org['raw']
        org_file=f'{code}_supplement_orgid.json'
        (raw_dir/org_file).write_bytes(org_raw)
        org_meta={'orgid':orgid,'http_status':org.get('http_status'),'attempts':org.get('attempts'),
                  'raw_file':org_file,'sha256':hashlib.sha256(org_raw).hexdigest(),'record':org.get('record')}
    except Exception as e:
        err=f'{type(e).__name__}: {e}'
        return [{'symbol':symbol,'ex_date':d,'org_lookup':None,'query':None,'match':None,'error':err} for d in dates]

    for i,d in enumerate(dates):
        start,end=event_query_window(d,45,2)
        row={'symbol':symbol,'ex_date':d,'org_lookup':org_meta,'query':None,'match':None,'error':None}
        try:
            q=query_cninfo(code,start,end,orgid=orgid,searchkey='实施公告',timeout=timeout,attempts=attempts)
            raw=q['raw']; fn=f'{code}_{d}_narrow_implementation.json'; (raw_dir/fn).write_bytes(raw)
            items=(q.get('json') or {}).get('announcements') or []
            match=match_announcements_to_events([d],items,max_prior_days=45)[d]
            row['query']={'http_status':q.get('http_status'),'content_type':q.get('content_type'),
                          'attempts':q.get('attempts'),'raw_file':fn,'sha256':hashlib.sha256(raw).hexdigest(),
                          'bytes':len(raw),'searchkey':q.get('searchkey'),'date_window':q.get('date_window'),
                          'announcement_n':len(items)}
            row['match']=match
        except Exception as e:
            row['error']=f'{type(e).__name__}: {e}'
        out.append(row)
        if sleep_between and i+1<len(dates):
            time.sleep(float(sleep_between))
    return out


def merge_base_with_supplement(base: dict, supplement: dict, expected_scope_n: int=87) -> dict:
    records=copy.deepcopy(base.get('records') or [])
    if len(records)!=expected_scope_n or len({r.get('symbol') for r in records})!=expected_scope_n:
        raise ValueError(f'base index must contain exact {expected_scope_n} unique symbols')
    by={r['symbol']:r for r in records}
    seen=set()
    for s in supplement.get('records') or []:
        symbol=str(s.get('symbol') or ''); d=str(s.get('ex_date') or '')[:10]
        key=(symbol,d)
        if key in seen: raise ValueError(f'duplicate supplement event: {key}')
        seen.add(key)
        if symbol not in by: raise ValueError(f'supplement symbol outside base scope: {symbol}')
        r=by[symbol]
        if d not in [str(x)[:10] for x in (r.get('event_dates') or [])]:
            raise ValueError(f'supplement date outside base event set: {key}')
        matches=r.setdefault('matches',{})
        if matches.get(d) is not None:
            raise ValueError(f'refuse to overwrite existing CNINFO match: {key}')
        if s.get('match') is not None:
            matches[d]=copy.deepcopy(s['match'])
        hist=r.setdefault('narrow_supplement',{'base_query_error':r.get('error'),'events':{}})
        hist['events'][d]={k:copy.deepcopy(s.get(k)) for k in ('query','match','error','org_lookup','replay_provenance')}

    for r in records:
        dates=[str(d)[:10] for d in (r.get('event_dates') or [])]
        matches=r.get('matches') or {}
        missing=[d for d in dates if matches.get(d) is None]
        if not missing:
            if r.get('error'):
                r.setdefault('narrow_supplement',{})['base_query_error']=r.get('error')
            r['error']=None
        r['matched_event_n']=len(dates)-len(missing)
        r['unmatched_event_dates']=missing

    total_events=sum(len(r.get('event_dates') or []) for r in records)
    matched=sum(int(r.get('matched_event_n') or 0) for r in records)
    all_matched=sum(int(r.get('matched_event_n') or 0)==len(r.get('event_dates') or []) for r in records)
    unresolved_symbols=sum(int(r.get('matched_event_n') or 0)<len(r.get('event_dates') or []) for r in records)
    out={
        'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_SUPPLEMENTED_V481','version':VERSION,
        'scope_symbol_n':len(records),'event_date_n':total_events,'matched_event_n':matched,
        'unmatched_event_n':total_events-matched,'symbols_all_events_matched_n':all_matched,
        'symbols_unresolved_n':unresolved_symbols,
        'status_counts':dict(Counter('ALL_MATCHED' if int(r.get('matched_event_n') or 0)==len(r.get('event_dates') or []) else 'PARTIAL_MATCH' for r in records)),
        'records':sorted(records,key=lambda r:r['symbol']),
        'supplement_source_artifact':supplement.get('artifact'),
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
    }
    return out


def collect_main(args):
    root=pathlib.Path(args.base_index_dir)
    base=json.loads(_base_index_file(root).read_text(encoding='utf-8'))
    targets=select_unmatched_targets(base)
    full_symbol_n=len(targets); full_event_n=sum(map(len,targets.values()))
    if args.expected_target_symbol_n is not None and full_symbol_n!=args.expected_target_symbol_n:
        raise RuntimeError(f'expected target symbols {args.expected_target_symbol_n}; got {full_symbol_n}')
    if args.expected_target_event_n is not None and full_event_n!=args.expected_target_event_n:
        raise RuntimeError(f'expected target events {args.expected_target_event_n}; got {full_event_n}')
    scope=shard_targets(targets,args.shard_index,args.shard_count)
    outdir=pathlib.Path(args.out_dir); raw=outdir/'raw'; raw.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,(symbol,dates) in enumerate(scope.items(),1):
        rows.extend(collect_symbol(symbol,dates,raw,args.timeout,args.attempts,args.sleep_between))
        print(json.dumps({'symbol_progress':i,'symbol_total':len(scope),'symbol':symbol,'events':len(dates)},ensure_ascii=False),flush=True)
    matched=sum(r.get('match') is not None for r in rows)
    errors=sum(r.get('error') is not None for r in rows)
    report={
        'artifact':'CNINFO_NARROW_EXACT_TERM_SUPPLEMENT_V481','version':VERSION,
        'base_scope_symbol_n':int(base.get('scope_symbol_n') or len(base.get('records') or [])),
        'full_target_symbol_n':full_symbol_n,'full_target_event_n':full_event_n,
        'shard_index':args.shard_index,'shard_count':args.shard_count,
        'target_symbol_n':len(scope),'target_event_n':len(rows),'matched_event_n':matched,
        'query_error_event_n':errors,'unmatched_no_error_event_n':len(rows)-matched-errors,'records':rows,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
    }
    (outdir/'CNINFO_NARROW_EXACT_TERM_SUPPLEMENT_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('full_target_symbol_n','full_target_event_n','shard_index','target_symbol_n','target_event_n','matched_event_n','query_error_event_n','unmatched_no_error_event_n')},ensure_ascii=False,indent=2))


def merge_main(args):
    base=json.loads(_base_index_file(pathlib.Path(args.base_index_dir)).read_text(encoding='utf-8'))
    paths=sorted(pathlib.Path(args.supplement_dir).rglob('CNINFO_NARROW_EXACT_TERM_SUPPLEMENT_V481.json'))
    reps=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
    if not reps: raise RuntimeError('no supplement shard reports')
    shard_count={int(r.get('shard_count',-1)) for r in reps}
    indices=sorted(int(r.get('shard_index',-1)) for r in reps)
    if len(shard_count)!=1 or indices!=list(range(next(iter(shard_count)))):
        raise RuntimeError(f'incomplete supplement shard set: counts={shard_count} indices={indices}')
    rows=[]
    for r in reps: rows.extend(r.get('records') or [])
    supplement={'artifact':'CNINFO_NARROW_EXACT_TERM_SUPPLEMENT_MERGED_V481','records':rows}
    merged=merge_base_with_supplement(base,supplement,args.expected_scope_n)
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'CNINFO_STANDARD_EXACT_TERM_INDEX_SUPPLEMENTED_V481.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:merged[k] for k in ('scope_symbol_n','event_date_n','matched_event_n','unmatched_event_n','symbols_all_events_matched_n','symbols_unresolved_n','status_counts')},ensure_ascii=False,indent=2))


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest='cmd',required=True)
    c=sub.add_parser('collect')
    c.add_argument('--base-index-dir',required=True); c.add_argument('--out-dir',required=True)
    c.add_argument('--shard-index',type=int,default=0); c.add_argument('--shard-count',type=int,default=1)
    c.add_argument('--timeout',type=int,default=15); c.add_argument('--attempts',type=int,default=4)
    c.add_argument('--sleep-between',type=float,default=0.25)
    c.add_argument('--expected-target-symbol-n',type=int); c.add_argument('--expected-target-event-n',type=int)
    m=sub.add_parser('merge')
    m.add_argument('--base-index-dir',required=True); m.add_argument('--supplement-dir',required=True); m.add_argument('--out-dir',required=True)
    m.add_argument('--expected-scope-n',type=int,default=87)
    args=ap.parse_args()
    collect_main(args) if args.cmd=='collect' else merge_main(args)

if __name__=='__main__':
    main()
