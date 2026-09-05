from __future__ import annotations
import argparse, json, pathlib, time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from global_qfq_source_v481 import (
    FORMAL_END, classify_source, parse_sina_qfq_js, shard_symbols, sina_symbol,
)

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36'


def read_scope(path: pathlib.Path):
    symbols=[x.strip().upper() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(symbols)!=847 or len(set(symbols))!=847:
        raise RuntimeError(f'V4.81 requires exact 847-symbol scope; rows={len(symbols)} unique={len(set(symbols))}')
    for s in symbols:
        sina_symbol(s)
    return symbols


def fetch_sina(symbol: str, attempts: int=3):
    ss=sina_symbol(symbol)
    url=f'https://finance.sina.com.cn/realstock/company/{ss}/qfq.js'
    last={'status':None,'content_type':None,'body':b'','error':None,'attempts':0,'url':url}
    for attempt in range(1, attempts+1):
        headers={'User-Agent':UA,'Accept':'*/*','Referer':'https://finance.sina.com.cn/'}
        try:
            with urlopen(Request(url,headers=headers), timeout=25) as r:
                body=r.read()
                return {
                    'status':getattr(r,'status',200),
                    'content_type':r.headers.get('Content-Type'),
                    'body':body,
                    'error':None,
                    'attempts':attempt,
                    'url':url,
                }
        except HTTPError as e:
            try: body=e.read()
            except Exception: body=b''
            last={
                'status':e.code,
                'content_type':e.headers.get('Content-Type') if e.headers else None,
                'body':body,
                'error':f'HTTPError: {e}',
                'attempts':attempt,
                'url':url,
            }
        except Exception as e:
            last={
                'status':None,'content_type':None,'body':b'',
                'error':f'{type(e).__name__}: {e}','attempts':attempt,'url':url,
            }
        if attempt < attempts:
            time.sleep(0.8*attempt)
    return last


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scope',required=True)
    p.add_argument('--out-dir',required=True)
    p.add_argument('--shard-index',required=True,type=int)
    p.add_argument('--shard-count',required=True,type=int)
    args=p.parse_args()

    scope=read_scope(pathlib.Path(args.scope))
    selected=shard_symbols(scope,args.shard_index,args.shard_count)
    out=pathlib.Path(args.out_dir); raw_dir=out/'raw'; raw_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,symbol in enumerate(selected,1):
        fetched=fetch_sina(symbol)
        raw=fetched['body']
        raw_name=symbol.replace('.','_')+'_sina_qfq.js'
        (raw_dir/raw_name).write_bytes(raw)
        try:
            rows=parse_sina_qfq_js(raw) if raw else []
            rec=classify_source(symbol,fetched['status'],fetched['content_type'],raw,rows,FORMAL_END)
            rec['parsed_factor_rows']=rows
        except Exception as e:
            rec=classify_source(symbol,fetched['status'],fetched['content_type'],raw,[],FORMAL_END)
            rec['status']='FAILED_PARSE'
            rec['parse_error']=f'{type(e).__name__}: {e}'
            rec['parsed_factor_rows']=[]
        rec.update({
            'url':fetched['url'],'fetch_error':fetched['error'],'attempts':fetched['attempts'],
            'raw_file':'raw/'+raw_name,'formal_promotion':False,
        })
        records.append(rec)
        if i%20==0 or i==len(selected):
            print(json.dumps({'shard':args.shard_index,'progress':i,'total':len(selected),'symbol':symbol,'status':rec['status']},ensure_ascii=False),flush=True)
        time.sleep(0.12)

    from collections import Counter
    counts=Counter(r['status'] for r in records)
    report={
        'artifact':f'GLOBAL_QFQ_SOURCE_COVERAGE_V481_SHARD_{args.shard_index}',
        'version':'V4.81','generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'formal_window_end':FORMAL_END,'provider':'Sina finance qfq.js','scope_n':len(scope),
        'shard_index':args.shard_index,'shard_count':args.shard_count,'shard_symbol_n':len(selected),
        'status_counts':dict(sorted(counts.items())),'formal_promotion':False,
        'global_validated_provenance_emitted':False,
        'rule':'Empty/failed/unanchored Sina source never defaults to factor=1 or VALIDATED_GLOBAL_PROVENANCE.',
        'records':records,
    }
    (out/f'GLOBAL_QFQ_SOURCE_COVERAGE_V481_SHARD_{args.shard_index}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'done':True,'shard':args.shard_index,'symbols':len(records),'status_counts':report['status_counts']},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
