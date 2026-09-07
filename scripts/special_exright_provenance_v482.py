from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time

from cninfo_exact_term_v481 import resolve_orgid, query_cninfo, announcement_pdf_url
from materialize_standard_exact_pdfs_v481 import _fetch_pdf, _extract_pdf_text

VERSION='V4.82'
SEARCH_KEYS=('除权参考价格','除权参考价','资本公积金转增股本','重整','除权')
TITLE_TERMS=(('除权',10),('资本公积',8),('重整',7),('转增',6),('实施',4),('复牌',2))


def _date_ms(item):
    try:
        return dt.datetime.fromtimestamp(float(item.get('announcementTime'))/1000,tz=dt.timezone.utc).date()
    except Exception:
        return None


def rank_candidates(items:list[dict], event_date:str)->list[dict]:
    ed=dt.date.fromisoformat(str(event_date)[:10])
    scored=[]
    for item in items or []:
        if not isinstance(item,dict): continue
        title=re.sub(r'<[^>]+>','',str(item.get('announcementTitle') or '')).replace(' ','')
        ad=_date_ms(item)
        if ad is None: continue
        gap=(ed-ad).days
        if gap < -2 or gap > 90: continue
        score=sum(w for term,w in TITLE_TERMS if term in title)
        if score<=0: continue
        scored.append((-score,abs(gap),-ad.toordinal(),item))
    scored.sort(key=lambda x:(x[0],x[1],x[2]))
    return [x[3] for x in scored]


def text_matches_reference(text:str, adjusted_reference_price:float)->bool:
    s=re.sub(r'\s+','',str(text or ''))
    if '除权' not in s or ('参考价' not in s and '参考价格' not in s): return False
    target=float(adjusted_reference_price)
    # Require the number to occur near an ex-right reference-price phrase, avoiding an
    # unrelated close/transaction price elsewhere in a long restructuring notice.
    patterns=[r'除权.{0,40}参考价(?:格)?.{0,80}',r'参考价(?:格)?.{0,80}除权.{0,40}']
    contexts=[]
    for pat in patterns:
        contexts.extend(m.group(0) for m in re.finditer(pat,s))
    if not contexts:
        # Common wording: "调整后的除权价格为..." without the word 参考.
        contexts.extend(m.group(0) for m in re.finditer(r'调整后.{0,20}除权.{0,20}价格.{0,80}',s))
    for c in contexts:
        for raw in re.findall(r'(?<!\d)(\d+(?:\.\d+)?)(?!\d)',c):
            try:
                if abs(float(raw)-target)<=0.005: return True
            except Exception: pass
    return False


def make_provenance_row(ledger:dict, announcement:dict, sha256:str)->dict:
    if not re.fullmatch(r'[0-9a-fA-F]{64}',str(sha256 or '')): raise ValueError('invalid materialized sha256')
    aid=str(announcement.get('announcementId') or '').strip()
    path=str(announcement.get('adjunctUrl') or '').strip()
    if not aid or not path: raise ValueError('CNINFO announcement lacks id/PDF path')
    return {
        'symbol':str(ledger.get('symbol') or '').upper(),
        'ex_date':str(ledger.get('ex_date') or '')[:10],
        'adjusted_reference_price':float(ledger['adjusted_reference_price']),
        'expected_prev_close':float(ledger['expected_prev_close']) if ledger.get('expected_prev_close') is not None else None,
        'source':'CNINFO_OFFICIAL_PDF','announcement_id':aid,
        'announcement_title':re.sub(r'<[^>]+>','',str(announcement.get('announcementTitle') or '')),
        'adjunct_url':path,'pdf_url':announcement_pdf_url(announcement),
        'materialized_sha256':str(sha256).lower(),
    }


def _find_unique(root:pathlib.Path,name:str)->pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1: raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _window(event_date:str,prior:int=75,forward:int=2):
    d=dt.date.fromisoformat(str(event_date)[:10])
    return (d-dt.timedelta(days=prior)).isoformat(),(d+dt.timedelta(days=forward)).isoformat()


def collect_one(row:dict,raw_dir:pathlib.Path,pdf_dir:pathlib.Path,text_dir:pathlib.Path,request_interval:float=1.5)->dict:
    symbol=str(row['symbol']).upper(); code=symbol.split('.')[0]; event=str(row['ex_date'])[:10]
    result={'symbol':symbol,'ex_date':event,'adjusted_reference_price':float(row['adjusted_reference_price']),
            'status':'UNRESOLVED','queries':[],'candidate_n':0,'validated_candidate_n':0,'provenance':None,'error':None}
    try:
        org=resolve_orgid(code); orgid=org['orgid']
        start,end=_window(event)
        all_items={}
        for qi,key in enumerate(SEARCH_KEYS):
            try:
                q=query_cninfo(code,start,end,orgid=orgid,searchkey=key,timeout=45,attempts=4)
                raw=q['raw']; fn=f'{code}_{event}_{qi}_{hashlib.sha256(key.encode()).hexdigest()[:8]}.json'; (raw_dir/fn).write_bytes(raw)
                items=(q.get('json') or {}).get('announcements') or []
                result['queries'].append({'searchkey':key,'http_status':q.get('http_status'),'announcement_n':len(items),'raw_file':fn,'sha256':hashlib.sha256(raw).hexdigest(),'error':None})
                for item in items:
                    stable=str(item.get('announcementId') or item.get('adjunctUrl') or '')
                    if stable: all_items[stable]=item
            except Exception as e:
                result['queries'].append({'searchkey':key,'error':f'{type(e).__name__}: {e}'})
            if request_interval>0: time.sleep(request_interval)
        ranked=rank_candidates(list(all_items.values()),event); result['candidate_n']=len(ranked)
        for idx,item in enumerate(ranked[:12]):
            try:
                body,http,attempts,error=_fetch_pdf(announcement_pdf_url(item),attempts=3)
                if not body: continue
                aid=str(item.get('announcementId') or f'cand{idx}')
                pdf=pdf_dir/f'{code}_{event}_{aid}.pdf'; txt=text_dir/f'{code}_{event}_{aid}.txt'
                pdf.write_bytes(body); ok,terr=_extract_pdf_text(pdf,txt)
                if not ok: continue
                text=txt.read_text(encoding='utf-8',errors='replace')
                if not text_matches_reference(text,float(row['adjusted_reference_price'])): continue
                sha=hashlib.sha256(body).hexdigest(); prov=make_provenance_row(row,item,sha)
                prov.update({'pdf_file':pdf.name,'text_file':txt.name,'http_status':http,'download_attempts':attempts})
                result['validated_candidate_n']+=1; result['provenance']=prov; result['status']='PASS_CNINFO_MATERIALIZED'; break
            except Exception:
                continue
        return result
    except Exception as e:
        result['error']=f'{type(e).__name__}: {e}'; return result


def collect(ledger_path:pathlib.Path,out_dir:pathlib.Path,request_interval:float=1.5)->dict:
    obj=json.loads(ledger_path.read_text(encoding='utf-8')); rows=obj.get('records') or []
    if len(rows)!=11: raise ValueError(f'expected 11 special ledger rows; got {len(rows)}')
    raw=out_dir/'raw_query'; pdf=out_dir/'pdf'; txt=out_dir/'text'
    for p in (raw,pdf,txt): p.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,row in enumerate(rows,1):
        r=collect_one(row,raw,pdf,txt,request_interval); records.append(r)
        print(json.dumps({'progress':i,'total':len(rows),'symbol':r['symbol'],'status':r['status'],'candidate_n':r['candidate_n']},ensure_ascii=False),flush=True)
    passed=[r for r in records if r['status']=='PASS_CNINFO_MATERIALIZED']
    report={'artifact':'SPECIAL_EXRIGHT_PROVENANCE_V482','version':VERSION,'target_n':11,'materialized_n':len(passed),'unresolved_n':11-len(passed),
            'records':records,'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False}
    (out_dir/'SPECIAL_EXRIGHT_PROVENANCE_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target_n':11,'materialized_n':len(passed),'unresolved_n':11-len(passed),'unresolved_symbols':[r['symbol'] for r in records if r['status']!='PASS_CNINFO_MATERIALIZED']},ensure_ascii=False,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--ledger',required=True); ap.add_argument('--out-dir',required=True); ap.add_argument('--request-interval',type=float,default=1.5)
    a=ap.parse_args(); collect(pathlib.Path(a.ledger),pathlib.Path(a.out_dir),a.request_interval)

if __name__=='__main__': main()
