from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from urllib.parse import urlparse

from materialize_standard_exact_pdfs_v481 import _fetch_pdf, _extract_pdf_text
from special_exright_provenance_v482 import text_matches_reference, make_provenance_row

VERSION='V4.82'


def _key(row:dict)->tuple[str,str]:
    symbol=str(row.get('symbol') or '').upper()
    ex_date=str(row.get('ex_date') or '')[:10]
    if not symbol or len(ex_date)!=10: raise ValueError('missing symbol/ex_date')
    return symbol,ex_date


def validate_manifest(ledger_rows:list[dict],manifest_rows:list[dict],expected_n:int=11)->dict[tuple[str,str],dict]:
    if len(ledger_rows or [])!=expected_n or len(manifest_rows or [])!=expected_n:
        raise ValueError('direct manifest partition mismatch')
    ledger_keys={_key(r) for r in ledger_rows}
    out={}
    for raw in manifest_rows:
        row=dict(raw); key=_key(row)
        if key in out: raise ValueError(f'duplicate manifest key {key}')
        url=str(row.get('pdf_url') or '')
        p=urlparse(url)
        if p.scheme!='https' or p.netloc!='static.cninfo.com.cn' or not p.path.lower().endswith('.pdf'):
            raise ValueError(f'{key}: non-official CNINFO PDF URL')
        aid=str(row.get('announcement_id') or '').strip()
        if not aid or aid not in p.path: raise ValueError(f'{key}: announcement id/url mismatch')
        out[key]=row
    if set(out)!=ledger_keys: raise ValueError('manifest keys do not exactly match special ledger')
    return out


def materialize(ledger_path:pathlib.Path,manifest_path:pathlib.Path,out_dir:pathlib.Path)->dict:
    ledger_obj=json.loads(ledger_path.read_text(encoding='utf-8'))
    manifest_obj=json.loads(manifest_path.read_text(encoding='utf-8'))
    ledger=ledger_obj.get('records') or []; manifest=manifest_obj.get('records') or []
    by=validate_manifest(ledger,manifest,11)
    pdf_dir=out_dir/'pdf'; text_dir=out_dir/'text'; pdf_dir.mkdir(parents=True,exist_ok=True); text_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,row in enumerate(ledger,1):
        key=_key(row); m=by[key]; url=m['pdf_url']; aid=m['announcement_id']
        result={'symbol':key[0],'ex_date':key[1],'adjusted_reference_price':float(row['adjusted_reference_price']),
                'status':'UNRESOLVED','provenance':None,'error':None}
        try:
            body,http,attempts,error=_fetch_pdf(url,attempts=3)
            if not body: raise ValueError(error or 'empty official PDF')
            pdf=pdf_dir/f'{key[0].split(".")[0]}_{key[1]}_{aid}.pdf'; txt=text_dir/f'{key[0].split(".")[0]}_{key[1]}_{aid}.txt'
            pdf.write_bytes(body); ok,terr=_extract_pdf_text(pdf,txt)
            if not ok: raise ValueError(terr or 'pdftotext failed')
            text=txt.read_text(encoding='utf-8',errors='replace')
            if not text_matches_reference(text,float(row['adjusted_reference_price'])):
                raise ValueError('official PDF did not validate adjusted reference price')
            ann={'announcementId':aid,'announcementTitle':'PINNED_CNINFO_OFFICIAL_SPECIAL_EXRIGHT','adjunctUrl':url.split('https://static.cninfo.com.cn/',1)[1]}
            sha=hashlib.sha256(body).hexdigest(); prov=make_provenance_row(row,ann,sha)
            prov.update({'pdf_file':pdf.name,'text_file':txt.name,'http_status':http,'download_attempts':attempts})
            result['status']='PASS_CNINFO_MATERIALIZED'; result['provenance']=prov
        except Exception as exc:
            result['error']=f'{type(exc).__name__}: {exc}'
        records.append(result)
        print(json.dumps({'progress':i,'total':11,'symbol':key[0],'status':result['status'],'error':result['error']},ensure_ascii=False),flush=True)
    passed=sum(r['status']=='PASS_CNINFO_MATERIALIZED' for r in records)
    report={'artifact':'SPECIAL_EXRIGHT_PROVENANCE_V482','version':VERSION,'target_n':11,'materialized_n':passed,'unresolved_n':11-passed,
            'records':records,'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'SPECIAL_EXRIGHT_PROVENANCE_V482.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'materialized_n':passed,'unresolved_n':11-passed,'unresolved_symbols':[r['symbol'] for r in records if r['status']!='PASS_CNINFO_MATERIALIZED']},ensure_ascii=False,indent=2))
    return report


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--ledger',required=True); ap.add_argument('--manifest',required=True); ap.add_argument('--out-dir',required=True)
    a=ap.parse_args(); materialize(pathlib.Path(a.ledger),pathlib.Path(a.manifest),pathlib.Path(a.out_dir))


if __name__=='__main__': main()
