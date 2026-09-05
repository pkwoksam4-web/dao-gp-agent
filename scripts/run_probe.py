from __future__ import annotations
import hashlib, json, os, pathlib, time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from sample50_probe import sina_symbol, report_url, eastmoney_kline_url, sohu_history_url

OUT = pathlib.Path(os.environ.get('PROBE_OUT','artifact'))
OUT.mkdir(parents=True, exist_ok=True)
SYMBOL = os.environ.get('PROBE_SYMBOL','300592.SZ')
UA='Mozilla/5.0'


def fetch(name: str, url: str, referer: str | None = None):
    p = OUT / name
    meta = {'name': name, 'url': url, 'ok': False, 'status': None, 'content_type': None, 'error': None, 'bytes': 0, 'sha256': None}
    headers={'User-Agent':UA, 'Accept':'*/*'}
    if referer: headers['Referer']=referer
    try:
        req=Request(url, headers=headers)
        with urlopen(req, timeout=25) as r:
            body=r.read()
            meta['status']=getattr(r,'status',200)
            meta['content_type']=r.headers.get('Content-Type')
        p.write_bytes(body)
        meta['ok']=True
    except HTTPError as e:
        meta['status']=e.code
        try: body=e.read()
        except Exception: body=b''
        p.write_bytes(body)
        meta['content_type']=e.headers.get('Content-Type') if e.headers else None
        meta['error']=f'HTTPError: {e}'
    except Exception as e:
        p.write_bytes(b'')
        meta['error']=f'{type(e).__name__}: {e}'
    body=p.read_bytes()
    meta['bytes']=len(body)
    meta['sha256']=hashlib.sha256(body).hexdigest()
    return meta

sources=[
    ('eastmoney_sharebonus.json', report_url(SYMBOL,'RPT_SHAREBONUS_DET'), 'https://data.eastmoney.com/'),
    ('eastmoney_rights.json', report_url(SYMBOL,'RPT_IPO_ALLOTMENT'), 'https://data.eastmoney.com/'),
    ('eastmoney_raw_kline.json', eastmoney_kline_url(SYMBOL), 'https://quote.eastmoney.com/'),
    ('sohu_raw_history.js', sohu_history_url(SYMBOL), 'https://q.stock.sohu.com/'),
    ('eastmoney_rights_control_600030.json', report_url('600030.SH','RPT_IPO_ALLOTMENT'), 'https://data.eastmoney.com/'),
    ('sina_qfq.js', f'https://finance.sina.com.cn/realstock/company/{sina_symbol(SYMBOL)}/qfq.js', 'https://finance.sina.com.cn/'),
]
manifest={'symbol':SYMBOL,'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),'sources':[]}
for name,url,ref in sources:
    manifest['sources'].append(fetch(name,url,ref))
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
