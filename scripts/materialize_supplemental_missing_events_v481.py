from __future__ import annotations

import hashlib
import json
import pathlib
import re
import time
import urllib.request

OUT=pathlib.Path('artifact_supplemental_missing_events_v481'); RAW=OUT/'raw'; RAW.mkdir(parents=True,exist_ok=True)
SPECS=[
 {'symbol':'000564.SZ','target_date':'2021-12-31','expected_term':'10转22.035714','source':'EASTMONEY_STOCKCALENDAR','url':'https://data.eastmoney.com/stockcalendar/000564.html'},
 {'symbol':'000981.SZ','target_date':'2022-02-25','expected_term':'10转增14.82','source':'SOHU_MAJOR_EVENTS','url':'https://q.stock.sohu.com/cn/000981/bw_50.shtml'},
 {'symbol':'002076.SZ','target_date':'2022-12-21','expected_term':'10转增4.58796','source':'SOHU_MAJOR_EVENTS','url':'https://q.stock.sohu.com/cn/002076/bw_38.shtml'},
 {'symbol':'300117.SZ','target_date':'2020-07-20','expected_term':'0.03','source':'SINA_SHAREBONUS','url':'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/300117.phtml'},
 {'symbol':'600070.SH','target_date':'2020-07-10','expected_term':'0.8','source':'SINA_SHAREBONUS','url':'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/600070.phtml'},
 {'symbol':'600190.SH','target_date':'2020-07-02','expected_term':'0.2','source':'SINA_SHAREBONUS','url':'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/600190.phtml'},
]

def fetch(url):
    last=None
    for attempt in range(1,4):
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.5'})
        try:
            with urllib.request.urlopen(req,timeout=25) as r:
                raw=r.read(); return raw,getattr(r,'status',None),r.headers.get('Content-Type'),attempt,None
        except Exception as e:
            last=f'{type(e).__name__}: {e}'; time.sleep(0.5*attempt)
    return b'',None,None,3,last

def decode(raw):
    for enc in ('utf-8-sig','gb18030','gbk'):
        try: return raw.decode(enc),enc
        except UnicodeDecodeError: pass
    return raw.decode('utf-8',errors='replace'),'utf-8-replace'

def compact_text(html):
    text=re.sub(r'<script\b[^>]*>.*?</script>',' ',html,flags=re.I|re.S)
    text=re.sub(r'<style\b[^>]*>.*?</style>',' ',text,flags=re.I|re.S)
    text=re.sub(r'<[^>]+>',' ',text)
    text=text.replace('&nbsp;',' ')
    text=re.sub(r'\s+',' ',text)
    return text.strip()

def main():
    rows=[]
    for s in SPECS:
        raw,status,ct,attempt,err=fetch(s['url']); code,ex=s['symbol'].split('.')
        fn=f'{code}_{ex}_{s["source"].lower()}.html'
        if raw: (RAW/fn).write_bytes(raw)
        html,enc=decode(raw) if raw else ('',None)
        text=compact_text(html)
        date_pos=text.find(s['target_date']); term_pos=text.find(s['expected_term'])
        # capture a bounded context around the target date; this is evidence summary only, raw bytes remain canonical.
        if date_pos>=0:
            lo=max(0,date_pos-500); hi=min(len(text),date_pos+1200); context=text[lo:hi]
        else: context=''
        target_term_near=(s['expected_term'] in context) if context else False
        rec={**s,'http_status':status,'content_type':ct,'attempts':attempt,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest() if raw else None,'raw_file':fn if raw else None,'decode':enc,'target_date_found':date_pos>=0,'expected_term_found':term_pos>=0,'target_term_near':target_term_near,'context':context,'error':err}
        rec['status']='SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE' if rec['target_date_found'] and (rec['expected_term_found'] or rec['target_term_near']) else 'SUPPLEMENTAL_EVIDENCE_UNRESOLVED'
        rows.append(rec)
        print(json.dumps({'symbol':s['symbol'],'status':rec['status'],'date':rec['target_date_found'],'term':rec['expected_term_found'],'near':rec['target_term_near'],'http':status},ensure_ascii=False),flush=True)
    passed=sum(r['status']=='SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE' for r in rows)
    report={'artifact':'SUPPLEMENTAL_MISSING_EVENT_EVIDENCE_V481','version':'V4.81','target_n':6,'positive_n':passed,'unresolved_n':6-passed,'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,'records':rows}
    (OUT/'SUPPLEMENTAL_MISSING_EVENT_EVIDENCE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target_n':6,'positive_n':passed,'unresolved_n':6-passed},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
