from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request

ENDPOINT='https://www.cninfo.com.cn/new/hisAnnouncement/query'
TOPSEARCH='https://www.cninfo.com.cn/new/information/topSearch/detailOfQuery'


def query_window(notice_date: str, days: int=10) -> tuple[str,str]:
    d=dt.date.fromisoformat(str(notice_date)[:10])
    return ((d-dt.timedelta(days=days)).isoformat(), (d+dt.timedelta(days=days)).isoformat())


def event_query_window(event_date: str, prior_days: int=45, forward_days: int=2) -> tuple[str,str]:
    d=dt.date.fromisoformat(str(event_date)[:10])
    return ((d-dt.timedelta(days=prior_days)).isoformat(), (d+dt.timedelta(days=forward_days)).isoformat())


def _clean_title(s: str) -> str:
    return re.sub(r'<[^>]+>','',str(s or '')).replace(' ','')


def is_distribution_implementation_title(s: str) -> bool:
    title=_clean_title(s)
    if '实施后' in title or '实施分派后' in title or '实施权益分派后' in title:
        return False
    if '预案' in title:
        return False
    families=('权益分派','权益分配','分红派息','利润分配')
    if not any(x in title for x in families):
        return False
    return '实施公告' in title or '方案实施公告' in title


def choose_implementation_announcement(items: list[dict], notice_date: str) -> dict | None:
    target=dt.date.fromisoformat(str(notice_date)[:10])
    candidates=[]
    for x in items or []:
        if not is_distribution_implementation_title(x.get('announcementTitle')):
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


def choose_orgid_record(records: list[dict], code: str) -> dict:
    code=str(code).strip()
    matches=[r for r in (records or []) if str(r.get('code') or '').strip()==code and str(r.get('orgId') or '').strip()]
    if len(matches)!=1:
        raise ValueError(f'expected exactly one CNINFO orgId record for {code}; found={len(matches)}')
    return matches[0]


def stock_query_param(code: str, orgid: str) -> str:
    code=str(code).strip(); orgid=str(orgid).strip()
    if not re.fullmatch(r'\d{6}',code) or not orgid:
        raise ValueError('invalid CNINFO code/orgId')
    return f'{code},{orgid}'


def column_for_code(code: str) -> str:
    code=str(code).strip()
    if not re.fullmatch(r'\d{6}',code):
        raise ValueError(f'invalid stock code: {code!r}')
    return 'sse' if code[0] in {'5','6','9'} else 'szse'


def _post(url: str, payload: dict, timeout: int=20, attempts: int=3) -> dict:
    body=urllib.parse.urlencode(payload).encode('utf-8')
    headers={
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36',
        'Accept':'application/json, text/plain, */*',
        'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer':'https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
        'Origin':'https://www.cninfo.com.cn',
        'X-Requested-With':'XMLHttpRequest',
        'Connection':'close',
    }
    last=None
    for attempt in range(1,attempts+1):
        req=urllib.request.Request(url,data=body,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                raw=r.read(); status=getattr(r,'status',None); ct=r.headers.get('Content-Type')
            return {'http_status':status,'content_type':ct,'raw':raw,'json':json.loads(raw.decode('utf-8')),'attempts':attempt}
        except Exception as e:
            last=e
            if attempt<attempts:
                time.sleep(0.75*attempt)
    raise last


def resolve_orgid(code: str) -> dict:
    res=_post(TOPSEARCH,{'keyWord':str(code),'maxSecNum':'10','maxListNum':'5'})
    obj=res['json']
    records=[]
    if isinstance(obj,list):
        records=obj
    elif isinstance(obj,dict):
        records=obj.get('keyBoardList') or obj.get('keyBoard') or obj.get('data') or []
    rec=choose_orgid_record(records,code)
    return {**res,'record':rec,'orgid':rec['orgId']}


def query_cninfo(code: str, start_date: str, end_date: str, orgid: str | None=None,
                 searchkey: str='权益分派实施公告', timeout: int=20, attempts: int=3) -> dict:
    org_meta=None
    if not orgid:
        org_meta=resolve_orgid(code)
        orgid=org_meta['orgid']
    payload={
        'pageNum':'1','pageSize':'30','column':column_for_code(code),'tabName':'fulltext',
        'plate':'','stock':stock_query_param(code,orgid),'searchkey':str(searchkey),'secid':'',
        'category':'','trade':'','seDate':f'{start_date}~{end_date}',
        'sortName':'','sortType':'','isHLtitle':'true',
    }
    res=_post(ENDPOINT,payload,timeout=timeout,attempts=attempts)
    res['orgid']=orgid
    res['org_lookup']=org_meta
    res['column']=payload['column']
    res['searchkey']=payload['searchkey']
    res['date_window']=[start_date,end_date]
    return res


def announcement_pdf_url(item: dict) -> str:
    path=str(item.get('adjunctUrl') or '').lstrip('/')
    if not path:
        raise ValueError('announcement missing adjunctUrl')
    return 'https://static.cninfo.com.cn/'+path
