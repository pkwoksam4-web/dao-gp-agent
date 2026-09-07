from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from recalc_global_qfq_from_ledger_v481_fixed import (
    classify_result,
    rows_by_security_code,
    sina_factor_change_dates,
)
from sample50_probe import eastmoney_kline_url, sohu_history_url
from sample50_validate import (
    compare_factor_path,
    event_ratio,
    expected_factor_for_date,
    merge_actions,
    normalize_rights_rows,
    normalize_sharebonus_rows,
    parse_sina_qfq,
    parse_sohu_history_bytes,
    prev_close_before,
    sina_normalized_for_date,
)

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
THRESHOLD_BP=5.0
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36'
TARGETS=('000069.SZ','001379.SZ')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_eastmoney_raw_kline(raw: bytes) -> list[dict]:
    try:
        obj=json.loads(raw.decode('utf-8'))
    except Exception as e:
        raise ValueError(f'EastMoney RAW JSON decode failed: {e}') from e
    data=obj.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('klines'),list) or not data['klines']:
        raise ValueError('EastMoney RAW missing data.klines')
    rows=[]
    for item in data['klines']:
        parts=str(item).split(',')
        if len(parts)<5:
            raise ValueError(f'EastMoney RAW malformed kline: {item!r}')
        d=parts[0]
        try:
            o=float(parts[1]); c=float(parts[2]); h=float(parts[3]); l=float(parts[4])
        except Exception as e:
            raise ValueError(f'EastMoney RAW invalid OHLC {d}: {e}') from e
        if min(o,c,h,l)<=0 or l>min(o,c,h) or h<max(o,c,l):
            raise ValueError(f'EastMoney RAW invalid OHLC geometry {d}')
        rows.append({'date':d,'open':o,'close':c,'high':h,'low':l})
    rows.sort(key=lambda r:r['date'])
    if len({r['date'] for r in rows})!=len(rows):
        raise ValueError('EastMoney RAW duplicate dates')
    return rows


def choose_raw_provider(*, sohu_ok: bool, eastmoney_ok: bool) -> str:
    if sohu_ok:
        return 'SOHU_RAW'
    if eastmoney_ok:
        return 'EASTMONEY_FQT0_FALLBACK'
    return 'BLOCKED_NO_RAW_PROVIDER'


def fetch_bytes(url: str, referer: str, attempts: int=3) -> tuple[bytes,dict]:
    last={'ok':False,'status':None,'content_type':None,'bytes':0,'sha256':sha256(b''),'attempts':0,'error':None,'url':url}
    for attempt in range(1,attempts+1):
        try:
            req=Request(url,headers={'User-Agent':UA,'Accept':'*/*','Referer':referer})
            with urlopen(req,timeout=30) as r:
                body=r.read()
                return body,{
                    'ok':True,'status':getattr(r,'status',200),'content_type':r.headers.get('Content-Type'),
                    'bytes':len(body),'sha256':sha256(body),'attempts':attempt,'error':None,'url':url,
                }
        except HTTPError as e:
            try: body=e.read()
            except Exception: body=b''
            last={
                'ok':False,'status':e.code,'content_type':e.headers.get('Content-Type') if e.headers else None,
                'bytes':len(body),'sha256':sha256(body),'attempts':attempt,'error':f'HTTPError: {e}','url':url,
            }
        except Exception as e:
            last={
                'ok':False,'status':None,'content_type':None,'bytes':0,'sha256':sha256(b''),'attempts':attempt,
                'error':f'{type(e).__name__}: {e}','url':url,
            }
        if attempt<attempts:
            time.sleep(0.8*attempt)
    return b'',last


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows=[]
    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.strip(): rows.append(json.loads(line))
    return rows


def find_unique(root: pathlib.Path, basename: str) -> pathlib.Path:
    hits=[p for p in root.rglob(basename) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected one {basename}, found={len(hits)}')
    return hits[0]


def repair_one(symbol: str, source_census: pathlib.Path, ledger_dir: pathlib.Path, out: pathlib.Path,
               share_by_code: dict[str,list[dict]], rights_by_code: dict[str,list[dict]]) -> dict:
    code,exch=symbol.split('.')
    prefix=f'{code}_{exch}'
    raw_dir=out/'raw'; raw_dir.mkdir(parents=True,exist_ok=True)
    rec={
        'symbol':symbol,'status':None,'raw_provider':None,'formal_rows':0,'event_count':0,
        'ledger_event_dates':[],'sina_event_dates':[],'factor_validation':None,'events':[],
        'source_meta':{},'formal_promotion':False,'validated_global_provenance_emitted':False,'error':None,
    }

    try:
        sina_path=find_unique(source_census,prefix+'_sina_qfq.js')
        sina_raw=sina_path.read_bytes(); factors=parse_sina_qfq(sina_raw)
        rec['source_meta']['sina']={'path':str(sina_path),'bytes':len(sina_raw),'sha256':sha256(sina_raw),
                                    'source_run':34009079533}
    except Exception as e:
        rec['status']='BLOCKED_SINA_SOURCE'; rec['error']=f'{type(e).__name__}: {e}'; return rec

    sohu_raw,sohu_meta=fetch_bytes(sohu_history_url(symbol),'https://q.stock.sohu.com/')
    sohu_name=prefix+'_sohu_repair.js'; (raw_dir/sohu_name).write_bytes(sohu_raw)
    sohu_meta['raw_file']='raw/'+sohu_name
    sohu_rows=None
    if sohu_meta['ok'] and sohu_raw:
        try: sohu_rows=parse_sohu_history_bytes(sohu_raw)
        except Exception as e: sohu_meta['parse_error']=f'{type(e).__name__}: {e}'
    rec['source_meta']['sohu_repair']=sohu_meta

    em_raw,em_meta=fetch_bytes(eastmoney_kline_url(symbol),'https://quote.eastmoney.com/')
    em_name=prefix+'_eastmoney_fqt0_repair.json'; (raw_dir/em_name).write_bytes(em_raw)
    em_meta['raw_file']='raw/'+em_name
    em_rows=None
    if em_meta['ok'] and em_raw:
        try: em_rows=parse_eastmoney_raw_kline(em_raw)
        except Exception as e: em_meta['parse_error']=f'{type(e).__name__}: {e}'
    rec['source_meta']['eastmoney_fqt0_repair']=em_meta

    provider=choose_raw_provider(sohu_ok=sohu_rows is not None,eastmoney_ok=em_rows is not None)
    rec['raw_provider']=provider
    if provider=='BLOCKED_NO_RAW_PROVIDER':
        rec['status']='BLOCKED_NO_RAW_PROVIDER'; rec['error']='Neither Sohu nor EastMoney fqt=0 produced valid RAW rows'; return rec
    raw_rows=sohu_rows if provider=='SOHU_RAW' else em_rows
    if len({r['date'] for r in raw_rows})!=len(raw_rows):
        rec['status']='BLOCKED_RAW_DUPLICATE_DATES'; rec['error']='duplicate dates after provider selection'; return rec

    formal_rows=[r for r in raw_rows if FORMAL_BEG<=r['date']<=FORMAL_END]
    rec['formal_rows']=len(formal_rows)
    if not formal_rows:
        rec['status']='NOT_APPLICABLE_NO_FORMAL_ROWS'; return rec

    try:
        actions=merge_actions(normalize_sharebonus_rows(symbol,share_by_code.get(code,[]))+
                              normalize_rights_rows(symbol,rights_by_code.get(code,[])))
        actions=[a for a in actions if FORMAL_BEG<a.ex_date<=FORMAL_END]
    except Exception as e:
        rec['status']='REVIEW_REPAIR_EVENT_PARSE'; rec['error']=f'{type(e).__name__}: {e}'; return rec

    ledger_dates=sorted({a.ex_date for a in actions})
    sina_dates=sina_factor_change_dates(factors,FORMAL_BEG,FORMAL_END)
    rec['event_count']=len(actions); rec['ledger_event_dates']=ledger_dates; rec['sina_event_dates']=sina_dates
    rec['missing_in_sina']=sorted(set(ledger_dates)-set(sina_dates))
    rec['missing_in_ledger']=sorted(set(sina_dates)-set(ledger_dates))

    try:
        ratios={}
        for a in actions:
            pc=prev_close_before(raw_rows,a.ex_date); ratio=event_ratio(a,pc); ratios[a.ex_date]=ratio
            rec['events'].append({'ex_date':a.ex_date,'prev_actual_close':pc,'event_ratio':ratio,
                                  'cash_per_share_nominal':a.cash_per_share,'stock_ratio':a.stock_ratio,
                                  'capitalization_ratio':a.cap_ratio,'rights_ratio':a.rights_ratio,
                                  'rights_price':a.rights_price,'source':a.source})
        expected={r['date']:expected_factor_for_date(r['date'],actions,ratios,FORMAL_END) for r in formal_rows}
        actual={r['date']:sina_normalized_for_date(factors,r['date'],FORMAL_END) for r in formal_rows}
        cmp=compare_factor_path(formal_rows,expected,actual,THRESHOLD_BP)
        rec['factor_validation']=cmp
    except Exception as e:
        rec['status']='REVIEW_REPAIR_FACTOR_COMPARISON'; rec['error']=f'{type(e).__name__}: {e}'; return rec

    rec['status']=classify_result(len(formal_rows),len(actions),cmp['status'],ledger_dates,sina_dates)
    return rec


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-census',required=True)
    p.add_argument('--ledger-dir',required=True)
    p.add_argument('--out-dir',required=True)
    args=p.parse_args()
    source=pathlib.Path(args.source_census); ledger=pathlib.Path(args.ledger_dir); out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    share=load_jsonl(ledger/'RPT_SHAREBONUS_DET_FORMAL_LEDGER_V481.jsonl')
    rights=load_jsonl(ledger/'RPT_IPO_ALLOTMENT_FORMAL_LEDGER_V481.jsonl')
    share_by=rows_by_security_code(share); rights_by=rows_by_security_code(rights)
    records=[repair_one(s,source,ledger,out,share_by,rights_by) for s in TARGETS]
    doc={
        'artifact':'QFQ_RAW_BLOCKER_REPAIR_V481','version':'V4.81',
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'targets':list(TARGETS),'records':records,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
        'rule':'Sohu RAW is primary. EastMoney fqt=0 is an explicit fallback only when Sohu is unavailable/invalid. Provider provenance and raw bytes are retained.',
    }
    (out/'QFQ_RAW_BLOCKER_REPAIR_V481.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(doc,ensure_ascii=False,indent=2))
    if any(r['status'].startswith('BLOCKED') or r['status'].startswith('REVIEW_REPAIR') for r in records):
        raise SystemExit(3)


if __name__=='__main__': main()
