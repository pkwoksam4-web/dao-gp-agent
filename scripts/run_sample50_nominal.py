from __future__ import annotations
import csv, hashlib, json, os, pathlib, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from sample50_probe import report_url, sohu_history_url, sina_symbol
from sample50_validate import (
    parse_eastmoney_report, normalize_sharebonus_rows, normalize_rights_rows,
    merge_actions, parse_sohu_history_bytes, prev_close_before, parse_sina_qfq,
    event_ratio, expected_factor_for_date, sina_normalized_for_date,
    compare_factor_path,
)

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
THRESHOLD_BP=5.0
UA='Mozilla/5.0'
OUT=pathlib.Path(os.environ.get('SAMPLE50_OUT','artifact_sample50'))
RAW=OUT/'raw'
RAW.mkdir(parents=True,exist_ok=True)

SAMPLE50=[
'600737.SH','002646.SZ','300465.SZ','002003.SZ','688200.SH','688125.SH','601162.SH','605068.SH','300152.SZ','002236.SZ',
'300827.SZ','600232.SH','300633.SZ','002318.SZ','600249.SH','300561.SZ','300246.SZ','603323.SH','300687.SZ','600386.SH',
'300775.SZ','002016.SZ','002627.SZ','600629.SH','002938.SZ','603583.SH','603901.SH','002662.SZ','600594.SH','300434.SZ',
'601225.SH','600592.SH','603170.SH','002001.SZ','300565.SZ','002693.SZ','600131.SH','300864.SZ','603123.SH','002230.SZ',
'002069.SZ','688277.SH','301327.SZ','002158.SZ','688455.SH','002658.SZ','601890.SH','605365.SH','600641.SH','600377.SH']


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_bytes(url: str, referer: str, attempts: int=3) -> tuple[bytes,dict]:
    last=None
    for i in range(attempts):
        try:
            req=Request(url,headers={'User-Agent':UA,'Accept':'*/*','Referer':referer})
            with urlopen(req,timeout=35) as r:
                b=r.read(); status=getattr(r,'status',200); ctype=r.headers.get('Content-Type')
            return b,{'ok':True,'status':status,'content_type':ctype,'bytes':len(b),'sha256':sha(b),'attempts':i+1,'error':None}
        except HTTPError as e:
            try: b=e.read()
            except Exception: b=b''
            last=f'HTTPError {e.code}: {e}'
            if 400 <= e.code < 500 and e.code != 429:
                return b,{'ok':False,'status':e.code,'content_type':e.headers.get('Content-Type') if e.headers else None,'bytes':len(b),'sha256':sha(b),'attempts':i+1,'error':last}
        except Exception as e:
            last=f'{type(e).__name__}: {e}'
        if i+1<attempts: time.sleep(0.7*(i+1))
    return b'',{'ok':False,'status':None,'content_type':None,'bytes':0,'sha256':sha(b''),'attempts':attempts,'error':last}


def fetch_report(symbol: str, report: str, d: pathlib.Path) -> tuple[list[dict],list[dict]]:
    all_rows=[]; metas=[]; page=1; max_pages=1
    while page <= max_pages:
        u=report_url(symbol,report,page_number=page)
        b,m=fetch_bytes(u,'https://data.eastmoney.com/')
        m.update({'url':u,'report':report,'page':page})
        (d/f'{report}_p{page}.json').write_bytes(b)
        metas.append(m)
        if not m['ok']:
            raise RuntimeError(f'{report} fetch failed: {m["error"]}')
        rows,pages=parse_eastmoney_report(b)
        all_rows.extend(rows)
        max_pages=max(1,pages)
        if max_pages>20: raise RuntimeError(f'{report} unreasonable pages={max_pages}')
        page += 1
        if pages==0: break
    return all_rows,metas


def one(symbol: str) -> dict:
    d=RAW/symbol.replace('.','_'); d.mkdir(parents=True,exist_ok=True)
    res={'symbol':symbol,'status':None,'factor_validation':None,'events':[], 'source_meta':{}, 'error':None}
    try:
        sb,sbm=fetch_report(symbol,'RPT_SHAREBONUS_DET',d)
        rr,rrm=fetch_report(symbol,'RPT_IPO_ALLOTMENT',d)
        res['source_meta']['sharebonus']=sbm; res['source_meta']['rights']=rrm

        sohu_url=sohu_history_url(symbol)
        sohu_b,sohu_m=fetch_bytes(sohu_url,'https://q.stock.sohu.com/')
        sohu_m['url']=sohu_url; (d/'sohu_raw_history.js').write_bytes(sohu_b)
        res['source_meta']['sohu']=sohu_m
        if not sohu_m['ok']: raise RuntimeError(f'Sohu RAW failed: {sohu_m["error"]}')

        sina_url=f'https://finance.sina.com.cn/realstock/company/{sina_symbol(symbol)}/qfq.js'
        sina_b,sina_m=fetch_bytes(sina_url,'https://finance.sina.com.cn/')
        sina_m['url']=sina_url; (d/'sina_qfq.js').write_bytes(sina_b)
        res['source_meta']['sina']=sina_m
        if not sina_m['ok']: raise RuntimeError(f'Sina qfq failed: {sina_m["error"]}')

        raw_rows=parse_sohu_history_bytes(sohu_b)
        if len({r['date'] for r in raw_rows}) != len(raw_rows): raise ValueError('duplicate Sohu dates')
        formal_rows=[r for r in raw_rows if FORMAL_BEG <= r['date'] <= FORMAL_END]
        if not formal_rows: raise ValueError('no Formal Sohu rows')
        factors=parse_sina_qfq(sina_b)

        actions=merge_actions(normalize_sharebonus_rows(symbol,sb)+normalize_rights_rows(symbol,rr))
        actions=[a for a in actions if FORMAL_BEG < a.ex_date <= FORMAL_END]
        ratios={}
        for a in actions:
            p=prev_close_before(raw_rows,a.ex_date)
            ratios[a.ex_date]=event_ratio(a,p)
            res['events'].append({
                'ex_date':a.ex_date,'cash_per_share_nominal':a.cash_per_share,
                'stock_ratio':a.stock_ratio,'capitalization_ratio':a.cap_ratio,
                'rights_ratio':a.rights_ratio,'rights_price':a.rights_price,
                'prev_actual_close':p,'event_ratio':ratios[a.ex_date],'source':a.source})
        expected={r['date']:expected_factor_for_date(r['date'],actions,ratios,FORMAL_END) for r in formal_rows}
        actual={r['date']:sina_normalized_for_date(factors,r['date'],FORMAL_END) for r in formal_rows}
        cmp=compare_factor_path(formal_rows,expected,actual,THRESHOLD_BP)
        res['factor_validation']=cmp
        res['formal_rows']=len(formal_rows); res['sina_factor_rows']=len(factors); res['event_count']=len(actions)
        if cmp['status']=='PASS':
            res['status']='PASS_NOMINAL_EVENT_FACTOR'
        elif actions:
            res['status']='REVIEW_REQUIRED_FACTOR_MISMATCH__REFINE_EXACT_DIVIDEND'
        else:
            res['status']='REVIEW_REQUIRED_FACTOR_MISMATCH__NO_EVENT_SOURCE_MATCH'
    except RuntimeError as e:
        res['status']='BLOCKED_SOURCE'; res['error']=str(e)
    except Exception as e:
        res['status']='REVIEW_REQUIRED_PARSE_OR_EVENT'; res['error']=f'{type(e).__name__}: {e}'
    (d/'result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    return res


def main():
    results=[None]*len(SAMPLE50)
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(one,s):i for i,s in enumerate(SAMPLE50)}
        for f in as_completed(futs):
            i=futs[f]
            try: results[i]=f.result()
            except Exception as e: results[i]={'symbol':SAMPLE50[i],'status':'INTERNAL_ERROR','error':repr(e)}
            print(json.dumps({'progress':sum(x is not None for x in results),'last':results[i]['symbol'],'status':results[i]['status']},ensure_ascii=False),flush=True)
    counts={}
    for r in results: counts[r['status']]=counts.get(r['status'],0)+1
    summary={
        'artifact':'GP_SAMPLE50_NOMINAL_FACTOR_CROSSCHECK_V478','generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'sample_version':'V3.67_FROZEN','sample_n':50,'formal_window':[FORMAL_BEG,FORMAL_END],
        'threshold_bp':THRESHOLD_BP,'formal_oos_allowed':False,
        'interpretation':'Nominal Eastmoney cash/bonus/transfer + Eastmoney rights + Sohu RAW vs normalized Sina qfq divisor. Nominal mismatches require exact dividend refinement; source failures are not factor failures.',
        'counts':counts,'all_nominal_pass':all(r['status']=='PASS_NOMINAL_EVENT_FACTOR' for r in results),
        'results':results,
    }
    (OUT/'sample50_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'sample50_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['order','symbol','status','event_count','formal_rows','max_diff_bp','error'])
        for i,r in enumerate(results,1):
            v=r.get('factor_validation') or {}
            w.writerow([i,r['symbol'],r['status'],r.get('event_count'),r.get('formal_rows'),v.get('max_diff_bp'),r.get('error')])
    with (OUT/'sample50_events.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['symbol','ex_date','cash_per_share_nominal','stock_ratio','capitalization_ratio','rights_ratio','rights_price','prev_actual_close','event_ratio','source']
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in results:
            for e in r.get('events',[]): w.writerow({'symbol':r['symbol'],**e})
    print(json.dumps({'done':True,'counts':counts,'all_nominal_pass':summary['all_nominal_pass']},ensure_ascii=False))

if __name__=='__main__': main()
