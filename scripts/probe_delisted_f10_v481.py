from __future__ import annotations

import hashlib
import json
import pathlib
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OUT=pathlib.Path('artifact_delisted_f10_probe_v481')
OUT.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36'
CONTROLS={
    '601989.SH':['2022-08-23','2024-08-01','2025-06-18'],
    '600190.SH':['2020-07-02','2021-06-25','2022-06-24','2024-06-26'],
    '002002.SZ':['2020-07-16','2021-06-22'],
    '002013.SZ':['2020-08-19','2021-06-23','2022-06-09'],
}


def sha256(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()


def em_code(symbol:str)->str:
    code,ex=symbol.split('.')
    return ex+code


def fetch(url:str,attempts:int=3):
    last={'ok':False,'status':None,'body':b'','error':None,'attempts':0,'url':url,'content_type':None}
    for attempt in range(1,attempts+1):
        try:
            req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,*/*','Referer':'https://emweb.securities.eastmoney.com/'})
            with urlopen(req,timeout=30) as r:
                b=r.read()
                return {'ok':True,'status':getattr(r,'status',200),'body':b,'error':None,'attempts':attempt,'url':url,'content_type':r.headers.get('Content-Type')}
        except HTTPError as e:
            try:b=e.read()
            except Exception:b=b''
            last={'ok':False,'status':e.code,'body':b,'error':f'HTTPError: {e}','attempts':attempt,'url':url,'content_type':e.headers.get('Content-Type') if e.headers else None}
        except Exception as e:
            last={'ok':False,'status':None,'body':b'','error':f'{type(e).__name__}: {e}','attempts':attempt,'url':url,'content_type':None}
        if attempt<attempts: time.sleep(0.8*attempt)
    return last


def decode(body:bytes)->str:
    for enc in ('utf-8','gb18030'):
        try:return body.decode(enc)
        except UnicodeDecodeError: pass
    return body.decode('utf-8',errors='replace')


def extract_candidates(text:str):
    patterns=[
        r'https?://[^"\'<>\s]+',
        r'[A-Za-z0-9_./-]*(?:Bonus|Dividend|Financing|Ajax|ajax|bonus|dividend)[A-Za-z0-9_?&=./%-]*',
        r'/PC_HSF10/[^"\'<>\s]+',
    ]
    out=set()
    for pat in patterns:
        for m in re.findall(pat,text,re.I):
            s=m if isinstance(m,str) else ''.join(m)
            if s and len(s)<500: out.add(s)
    return sorted(out)


def probe(symbol:str,dates:list[str]):
    ec=em_code(symbol)
    urls=[
        f'https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/Index?code={ec}&type=web',
        f'https://emweb.securities.eastmoney.com/BonusFinancing/Index?code={ec}&type=web',
    ]
    attempts=[]
    best=None
    for url in urls:
        r=fetch(url)
        body=r['body']; text=decode(body) if body else ''
        name=f'{symbol.replace(".","_")}_{len(attempts)}.html'
        (OUT/name).write_bytes(body)
        a={
            'url':url,'ok':r['ok'],'http_status':r['status'],'content_type':r['content_type'],
            'bytes':len(body),'sha256':sha256(body),'attempts':r['attempts'],'error':r['error'],
            'raw_file':name,'title':(re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S).group(1).strip() if re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S) else None),
            'target_date_hits':{d:(d in text) for d in dates},
            'candidate_links':extract_candidates(text)[:500],
            'contains_bonus_text':bool(re.search(r'分红|派息|送股|转增|配股|BonusFinancing|Dividend',text,re.I)),
        }
        attempts.append(a)
        if best is None or sum(a['target_date_hits'].values())>sum(best['target_date_hits'].values()) or (a['bytes']>best['bytes'] and sum(a['target_date_hits'].values())==sum(best['target_date_hits'].values())):
            best=a
    return {'symbol':symbol,'expected_dates':dates,'attempts':attempts,'best':best}


def main():
    rows=[probe(s,d) for s,d in CONTROLS.items()]
    doc={
        'artifact':'DELISTED_F10_PROBE_V481','version':'V4.81',
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'purpose':'Feasibility probe for historical corporate-action recovery of delisted symbols. No Formal promotion.',
        'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,
        'controls':rows,
    }
    (OUT/'DELISTED_F10_PROBE_V481.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({s['symbol']:{'best_url':s['best']['url'],'status':s['best']['http_status'],'bytes':s['best']['bytes'],'hits':s['best']['target_date_hits'],'candidates_n':len(s['best']['candidate_links'])} for s in rows},ensure_ascii=False,indent=2))
    if not any(c['best']['ok'] and c['best']['bytes']>0 for c in rows): raise SystemExit(2)

if __name__=='__main__': main()
