from __future__ import annotations

import hashlib
import json
import pathlib
import re
import urllib.request

OUT = pathlib.Path('artifact_bonusfinancing_js_probe_v481')
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    'https://emweb.securities.eastmoney.com/PC_HSF10/Content/js/new/BonusFinancing.js?v=1.0.2.7054',
    'https://emweb.securities.eastmoney.com/Content/js/new/BonusFinancing.js?v=1.0.2.7054',
    'https://emweb.securities.eastmoney.com/PC_HSF10/Content/js/new/BonusFinancing.js',
    'https://emweb.securities.eastmoney.com/Content/js/new/BonusFinancing.js',
]


def fetch(url: str):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://emweb.securities.eastmoney.com/PC_HSF10/BonusFinancing/Index?code=SH601989&type=web',
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read()
            return {
                'url': url,
                'ok': True,
                'status': getattr(r, 'status', None),
                'content_type': r.headers.get('Content-Type'),
                'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(),
                'raw': raw,
                'error': None,
            }
    except Exception as e:
        return {'url': url, 'ok': False, 'status': None, 'content_type': None, 'bytes': 0, 'sha256': None, 'raw': b'', 'error': f'{type(e).__name__}: {e}'}


def interesting_lines(text: str):
    pats = ('ajax', 'url', 'api', 'bonus', 'dividend', 'report', 'filter', 'Get', 'POST', 'BonusDetails')
    out=[]
    for i,line in enumerate(text.splitlines(),1):
        if any(p.lower() in line.lower() for p in pats):
            out.append({'line': i, 'text': line[:1000]})
    return out[:500]


def main():
    rows=[]
    for idx,url in enumerate(CANDIDATES):
        rec=fetch(url)
        raw=rec.pop('raw')
        if raw:
            p=OUT/f'candidate_{idx}.js'
            p.write_bytes(raw)
            rec['raw_file']=p.name
            text=raw.decode('utf-8', errors='replace')
            rec['interesting_lines']=interesting_lines(text)
            rec['urls']=sorted(set(re.findall(r'https?://[^\"\'\s)]+', text)))[:200]
            rec['quoted_paths']=sorted(set(re.findall(r'[\"\']([^\"\']*(?:Bonus|bonus|Dividend|dividend|ajax|Ajax|api|API)[^\"\']*)[\"\']', text)))[:300]
        rows.append(rec)
    report={
        'artifact':'BONUSFINANCING_JS_PROBE_V481',
        'version':'V4.81',
        'formal_promotion':False,
        'validated_global_provenance_emitted':False,
        'formal_ready':False,
        'oos_metrics_allowed':False,
        'candidates':rows,
    }
    (OUT/'BONUSFINANCING_JS_PROBE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
