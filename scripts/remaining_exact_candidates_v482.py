from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from cninfo_effective_terms_v481 import extract_effective_terms
from cninfo_exact_term_v481 import announcement_pdf_url
from materialize_standard_exact_pdfs_v481 import _extract_pdf_text, _parse_sina_js, factor_jump_ratio

EXPECTED_REMAINING_SYMBOL_N = 52
EXPECTED_MATCHED_EVENT_N = 203
EXPECTED_MATCHED_SYMBOL_N = 36


def select_matched_unoverridden(
    remaining_symbols: set[str],
    frozen_closure: dict,
    cninfo_index: dict,
    already_overridden: set[tuple[str, str]],
) -> list[dict]:
    remaining={str(s).upper() for s in remaining_symbols}
    frozen_by={str(r.get('symbol') or '').upper():r for r in (frozen_closure.get('records') or [])}
    missing=sorted(remaining-set(frozen_by))
    if missing:
        raise ValueError(f'remaining symbols missing from frozen closure: {missing}')
    index_by={str(r.get('symbol') or '').upper():r for r in (cninfo_index.get('records') or [])}
    rows=[]
    for symbol in sorted(remaining):
        matches=(index_by.get(symbol,{}) or {}).get('matches') or {}
        for event in frozen_by[symbol].get('events') or []:
            ex_date=str(event.get('ex_date') or '')[:10]
            if not ex_date or (symbol,ex_date) in already_overridden:
                continue
            ann=matches.get(ex_date)
            if not ann:
                continue
            rows.append({
                'symbol':symbol,
                'ex_date':ex_date,
                'event':dict(event),
                'announcement':ann,
            })
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
            if attempt<attempts:
                time.sleep(0.8*attempt)
    return b'',None,attempts,last


def materialize(
    frozen_closure_dir: pathlib.Path,
    current_closure_dir: pathlib.Path,
    index_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
    out_dir: pathlib.Path,
    workers: int=6,
) -> dict:
    frozen=json.loads(_find_unique(frozen_closure_dir,'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json').read_text(encoding='utf-8'))
    current=json.loads(_find_unique(current_closure_dir,'EFFECTIVE_TERM_CLOSURE_V482.json').read_text(encoding='utf-8'))
    index=json.loads(_find_unique(index_dir,'CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json').read_text(encoding='utf-8'))
    remaining=set(current.get('remaining_symbols') or [])
    if len(remaining)!=EXPECTED_REMAINING_SYMBOL_N:
        raise ValueError(f'expected {EXPECTED_REMAINING_SYMBOL_N} remaining symbols; got {len(remaining)}')
    already={(str(r.get('symbol') or '').upper(),str(r.get('ex_date') or '')[:10]) for r in (current.get('event_overrides') or [])}
    candidates=select_matched_unoverridden(remaining,frozen,index,already)
    if len(candidates)!=EXPECTED_MATCHED_EVENT_N:
        raise ValueError(f'expected {EXPECTED_MATCHED_EVENT_N} matched unoverridden events; got {len(candidates)}')
    if len({r['symbol'] for r in candidates})!=EXPECTED_MATCHED_SYMBOL_N:
        raise ValueError('matched-symbol partition changed')

    out=out_dir; raw=out/'raw_pdf'; txt=out/'text'; raw.mkdir(parents=True,exist_ok=True); txt.mkdir(parents=True,exist_ok=True)
    unique={}
    for row in candidates:
        ann=row['announcement']; key=str(ann.get('announcementId') or ann.get('adjunctUrl') or '')
        if not key: raise ValueError(f"{row['symbol']} {row['ex_date']}: announcement lacks identity")
        unique[key]=ann
    if len(unique)!=EXPECTED_MATCHED_EVENT_N:
        raise ValueError('expected one unique official implementation announcement per candidate event')

    def fetch_one(key,ann):
        url=announcement_pdf_url(ann)
        b,http,attempt,err=_fetch_pdf(url)
        suffix=str(ann.get('announcementId') or key).replace('/','_')
        pdf=raw/f'{suffix}.pdf'; textp=txt/f'{suffix}.txt'
        if b: pdf.write_bytes(b)
        ok=False; texterr=None; terms=None
        if b:
            ok,texterr=_extract_pdf_text(pdf,textp)
            if ok:
                try:
                    terms=extract_effective_terms(textp.read_text(encoding='utf-8',errors='replace'))
                except Exception as e:
                    texterr=f'parser:{type(e).__name__}: {e}'
        return key,{
            'url':url,'http_status':http,'attempts':attempt,'error':err,'bytes':len(b),
            'sha256':hashlib.sha256(b).hexdigest() if b else None,
            'pdf_file':pdf.name if b else None,'text_file':textp.name if ok else None,
            'text_extract_ok':ok,'text_error':texterr,'effective_terms':terms,
        }

    fetched={}
    with ThreadPoolExecutor(max_workers=max(1,workers)) as pool:
        fut={pool.submit(fetch_one,k,a):k for k,a in unique.items()}
        for n,f in enumerate(as_completed(fut),1):
            key,res=f.result(); fetched[key]=res
            if n%25==0 or n==len(unique):
                print(json.dumps({'pdf_progress':n,'total':len(unique)},ensure_ascii=False),flush=True)

    source_root=source_census_dir
    factor_cache={}
    records=[]
    for row in candidates:
        symbol=row['symbol']; code,exchange=symbol.split('.')
        if symbol not in factor_cache:
            factor_cache[symbol]=_parse_sina_js(_find_unique(source_root,f'{code}_{exchange}_sina_qfq.js').read_bytes())
        actual=factor_jump_ratio(factor_cache[symbol],row['ex_date'])
        nominal=float(row['event']['event_ratio'])
        ann=row['announcement']; key=str(ann.get('announcementId') or ann.get('adjunctUrl'))
        records.append({
            'symbol':symbol,'ex_date':row['ex_date'],
            'nominal_event_ratio':nominal,'actual_factor_jump':actual,
            'nominal_event_diff_bp':abs(actual/nominal-1.0)*10000.0,
            'announcement':ann,'pdf_evidence':fetched.get(key),
        })

    pdf_ok=sum((r.get('pdf_evidence') or {}).get('text_extract_ok') is True for r in records)
    effective=sum(bool((r.get('pdf_evidence') or {}).get('effective_terms') and any((r['pdf_evidence']['effective_terms'].get(k) is not None) for k in ('cash_per_share','cap_ratio'))) for r in records)
    report={
        'artifact':'REMAINING_EXACT_MATCHED_PDF_EVIDENCE_V482','version':'V4.82',
        'remaining_symbol_n':len(remaining),'matched_candidate_event_n':len(records),
        'matched_candidate_symbol_n':len({r['symbol'] for r in records}),
        'unique_announcement_n':len(unique),'pdf_text_ok_event_n':pdf_ok,
        'effective_term_event_n':effective,'records':records,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
    }
    (out/'REMAINING_EXACT_MATCHED_PDF_EVIDENCE_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frozen-closure-dir',required=True)
    ap.add_argument('--current-closure-dir',required=True)
    ap.add_argument('--index-dir',required=True)
    ap.add_argument('--source-census-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--workers',type=int,default=6)
    args=ap.parse_args()
    x=materialize(pathlib.Path(args.frozen_closure_dir),pathlib.Path(args.current_closure_dir),pathlib.Path(args.index_dir),pathlib.Path(args.source_census_dir),pathlib.Path(args.out_dir),args.workers)
    print(json.dumps({k:x[k] for k in ('remaining_symbol_n','matched_candidate_event_n','matched_candidate_symbol_n','unique_announcement_n','pdf_text_ok_event_n','effective_term_event_n')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
