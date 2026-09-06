from __future__ import annotations

import hashlib
import json
import pathlib
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = pathlib.Path('artifact_global_event_ledger_probe')
OUT.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36'
BASE = 'https://datacenter-web.eastmoney.com/api/data/v1/get'


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def url_for(report: str, page: int = 1) -> str:
    params = {
        'reportName': report,
        'columns': 'ALL',
        'pageNumber': page,
        'pageSize': 500,
        'source': 'WEB',
        'client': 'WEB',
        'sortTypes': -1,
    }
    if report == 'RPT_IPO_ALLOTMENT':
        params['sortColumns'] = 'EQUITY_RECORD_DATE'
        params['quoteColumns'] = 'f2~01~SECURITY_CODE~NEW_PRICE'
    else:
        params['sortColumns'] = 'EX_DIVIDEND_DATE'
    return BASE + '?' + urlencode(params)


def probe(report: str) -> dict:
    url = url_for(report, 1)
    req = Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Referer': 'https://data.eastmoney.com/'})
    with urlopen(req, timeout=35) as r:
        body = r.read()
        status = getattr(r, 'status', 200)
        ctype = r.headers.get('Content-Type')
    raw_name = report + '_page1.json'
    (OUT / raw_name).write_bytes(body)
    obj = json.loads(body.decode('utf-8'))
    result = obj.get('result') or {}
    data = result.get('data') or []
    first = data[0] if data else {}
    dates = []
    for row in data:
        for key in ('EX_DIVIDEND_DATE', 'EQUITY_RECORD_DATE', 'NOTICE_DATE', 'PLAN_NOTICE_DATE'):
            v = row.get(key)
            if v:
                dates.append(str(v)[:10])
                break
    return {
        'report': report,
        'url': url,
        'http_status': status,
        'content_type': ctype,
        'bytes': len(body),
        'sha256': sha256(body),
        'success': obj.get('success'),
        'code': obj.get('code'),
        'message': obj.get('message'),
        'pages': result.get('pages'),
        'count': result.get('count'),
        'page_data_n': len(data),
        'page_date_min': min(dates) if dates else None,
        'page_date_max': max(dates) if dates else None,
        'sample_keys': sorted(first.keys()) if isinstance(first, dict) else [],
        'sample_security_code': first.get('SECURITY_CODE') if isinstance(first, dict) else None,
        'sample_ex_dividend_date': first.get('EX_DIVIDEND_DATE') if isinstance(first, dict) else None,
        'sample_equity_record_date': first.get('EQUITY_RECORD_DATE') if isinstance(first, dict) else None,
        'raw_file': raw_name,
    }


def main() -> None:
    rows = []
    for report in ('RPT_IPO_ALLOTMENT', 'RPT_SHAREBONUS_DET'):
        try:
            rows.append(probe(report))
        except Exception as e:
            rows.append({'report': report, 'error': f'{type(e).__name__}: {e}'})
    doc = {
        'artifact': 'GLOBAL_EVENT_LEDGER_PROBE_V481',
        'version': 'V4.81',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'purpose': 'Feasibility only. No Formal promotion and no review-status mutation.',
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'results': rows,
    }
    (OUT / 'GLOBAL_EVENT_LEDGER_PROBE_V481.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    if any(r.get('error') for r in rows):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
