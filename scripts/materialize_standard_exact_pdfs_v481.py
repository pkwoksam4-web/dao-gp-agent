from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from cninfo_exact_term_v481 import announcement_pdf_url
from cninfo_effective_terms_v481 import extract_effective_terms
from collect_cninfo_exact_term_indices_v481 import SPECIAL_RESTRUCTURING_11


def factor_jump_ratio(factors: list[dict], event_date: str) -> float:
    rows=sorted((str(r.get('d') or '')[:10],float(r['f'])) for r in factors if r.get('d') and r.get('f') not in (None,''))
    for i,(d,f) in enumerate(rows):
        if d==event_date:
            if i==0:
                raise ValueError(f'no prior factor before {event_date}')
            prior=rows[i-1][1]
            if prior==0:
                raise ValueError('zero prior factor')
            return f/prior
    raise ValueError(f'factor event date missing: {event_date}')


def select_candidate_events(record: dict, factors: list[dict], threshold_bp: float=5.0) -> list[dict]:
    out=[]
    for e in record.get('events') or []:
        d=str(e.get('ex_date') or '')[:10]
        nominal=e.get('event_ratio')
        if not d or nominal in (None,''):
            raise ValueError(f'missing event date/nominal ratio for {record.get("symbol")}')
        nominal=float(nominal)
        actual=factor_jump_ratio(factors,d)
        if nominal==0:
            raise ValueError('zero nominal event ratio')
        diff=abs(actual/nominal-1.0)*10000.0
        if diff>threshold_bp:
            x=dict(e)
            x['actual_factor_jump']=actual
            x['event_diff_bp']=diff
            out.append(x)
    return out


def _parse_sina_js(raw: bytes) -> list[dict]:
    text=raw.decode('utf-8-sig',errors='replace')
    m=re.search(r'=\s*(\{.*\})\s*;?\s*$',text,re.S)
    if not m:
        raise ValueError('cannot parse Sina qfq JS')
    obj=json.loads(m.group(1))
    rows=obj.get('data') or []
    if not rows:
        raise ValueError('empty Sina factor rows')
    return rows


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _fetch_pdf(url: str, attempts: int=3) -> tuple[bytes,int|None,int,str|None]:
    last=None
    for attempt in range(1,attempts+1):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
            with urllib.request.urlopen(req,timeout=30) as r:
                return r.read(),getattr(r,'status',None),attempt,None
        except Exception as e:
            last=f'{type(e).__name__}: {e}'
            if attempt<attempts: time.sleep(0.8*attempt)
    return b'',None,attempts,last


def _extract_pdf_text(pdf_path: pathlib.Path, txt_path: pathlib.Path) -> tuple[bool,str|None]:
    try:
        p=subprocess.run(['pdftotext','-layout',str(pdf_path),str(txt_path)],capture_output=True,text=True,timeout=60)
        if p.returncode!=0:
            return False,(p.stderr or p.stdout or f'pdftotext exit {p.returncode}')[-1000:]
        return txt_path.exists() and txt_path.stat().st_size>0,None
    except Exception as e:
        return False,f'{type(e).__name__}: {e}'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--closure-dir',required=True)
    ap.add_argument('--index-dir',required=True)
    ap.add_argument('--source-census-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--threshold-bp',type=float,default=5.0)
    ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args()

    closure=json.loads(_find_unique(pathlib.Path(args.closure_dir),'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json').read_text(encoding='utf-8'))
    idx=json.loads(_find_unique(pathlib.Path(args.index_dir),'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json').read_text(encoding='utf-8'))
    if idx.get('scope_symbol_n')!=87:
        raise RuntimeError('CNINFO standard index scope is not 87')
    idx_by={r['symbol']:r for r in idx.get('records') or []}

    exact_records={r['symbol']:r for r in closure.get('records') or [] if r.get('status') in {'REVIEW_GLOBAL_LEDGER_EXACT_TERMS','REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'} and r.get('symbol') not in SPECIAL_RESTRUCTURING_11}
    if len(exact_records)!=87:
        raise RuntimeError(f'expected 87 standard exact records; got {len(exact_records)}')

    source_root=pathlib.Path(args.source_census_dir)
    candidate_rows=[]
    for symbol,record in sorted(exact_records.items()):
        code,ex=symbol.split('.')
        p=_find_unique(source_root,f'{code}_{ex}_sina_qfq.js')
        factors=_parse_sina_js(p.read_bytes())
        for e in select_candidate_events(record,factors,args.threshold_bp):
            match=(idx_by.get(symbol,{}).get('matches') or {}).get(e['ex_date'])
            candidate_rows.append({'symbol':symbol,'event':e,'announcement':match})

    if len(candidate_rows)!=89:
        raise RuntimeError(f'expected 89 >5bp standard events; got {len(candidate_rows)}')

    out=pathlib.Path(args.out_dir); raw=out/'raw_pdf'; txt=out/'text'; raw.mkdir(parents=True,exist_ok=True); txt.mkdir(parents=True,exist_ok=True)
    unique={}
    for row in candidate_rows:
        ann=row['announcement']
        if ann:
            key=str(ann.get('announcementId') or ann.get('adjunctUrl'))
            unique[key]=ann

    def fetch_one(k,ann):
        url=announcement_pdf_url(ann)
        b,http,attempt,err=_fetch_pdf(url)
        suffix=str(ann.get('announcementId') or k).replace('/','_')
        pdf=raw/f'{suffix}.pdf'; textp=txt/f'{suffix}.txt'
        if b: pdf.write_bytes(b)
        ok=False; texterr=None; terms=None
        if b:
            ok,texterr=_extract_pdf_text(pdf,textp)
            if ok:
                try: terms=extract_effective_terms(textp.read_text(encoding='utf-8',errors='replace'))
                except Exception as e: texterr=f'parser:{type(e).__name__}: {e}'
        return k,{'url':url,'http_status':http,'attempts':attempt,'error':err,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest() if b else None,
                  'pdf_file':pdf.name if b else None,'text_file':textp.name if ok else None,'text_extract_ok':ok,'text_error':texterr,'effective_terms':terms}

    fetched={}
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        fut={pool.submit(fetch_one,k,a):k for k,a in unique.items()}
        for i,f in enumerate(as_completed(fut),1):
            k,res=f.result(); fetched[k]=res
            if i%20==0 or i==len(unique): print(json.dumps({'pdf_progress':i,'total':len(unique)},ensure_ascii=False),flush=True)

    records=[]
    for row in candidate_rows:
        ann=row['announcement']; key=str((ann or {}).get('announcementId') or (ann or {}).get('adjunctUrl') or '')
        records.append({
            'symbol':row['symbol'],'ex_date':row['event']['ex_date'],'event_diff_bp':row['event']['event_diff_bp'],
            'actual_factor_jump':row['event']['actual_factor_jump'],'nominal_event_ratio':row['event']['event_ratio'],
            'announcement':ann,'pdf_evidence':fetched.get(key) if key else None,
        })
    matched=sum(r['announcement'] is not None for r in records)
    pdf_ok=sum((r.get('pdf_evidence') or {}).get('text_extract_ok') is True for r in records)
    effective=sum(bool((r.get('pdf_evidence') or {}).get('effective_terms') and any((r['pdf_evidence']['effective_terms'].get(k) is not None) for k in ('cash_per_share','cap_ratio'))) for r in records)
    report={
        'artifact':'CNINFO_STANDARD_EXACT_PDF_EVIDENCE_V481','version':'V4.81','threshold_bp':args.threshold_bp,
        'candidate_event_n':len(records),'candidate_symbol_n':len({r['symbol'] for r in records}),
        'announcement_matched_event_n':matched,'pdf_text_ok_event_n':pdf_ok,'effective_term_event_n':effective,
        'unique_announcement_n':len(unique),'records':records,
        'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,
    }
    (out/'CNINFO_STANDARD_EXACT_PDF_EVIDENCE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['candidate_event_n','candidate_symbol_n','announcement_matched_event_n','pdf_text_ok_event_n','effective_term_event_n','unique_announcement_n']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
