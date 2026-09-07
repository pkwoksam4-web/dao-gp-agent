from __future__ import annotations
import hashlib, json, pathlib, urllib.parse, urllib.request

OUT=pathlib.Path('artifact_f10_pageajax_probe_v481'); OUT.mkdir(parents=True,exist_ok=True)
CONTROLS={
 '601989.SH':['2022-08-23','2024-08-01','2025-06-18'],
 '600190.SH':['2020-07-02','2021-06-25','2022-06-24','2024-06-26'],
 '002002.SZ':['2020-07-16','2021-06-22'],
 '002013.SZ':['2020-08-19','2021-06-23','2022-06-09'],
}
BASES=[
 'https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/PageAjax',
 'https://emweb.securities.eastmoney.com/BonusFinancing/PageAjax',
]

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/Index?type=web&code=SH601989','X-Requested-With':'XMLHttpRequest'})
 try:
  with urllib.request.urlopen(req,timeout=25) as r:
   raw=r.read(); return {'ok':True,'status':getattr(r,'status',None),'content_type':r.headers.get('Content-Type'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'raw':raw,'error':None}
 except Exception as e:
  return {'ok':False,'status':None,'content_type':None,'bytes':0,'sha256':None,'raw':b'','error':f'{type(e).__name__}: {e}'}

def scan_dates(obj, targets):
 text=json.dumps(obj,ensure_ascii=False,sort_keys=True) if obj is not None else ''
 return {d:(d in text) for d in targets}

def main():
 controls=[]
 for symbol,targets in CONTROLS.items():
  code=symbol.split('.')[0]; exch=symbol.split('.')[1]; sc=('SH' if exch=='SH' else 'SZ')+code
  attempts=[]
  for bi,base in enumerate(BASES):
   url=base+'?'+urllib.parse.urlencode({'code':sc})
   rec=fetch(url); raw=rec.pop('raw')
   rec['url']=url
   if raw:
    fn=f'{code}_{exch}_{bi}.json'; (OUT/fn).write_bytes(raw); rec['raw_file']=fn
    try:
     obj=json.loads(raw.decode('utf-8-sig')); rec['json_ok']=True; rec['top_type']=type(obj).__name__; rec['keys']=sorted(obj.keys()) if isinstance(obj,dict) else None
     rec['target_date_hits']=scan_dates(obj,targets)
     # summarize likely collections without altering evidence
     if isinstance(obj,dict):
      rec['collections']={k:len(v) for k,v in obj.items() if isinstance(v,list)}
     else: rec['collections']={}
    except Exception as e:
     rec['json_ok']=False; rec['json_error']=f'{type(e).__name__}: {e}'; rec['target_date_hits']={d:False for d in targets}; rec['collections']={}
   attempts.append(rec)
  controls.append({'symbol':symbol,'expected_dates':targets,'attempts':attempts})
 report={'artifact':'F10_PAGEAJAX_PROBE_V481','version':'V4.81','formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,'controls':controls}
 (OUT/'F10_PAGEAJAX_PROBE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
