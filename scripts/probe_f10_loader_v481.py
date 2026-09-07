from __future__ import annotations
import hashlib, json, pathlib, re, urllib.request
OUT=pathlib.Path('artifact_f10_loader_probe_v481'); OUT.mkdir(parents=True,exist_ok=True)
BASE='https://emweb.securities.eastmoney.com'
PATHS=[
 '/PC_HSF10/Content/js/lib/qphf.js?v=1.0.2.7054',
 '/PC_HSF10/Content/js/lib/f10pcCommon.min.js?v=1.0.2.7054',
 '/PC_HSF10/Content/js/lib/HisAcc.js?v=1.0.2.7054',
 '/PC_HSF10/Content/js/lib/formatData.js?v=1.0.2.7054',
]
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':BASE+'/PC_HSF10/BonusFinancing/Index?code=SH601989&type=web'})
 try:
  with urllib.request.urlopen(req,timeout=25) as r:
   raw=r.read(); return True,getattr(r,'status',None),r.headers.get('Content-Type'),raw,None
 except Exception as e: return False,None,None,b'',f'{type(e).__name__}: {e}'
def main():
 rows=[]
 for i,p in enumerate(PATHS):
  url=BASE+p; ok,status,ct,raw,err=get(url)
  rec={'url':url,'ok':ok,'status':status,'content_type':ct,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest() if raw else None,'error':err}
  if raw:
   fn=OUT/f'loader_{i}.js'; fn.write_bytes(raw); rec['raw_file']=fn.name
   txt=raw.decode('utf-8',errors='replace')
   lines=[]
   for n,line in enumerate(txt.splitlines(),1):
    if any(k in line.lower() for k in ('loader','base','path','new/','content/js','static','resource','use:function','use =')):
     lines.append({'line':n,'text':line[:1500]})
   rec['interesting_lines']=lines[:500]
   rec['urls']=sorted(set(re.findall(r'https?://[^\"\'\s)]+',txt)))[:300]
  rows.append(rec)
 report={'artifact':'F10_LOADER_PROBE_V481','version':'V4.81','formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,'files':rows}
 (OUT/'F10_LOADER_PROBE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
