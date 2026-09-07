from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
import urllib.request

ENDPOINT='https://www.cninfo.com.cn/new/hisAnnouncement/query'


def query_window(notice_date: str, days: int=10) -> tuple[str,str]:
    d=dt.date.fromisoformat(str(notice_date)[:10])
    return ((d-dt.timedelta(days=days)).isoformat(), (d+dt.timedelta(days=days)).isoformat())


def _clean_title(s: str) -> str:
    return re.sub(r'<[^>]+>','',str(s or '')).replace(' ','')


def choose_implementation_announcement(items: list[dict], notice_date: str) -> dict | None:
    target=dt.date.fromisoformat(str(notice_date)[:10])
    candidates=[]
    for x in items or []:
        title=_clean_title(x.get('announcementTitle'))
        if '权益分派实施公告' not in title and '权益分配实施公告' not in title:
            continue
        ms=x.get('announcementTime')
        try:
            d=dt.datetime.fromtimestamp(float(ms)/1000, tz=dt.timezone.utc).date()
        except Exception:
            d=target
        candidates.append((abs((d-target).days), d, x))
    if not candidates:
        return None
    candidates.sort(key=lambda t:(t[0],t[1]))
    return candidates[0][2]


def query_cninfo(code: str, start_date: str, end_date: str) -> dict:
    payload={
        'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext',
        'plate':'','stock':str(code),'searchkey':'权益分派实施公告','secid':'',
        'category':'','trade':'','seDate':f'{start_date}~{end_date}',
        'sortName':'','sortType':'','isHLtitle':'true',
    }
    body=urllib.parse.urlencode(payload).encode('utf-8')
    req=urllib.request.Request(ENDPOINT,data=body,headers={
        'User-Agent':'Mozilla/5.0','Accept':'application/json, text/plain, */*',
        'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer':'https://www.cninfo.com.cn/new/fulltextSearch',
        'Origin':'https://www.cninfo.com.cn',
    })
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read()
        status=getattr(r,'status',None)
        ct=r.headers.get('Content-Type')
    obj=json.loads(raw.decode('utf-8'))
    return {'http_status':status,'content_type':ct,'raw':raw,'json':obj}


def announcement_pdf_url(item: dict) -> str:
    path=str(item.get('adjunctUrl') or '').lstrip('/')
    if not path:
        raise ValueError('announcement missing adjunctUrl')
    return 'https://static.cninfo.com.cn/'+path
