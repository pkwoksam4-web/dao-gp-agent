from __future__ import annotations

import gzip
import hashlib
import json
import pathlib
import time
import urllib.parse
import urllib.request

OUT=pathlib.Path('artifact_f10_unresolved_history_v481'); RAW=OUT/'raw'; RAW.mkdir(parents=True,exist_ok=True)
TARGETS={
 '000564.SZ':'2021-12-31',
 '000981.SZ':'2022-02-25',
 '002076.SZ':'2022-12-21',
 '300117.SZ':'2020-07-20',
 '300262.SZ':'2020-08-11',
 '600070.SH':'2020-07-10',
 '600190.SH':'2020-07-02',
}
PAGEAJAX='https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/PageAjax'
REPORT='https://datacenter-web.eastmoney.com/api/data/v1/get'

def get(url, referer):
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0',
        'Referer':referer,
        'X-Requested-With':'XMLHttpRequest',
        'Accept-Encoding':'gzip, deflate',
    })
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            wire=r.read(); status=getattr(r,'status',None); hdr=dict(r.headers.items())
        decoded=wire
        encoding=(hdr.get('Content-Encoding') or hdr.get('content-encoding') or '').lower()
        gzip_wire=wire[:2]==b'\x1f\x8b'
        if gzip_wire or 'gzip' in encoding:
            decoded=gzip.decompress(wire)
        return {'ok':True,'status':status,'headers':hdr,'wire':wire,'decoded':decoded,'gzip':gzip_wire or 'gzip' in encoding,'error':None}
    except Exception as e:
        return {'ok':False,'status':None,'headers':{},'wire':b'','decoded':b'','gzip':False,'error':f'{type(e).__name__}: {e}'}

def save_payload(symbol,label,res):
    code,ex=symbol.split('.')
    wire_name=f'{code}_{ex}_{label}_wire.bin'; dec_name=f'{code}_{ex}_{label}_decoded.json'
    if res['wire']: (RAW/wire_name).write_bytes(res['wire'])
    if res['decoded']: (RAW/dec_name).write_bytes(res['decoded'])
    return wire_name if res['wire'] else None, dec_name if res['decoded'] else None

def parse_json(res):
    if not res['ok']: return None, res['error']
    try: return json.loads(res['decoded'].decode('utf-8-sig')), None
    except Exception as e: return None, f'{type(e).__name__}: {e}'

def report_url(symbol, filter_expr):
    params={
        'sortColumns':'PLAN_NOTICE_DATE','sortTypes':'-1','pageSize':'500','pageNumber':'1',
        'reportName':'RPT_SHAREBONUS_DET','columns':'ALL','quoteColumns':'','source':'WEB','client':'WEB',
        'filter':filter_expr,
    }
    return REPORT+'?'+urllib.parse.urlencode(params)

def rows_from_report(obj):
    if not isinstance(obj,dict): return []
    if obj.get('success') is not True or int(obj.get('code',-1))!=0: return []
    result=obj.get('result') or {}; rows=result.get('data') or []
    return rows if isinstance(rows,list) else []

def date_hits(rows,target):
    return [r for r in rows if isinstance(r,dict) and target in json.dumps(r,ensure_ascii=False,sort_keys=True)]

def main():
    records=[]
    for symbol,target in TARGETS.items():
        code,ex=symbol.split('.'); sc=('SH' if ex=='SH' else 'SZ')+code
        referer=f'https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/Index?type=web&code={sc}'
        rec={'symbol':symbol,'target_date':target,'pageajax':None,'report_attempts':[],'resolved':False,'resolved_source':None,'resolved_rows':[]}
        # First retry PageAjax with explicit gzip handling (fixes 300262 if compression was the only issue).
        purl=PAGEAJAX+'?'+urllib.parse.urlencode({'code':sc})
        pres=get(purl,referer); pobj,perr=parse_json(pres); wf,df=save_payload(symbol,'pageajax_gzip',pres)
        phits=[]
        if isinstance(pobj,dict):
            for cname,rows in pobj.items():
                if isinstance(rows,list):
                    for row in rows:
                        if isinstance(row,dict) and target in json.dumps(row,ensure_ascii=False,sort_keys=True): phits.append({'collection':cname,'row':row})
        rec['pageajax']={'url':purl,'ok':pres['ok'],'status':pres['status'],'gzip':pres['gzip'],'wire_bytes':len(pres['wire']),'decoded_bytes':len(pres['decoded']),'wire_sha256':hashlib.sha256(pres['wire']).hexdigest() if pres['wire'] else None,'decoded_sha256':hashlib.sha256(pres['decoded']).hexdigest() if pres['decoded'] else None,'wire_file':wf,'decoded_file':df,'json_error':perr,'hits':phits}
        if phits:
            rec['resolved']=True; rec['resolved_source']='F10_PAGEAJAX_GZIP_AWARE'; rec['resolved_rows']=phits
        # Probe multiple field filters. Keep every raw response for audit.
        filters=[
            f"(SECURITY_CODE='{code}')",
            f'(SECURITY_CODE="{code}")',
            f"(SECUCODE='{code}.{ex}')",
            f'(SECUCODE="{code}.{ex}")',
        ]
        for i,flt in enumerate(filters):
            url=report_url(symbol,flt); rr=get(url,'https://data.eastmoney.com/yjfp/'); obj,err=parse_json(rr); wf,df=save_payload(symbol,f'report_{i}',rr)
            rows=rows_from_report(obj); hits=date_hits(rows,target)
            meta={'filter':flt,'url':url,'ok':rr['ok'],'status':rr['status'],'gzip':rr['gzip'],'wire_bytes':len(rr['wire']),'decoded_bytes':len(rr['decoded']),'wire_sha256':hashlib.sha256(rr['wire']).hexdigest() if rr['wire'] else None,'decoded_sha256':hashlib.sha256(rr['decoded']).hexdigest() if rr['decoded'] else None,'wire_file':wf,'decoded_file':df,'json_error':err,'api_success':obj.get('success') if isinstance(obj,dict) else None,'api_code':obj.get('code') if isinstance(obj,dict) else None,'api_message':obj.get('message') if isinstance(obj,dict) else None,'row_n':len(rows),'target_hits':hits}
            rec['report_attempts'].append(meta)
            if hits and not rec['resolved']:
                rec['resolved']=True; rec['resolved_source']='DATACENTER_RPT_SHAREBONUS_DET_PER_SECURITY'; rec['resolved_rows']=hits
            time.sleep(0.15)
        records.append(rec)
        print(json.dumps({'symbol':symbol,'target':target,'resolved':rec['resolved'],'source':rec['resolved_source'],'pageajax_gzip':rec['pageajax']['gzip'],'report_rows':[x['row_n'] for x in rec['report_attempts']]},ensure_ascii=False),flush=True)
    resolved=sum(r['resolved'] for r in records)
    report={'artifact':'F10_UNRESOLVED_HISTORY_PROBE_V481','version':'V4.81','target_n':7,'resolved_n':resolved,'unresolved_n':7-resolved,'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,'records':records}
    (OUT/'F10_UNRESOLVED_HISTORY_PROBE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target_n':7,'resolved_n':resolved,'unresolved_n':7-resolved},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
