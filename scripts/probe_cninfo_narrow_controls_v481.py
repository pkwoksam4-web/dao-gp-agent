from __future__ import annotations

import json
import pathlib

from cninfo_narrow_supplement_v481 import collect_symbol

CONTROLS={
    '000338.SZ':['2024-10-18'],
    '000333.SZ':['2025-06-12'],
    '001979.SZ':['2024-07-23'],
    '000631.SZ':['2023-05-17'],
}


def main():
    out=pathlib.Path('artifact_cninfo_narrow_controls_v481'); raw=out/'raw'; raw.mkdir(parents=True,exist_ok=True)
    rows=[]
    for symbol,dates in CONTROLS.items():
        rows.extend(collect_symbol(symbol,dates,raw,timeout=15,attempts=4,sleep_between=0.0))
    report={
        'artifact':'CNINFO_NARROW_CONTROL_PROBE_V481','version':'V4.81',
        'control_n':len(rows),'matched_n':sum(r.get('match') is not None for r in rows),
        'error_n':sum(r.get('error') is not None for r in rows),'records':rows,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
    }
    (out/'CNINFO_NARROW_CONTROL_PROBE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('control_n','matched_n','error_n')},ensure_ascii=False,indent=2))
    for r in rows:
        print(json.dumps({'symbol':r['symbol'],'ex_date':r['ex_date'],'match_title':(r.get('match') or {}).get('announcementTitle'),'error':r.get('error')},ensure_ascii=False))

if __name__=='__main__':
    main()
