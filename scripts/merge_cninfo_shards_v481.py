from __future__ import annotations

import argparse
from collections import Counter
import json
import pathlib
import time

ARTIFACT='CNINFO_STANDARD_EXACT_TERM_INDEX_V481'
VERSION='V4.81'


def merge_shard_reports(shards: list[dict], expected_scope_n: int=87) -> dict:
    if not shards:
        raise ValueError('no CNINFO shard reports')
    counts={int(s.get('shard_count',-1)) for s in shards}
    if len(counts)!=1:
        raise ValueError(f'inconsistent shard_count values: {sorted(counts)}')
    shard_count=next(iter(counts))
    if shard_count < 1:
        raise ValueError(f'invalid shard_count={shard_count}')
    indices=[int(s.get('shard_index',-1)) for s in shards]
    if sorted(indices)!=list(range(shard_count)):
        raise ValueError(f'incomplete shard partition indices={sorted(indices)} expected={list(range(shard_count))}')

    records=[]
    source_shards=[]
    seen=set()
    for s in sorted(shards,key=lambda x:int(x['shard_index'])):
        if s.get('artifact')!=ARTIFACT or s.get('version')!=VERSION:
            raise ValueError('unexpected CNINFO shard artifact/version')
        for guard in ('formal_promotion','validated_global_provenance_emitted','formal_ready','oos_metrics_allowed'):
            if s.get(guard) is not False:
                raise ValueError(f'shard guard must remain false: {guard}')
        rs=s.get('records') or []
        if int(s.get('scope_symbol_n',len(rs)))!=len(rs):
            raise ValueError(f"scope count mismatch shard={s.get('shard_index')}")
        for r in rs:
            symbol=str(r.get('symbol') or '')
            if not symbol:
                raise ValueError('blank symbol in shard')
            if symbol in seen:
                raise ValueError(f'duplicate CNINFO symbol across shards: {symbol}')
            seen.add(symbol); records.append(r)
        source_shards.append({
            'shard_index':int(s['shard_index']),
            'scope_symbol_n':len(rs),
            'query_ok_n':int(s.get('query_ok_n',sum(r.get('error') is None for r in rs))),
            'query_error_n':int(s.get('query_error_n',sum(r.get('error') is not None for r in rs))),
        })

    if len(records)!=int(expected_scope_n):
        raise ValueError(f'CNINFO merged scope must be exact {expected_scope_n}; got={len(records)}')
    records.sort(key=lambda r:r['symbol'])
    query_ok=sum(r.get('error') is None for r in records)
    event_date_n=sum(len(r.get('event_dates') or []) for r in records)
    matched_event_n=sum(int(r.get('matched_event_n') or 0) for r in records)
    all_matched=sum(r.get('error') is None and int(r.get('matched_event_n') or 0)==len(r.get('event_dates') or []) for r in records)
    status_counts=Counter(
        'QUERY_ERROR' if r.get('error') else
        ('ALL_MATCHED' if int(r.get('matched_event_n') or 0)==len(r.get('event_dates') or []) else 'PARTIAL_MATCH')
        for r in records
    )
    return {
        'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_MERGED_V481',
        'version':VERSION,
        'scope_symbol_n':len(records),
        'shard_count':shard_count,
        'query_ok_n':query_ok,
        'query_error_n':len(records)-query_ok,
        'event_date_n':event_date_n,
        'matched_event_n':matched_event_n,
        'symbols_all_events_matched_n':all_matched,
        'status_counts':dict(status_counts),
        'source_shards':source_shards,
        'records':records,
        'formal_promotion':False,
        'validated_global_provenance_emitted':False,
        'formal_ready':False,
        'oos_metrics_allowed':False,
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--expected-scope-n',type=int,default=87)
    args=ap.parse_args()
    root=pathlib.Path(args.input_dir)
    paths=sorted(root.rglob('CNINFO_STANDARD_EXACT_TERM_INDEX_V481.json'))
    shards=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
    merged=merge_shard_reports(shards,args.expected_scope_n)
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'CNINFO_STANDARD_EXACT_TERM_INDEX_MERGED_V481.json').write_text(
        json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:merged[k] for k in (
        'scope_symbol_n','shard_count','query_ok_n','query_error_n','event_date_n',
        'matched_event_n','symbols_all_events_matched_n','status_counts')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
