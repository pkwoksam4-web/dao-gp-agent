from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

from cninfo_exact_term_v481 import resolve_orgid, query_cninfo

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
SPECIAL_RESTRUCTURING_11={
    '000525.SZ','000615.SZ','000796.SZ','000430.SZ','000697.SZ','000981.SZ',
    '002021.SZ','000908.SZ','600306.SH','002076.SZ','000691.SZ',
}
EXACT_STATUSES={'REVIEW_GLOBAL_LEDGER_EXACT_TERMS','REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'}


def _date_from_ms(ms) -> dt.date | None:
    try:
        return dt.datetime.fromtimestamp(float(ms)/1000,tz=dt.timezone.utc).date()
    except Exception:
        return None


def _clean_title(s: str) -> str:
    return re.sub(r'<[^>]+>','',str(s or '')).replace(' ','')


def _is_implementation(item: dict) -> bool:
    t=_clean_title(item.get('announcementTitle'))
    return '权益分派实施公告' in t or '权益分配实施公告' in t


def select_standard_exact_symbols(report: dict) -> dict[str,list[str]]:
    out={}
    for r in report.get('records') or []:
        if not isinstance(r,dict):
            continue
        symbol=str(r.get('symbol') or '').upper()
        if r.get('status') not in EXACT_STATUSES or symbol in SPECIAL_RESTRUCTURING_11:
            continue
        dates=sorted({str(e.get('ex_date') or '')[:10] for e in (r.get('events') or []) if e.get('ex_date')})
        if not dates:
            raise ValueError(f'{symbol} exact review has no event dates')
        out[symbol]=dates
    return dict(sorted(out.items()))


def match_announcements_to_events(event_dates: list[str], items: list[dict], max_prior_days: int=30) -> dict[str,dict|None]:
    candidates=[]
    for item in items or []:
        if not isinstance(item,dict) or not _is_implementation(item):
            continue
        d=_date_from_ms(item.get('announcementTime'))
        if d is None:
            continue
        candidates.append((d,item))
    candidates.sort(key=lambda x:x[0])
    out={}
    for event in event_dates:
        ed=dt.date.fromisoformat(str(event)[:10])
        choices=[]
        for ad,item in candidates:
            gap=(ed-ad).days
            if 0 <= gap <= max_prior_days:
                choices.append((gap,ad,item))
        if not choices:
            out[event]=None
        else:
            choices.sort(key=lambda x:(x[0],-x[1].toordinal()))
            out[event]=choices[0][2]
    return out


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _safe_jsonable_org_meta(meta: dict) -> dict:
    return {
        'http_status':meta.get('http_status'),'content_type':meta.get('content_type'),
        'attempts':meta.get('attempts'),'orgid':meta.get('orgid'),'record':meta.get('record'),
    }


def collect_one(symbol: str, event_dates: list[str], raw_dir: pathlib.Path) -> dict:
    code=symbol.split('.')[0]
    rec={'symbol':symbol,'event_dates':event_dates,'orgid':None,'org_lookup':None,'query':None,
         'announcement_n':0,'matched_event_n':0,'matches':{},'error':None}
    try:
        org=resolve_orgid(code)
        rec['orgid']=org['orgid']; rec['org_lookup']=_safe_jsonable_org_meta(org)
        org_raw=org['raw']; org_file=f'{code}_orgid.json'; (raw_dir/org_file).write_bytes(org_raw)
        rec['org_lookup']['raw_file']=org_file; rec['org_lookup']['sha256']=hashlib.sha256(org_raw).hexdigest()

        q=query_cninfo(code,'2020-05-01',FORMAL_END,orgid=org['orgid'])
        q_raw=q['raw']; q_file=f'{code}_formal_implementation_index.json'; (raw_dir/q_file).write_bytes(q_raw)
        items=(q['json'] or {}).get('announcements') or []
        rec['query']={'http_status':q.get('http_status'),'content_type':q.get('content_type'),'attempts':q.get('attempts'),
                      'raw_file':q_file,'sha256':hashlib.sha256(q_raw).hexdigest(),'bytes':len(q_raw)}
        rec['announcement_n']=len(items)
        matched=match_announcements_to_events(event_dates,items,30)
        for d,item in matched.items():
            rec['matches'][d]=item
        rec['matched_event_n']=sum(v is not None for v in matched.values())
        return rec
    except Exception as e:
        rec['error']=f'{type(e).__name__}: {e}'
        return rec


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--closure-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--workers',type=int,default=3)
    args=ap.parse_args()
    closure_path=_find_unique(pathlib.Path(args.closure_dir),'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json')
    closure=json.loads(closure_path.read_text(encoding='utf-8'))
    scope=select_standard_exact_symbols(closure)
    if len(scope)!=87:
        raise RuntimeError(f'expected exact 87 standard exact-term symbols; got {len(scope)}')

    out=pathlib.Path(args.out_dir); raw=out/'raw'; raw.mkdir(parents=True,exist_ok=True)
    records=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        fut={pool.submit(collect_one,s,dates,raw):s for s,dates in scope.items()}
        for i,f in enumerate(as_completed(fut),1):
            r=f.result(); records.append(r)
            if i%10==0 or i==len(scope):
                print(json.dumps({'progress':i,'total':len(scope),'symbol':r['symbol'],'matched':r['matched_event_n'],'events':len(r['event_dates']),'error':r['error']},ensure_ascii=False),flush=True)
    records.sort(key=lambda r:r['symbol'])
    query_ok=sum(r['error'] is None for r in records)
    total_events=sum(len(r['event_dates']) for r in records)
    matched_events=sum(r['matched_event_n'] for r in records)
    all_matched=sum(r['error'] is None and r['matched_event_n']==len(r['event_dates']) for r in records)
    report={
        'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_V481','version':'V4.81',
        'formal_window':[FORMAL_BEG,FORMAL_END],'scope_symbol_n':87,
        'query_ok_n':query_ok,'query_error_n':87-query_ok,'event_date_n':total_events,
        'matched_event_n':matched_events,'symbols_all_events_matched_n':all_matched,
        'status_counts':dict(Counter('QUERY_ERROR' if r['error'] else ('ALL_MATCHED' if r['matched_event_n']==len(r['event_dates']) else 'PARTIAL_MATCH') for r in records)),
        'records':records,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    }
    (out/'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['scope_symbol_n','query_ok_n','query_error_n','event_date_n','matched_event_n','symbols_all_events_matched_n','status_counts']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
