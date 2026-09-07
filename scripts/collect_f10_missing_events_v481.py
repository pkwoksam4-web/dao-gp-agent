from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

BASE='https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/PageAjax'
OUT_STATUS_HIT='F10_PAGEAJAX_TARGET_DATE_HIT'
OUT_STATUS_PARTIAL='F10_PAGEAJAX_TARGET_DATE_UNRESOLVED_PARTIAL_WINDOW'


def fetch_one(symbol: str, targets: list[str], out_raw: pathlib.Path) -> dict:
    code,exch=symbol.split('.')
    sc=('SH' if exch=='SH' else 'SZ')+code
    url=BASE+'?'+urllib.parse.urlencode({'code':sc})
    last_error=None
    for attempt in range(1,4):
        req=urllib.request.Request(url,headers={
            'User-Agent':'Mozilla/5.0',
            'Referer':f'https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/Index?type=web&code={sc}',
            'X-Requested-With':'XMLHttpRequest',
        })
        try:
            with urllib.request.urlopen(req,timeout=25) as r:
                raw=r.read(); status=getattr(r,'status',None); ct=r.headers.get('Content-Type')
            obj=json.loads(raw.decode('utf-8-sig'))
            if not isinstance(obj,dict): raise ValueError('PageAjax top-level is not object')
            raw_name=f'{code}_{exch}_pageajax.json'
            (out_raw/raw_name).write_bytes(raw)
            collections={k:v for k,v in obj.items() if isinstance(v,list)}
            target_results=[]
            for d in targets:
                hits=[]
                for cname,rows in collections.items():
                    for idx,row in enumerate(rows):
                        if not isinstance(row,dict): continue
                        text=json.dumps(row,ensure_ascii=False,sort_keys=True)
                        if d in text:
                            hits.append({'collection':cname,'row_index':idx,'row':row})
                target_results.append({
                    'date':d,
                    'status':OUT_STATUS_HIT if hits else OUT_STATUS_PARTIAL,
                    'hits':hits,
                })
            return {
                'symbol':symbol,'url':url,'ok':True,'http_status':status,'content_type':ct,
                'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'attempts':attempt,
                'raw_file':raw_name,'collections':{k:len(v) for k,v in collections.items()},
                'targets':target_results,'error':None,
            }
        except Exception as e:
            last_error=f'{type(e).__name__}: {e}'
            time.sleep(0.6*attempt)
    return {'symbol':symbol,'url':url,'ok':False,'http_status':None,'content_type':None,'bytes':0,'sha256':None,'attempts':3,'raw_file':None,'collections':{},'targets':[{'date':d,'status':'F10_PAGEAJAX_FETCH_FAILED','hits':[]} for d in targets],'error':last_error}


def read_missing(path: pathlib.Path):
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    out=[]
    for r in rows:
        if r.get('status')!='REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH': continue
        targets=[x for x in (r.get('missing_in_ledger') or '').split('|') if x]
        if not targets: raise RuntimeError(f'missing-event row without target dates: {r.get("symbol")}')
        out.append((r['symbol'],targets))
    if len(out)!=60: raise RuntimeError(f'expected exact 60 missing-event symbols, got {len(out)}')
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--review-queue',required=True); ap.add_argument('--out-dir',required=True); args=ap.parse_args()
    out=pathlib.Path(args.out_dir); rawdir=out/'raw'; rawdir.mkdir(parents=True,exist_ok=True)
    work=read_missing(pathlib.Path(args.review_queue))
    records=[]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs={ex.submit(fetch_one,s,t,rawdir):(s,t) for s,t in work}
        for fut in as_completed(futs):
            rec=fut.result(); records.append(rec); print(json.dumps({'symbol':rec['symbol'],'ok':rec['ok'],'targets':[(x['date'],x['status']) for x in rec['targets']]},ensure_ascii=False),flush=True)
    records.sort(key=lambda r:r['symbol'])
    if len(records)!=60 or len({r['symbol'] for r in records})!=60: raise RuntimeError('PageAjax output not exact 60 partition')
    target_status=Counter(t['status'] for r in records for t in r['targets'])
    symbol_all_hit=sum(all(t['status']==OUT_STATUS_HIT for t in r['targets']) for r in records)
    symbol_any_unresolved=sum(any(t['status']!=OUT_STATUS_HIT for t in r['targets']) for r in records)
    report={
        'artifact':'F10_MISSING_EVENT_COVERAGE_V481','version':'V4.81',
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'source':'EastMoney PC_HSF10 BonusFinancing/PageAjax',
        'input_checkpoint':'V4.81 integrated 847 review queue: 60 REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH',
        'symbol_n':60,'record_n':len(records),'partition_exact':len(records)==60 and len({r['symbol'] for r in records})==60,
        'target_date_n':sum(len(r['targets']) for r in records),
        'target_status_counts':dict(sorted(target_status.items())),
        'symbols_all_targets_hit_n':symbol_all_hit,
        'symbols_with_any_unresolved_n':symbol_any_unresolved,
        'note':'PageAjax fhyx is a partial recent window. Absence is never negative evidence and remains unresolved.',
        'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,
        'records':records,
    }
    (out/'F10_MISSING_EVENT_COVERAGE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # compact CSV target matrix
    with (out/'F10_MISSING_EVENT_TARGET_MATRIX_V481.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['symbol','date','status','collections_hit','raw_sha256','error']); w.writeheader()
        for r in records:
            for t in r['targets']:
                w.writerow({'symbol':r['symbol'],'date':t['date'],'status':t['status'],'collections_hit':'|'.join(sorted({h['collection'] for h in t['hits']})),'raw_sha256':r.get('sha256'),'error':r.get('error')})
    print(json.dumps({k:report[k] for k in ['symbol_n','target_date_n','target_status_counts','symbols_all_targets_hit_n','symbols_with_any_unresolved_n']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
