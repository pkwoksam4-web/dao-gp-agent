from __future__ import annotations

import hashlib
import json
import pathlib

from cninfo_exact_term_v481 import query_window, query_cninfo, choose_implementation_announcement, announcement_pdf_url

OUT=pathlib.Path('artifact_cninfo_exact_term_controls_v481')
RAW=OUT/'raw'
RAW.mkdir(parents=True,exist_ok=True)

CONTROLS=[
    {'symbol':'000631.SZ','event_date':'2023-05-17','notice_date':'2023-05-09'},
    {'symbol':'000651.SZ','event_date':'2021-08-23','notice_date':'2021-08-14'},
    {'symbol':'001299.SZ','event_date':'2025-04-29','notice_date':'2025-04-22'},
    {'symbol':'001202.SZ','event_date':'2025-06-18','notice_date':'2025-06-11'},
]


def main():
    rows=[]
    for c in CONTROLS:
        code=c['symbol'].split('.')[0]
        start,end=query_window(c['notice_date'],14)
        try:
            res=query_cninfo(code,start,end)
            raw=res['raw']
            fn=f'{code}_{start}_{end}_cninfo_query.json'
            (RAW/fn).write_bytes(raw)
            obj=res['json']
            items=obj.get('announcements') or []
            picked=choose_implementation_announcement(items,c['notice_date'])
            row={**c,'http_status':res['http_status'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                 'raw_file':fn,'announcement_n':len(items),'picked':picked,
                 'pdf_url':announcement_pdf_url(picked) if picked else None,'error':None}
        except Exception as e:
            row={**c,'http_status':None,'bytes':0,'sha256':None,'raw_file':None,'announcement_n':0,
                 'picked':None,'pdf_url':None,'error':f'{type(e).__name__}: {e}'}
        rows.append(row)
        print(json.dumps({'symbol':row['symbol'],'http':row['http_status'],'n':row['announcement_n'],
                          'picked':(row['picked'] or {}).get('announcementTitle'),'error':row['error']},ensure_ascii=False),flush=True)
    picked_n=sum(r['picked'] is not None for r in rows)
    report={'artifact':'CNINFO_EXACT_TERM_CONTROL_PROBE_V481','version':'V4.81','control_n':len(rows),
            'picked_n':picked_n,'records':rows,'formal_promotion':False,
            'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False}
    (OUT/'CNINFO_EXACT_TERM_CONTROL_PROBE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'control_n':len(rows),'picked_n':picked_n},ensure_ascii=False))

if __name__=='__main__':
    main()
