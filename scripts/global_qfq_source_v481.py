from __future__ import annotations
import hashlib, json, re

FORMAL_END='2026-04-17'


def sina_symbol(symbol: str) -> str:
    s=str(symbol).strip().upper()
    if len(s)!=9 or s[6] != '.':
        raise ValueError(f'invalid symbol: {symbol}')
    code, exch=s.split('.')
    if len(code)!=6 or not code.isdigit() or exch not in {'SZ','SH'}:
        raise ValueError(f'invalid symbol: {symbol}')
    return exch.lower()+code


def shard_symbols(symbols, shard_index: int, shard_count: int):
    if shard_count <= 0 or not 0 <= shard_index < shard_count:
        raise ValueError('invalid shard')
    return [s for i,s in enumerate(symbols) if i % shard_count == shard_index]


def parse_sina_qfq_js(raw: bytes):
    try:
        text=raw.decode('utf-8-sig', errors='strict').strip()
    except UnicodeDecodeError as e:
        raise ValueError(f'non-utf8 Sina qfq.js: {e}') from e
    if 'KKE_ShareHFq' not in text or 'data' not in text:
        raise ValueError('not a Sina KKE_ShareHFq payload')
    m=re.search(r'data\s*:\s*(\[.*?\])\s*[,}]', text, flags=re.S)
    if not m:
        raise ValueError('missing data[] in Sina qfq.js')
    try:
        data=json.loads(m.group(1))
    except Exception as e:
        raise ValueError(f'invalid Sina data[] JSON: {e}') from e
    if not isinstance(data,list):
        raise ValueError('Sina data is not a list')
    out=[]
    for i,row in enumerate(data):
        if isinstance(row,dict):
            d=row.get('d', row.get('date'))
            f=row.get('f', row.get('factor', row.get('qfq_factor')))
        elif isinstance(row,(list,tuple)) and len(row)>=2:
            d,f=row[0],row[1]
        else:
            raise ValueError(f'invalid Sina factor row #{i}')
        date=str(d or '')[:10]
        try:
            factor=float(f)
        except Exception as e:
            raise ValueError(f'invalid factor row #{i}') from e
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) or not factor>0:
            raise ValueError(f'invalid factor row #{i}')
        out.append({'date':date,'factor':factor})
    out.sort(key=lambda x:x['date'], reverse=True)
    dates=[x['date'] for x in out]
    if len(dates)!=len(set(dates)):
        raise ValueError('duplicate factor dates')
    return out


def classify_source(symbol, http_status, content_type, raw, rows, formal_end=FORMAL_END):
    base={
        'symbol':symbol,
        'http_status':int(http_status) if http_status is not None else None,
        'content_type':content_type,
        'bytes':len(raw or b''),
        'sha256':hashlib.sha256(raw or b'').hexdigest(),
        'factor_rows':len(rows or []),
        'first_factor_date':min((r['date'] for r in (rows or [])), default=None),
        'last_factor_date':max((r['date'] for r in (rows or [])), default=None),
        'anchor_divisor':None,
        'formal_promotion':False,
    }
    if int(http_status or 0) != 200:
        return {**base,'status':'FAILED_HTTP'}
    if not raw:
        return {**base,'status':'FAILED_EMPTY_BODY'}
    if not rows:
        return {**base,'status':'UNKNOWN_ZERO_ACTION_OR_SOURCE_EMPTY'}
    eligible=[r for r in rows if r['date'] <= formal_end]
    if not eligible:
        return {**base,'status':'UNKNOWN_NO_ANCHOR_DIVISOR_BY_FORMAL_END'}
    anchor=max(eligible,key=lambda r:r['date'])['factor']
    return {**base,'status':'SINA_FACTOR_PATH_SOURCE_READY','anchor_divisor':anchor,'factor_rows_le_formal_end':len(eligible)}
