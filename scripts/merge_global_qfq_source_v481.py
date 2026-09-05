from __future__ import annotations
import argparse, json, pathlib, time

from global_qfq_merge_v481 import merge_records


def read_scope(path: pathlib.Path):
    xs=[x.strip().upper() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(xs)!=847 or len(set(xs))!=847:
        raise RuntimeError(f'exact 847-symbol scope required; rows={len(xs)} unique={len(set(xs))}')
    return xs


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scope',required=True)
    p.add_argument('--input-dir',required=True)
    p.add_argument('--out-dir',required=True)
    args=p.parse_args()
    scope=read_scope(pathlib.Path(args.scope))
    inp=pathlib.Path(args.input_dir)
    files=sorted(inp.glob('GLOBAL_QFQ_SOURCE_COVERAGE_V481_SHARD_*.json'))
    if len(files)!=8:
        raise RuntimeError(f'expected 8 shard summaries, got {len(files)}: {[x.name for x in files]}')
    shards=[]
    for f in files:
        doc=json.loads(f.read_text(encoding='utf-8'))
        shards.append(doc['records'])
    merged=merge_records(scope,shards)
    if not merged['partition_exact']:
        raise RuntimeError(f'V4.81 partition not exact: {merged}')

    ready=[r['symbol'] for r in merged['records'] if r['status']=='SINA_FACTOR_PATH_SOURCE_READY']
    zero=[r['symbol'] for r in merged['records'] if r['status']=='UNKNOWN_ZERO_ACTION_OR_SOURCE_EMPTY']
    unanchored=[r['symbol'] for r in merged['records'] if r['status']=='UNKNOWN_NO_ANCHOR_DIVISOR_BY_FORMAL_END']
    failed=[r['symbol'] for r in merged['records'] if r['status'].startswith('FAILED_')]
    unresolved=sorted(set(zero+unanchored+failed))
    factor_rows=sum(int(r.get('factor_rows') or 0) for r in merged['records'])
    formal_anchor_rows=sum(int(r.get('factor_rows_le_formal_end') or 0) for r in merged['records'])

    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    report={
        'artifact':'GLOBAL_QFQ_SOURCE_COVERAGE_V481','version':'V4.81',
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'scope_n':847,'record_n':merged['record_n'],'partition_exact':True,
        'status_counts':merged['status_counts'],'sina_ready_n':len(ready),'sina_ready_symbols':ready,
        'unknown_zero_action_or_empty_n':len(zero),'unknown_zero_action_or_empty_symbols':zero,
        'unknown_unanchored_n':len(unanchored),'unknown_unanchored_symbols':unanchored,
        'failed_source_n':len(failed),'failed_source_symbols':failed,
        'unresolved_n':len(unresolved),'unresolved_symbols':unresolved,
        'factor_rows_total':factor_rows,'factor_rows_le_formal_end_total':formal_anchor_rows,
        'formal_promotion':False,'global_validated_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
        'interpretation':'Source census only. SINA_FACTOR_PATH_SOURCE_READY means a parseable Sina divisor path with an anchor at or before Formal end; it does not by itself satisfy independent global provenance.',
        'records':merged['records'],
    }
    (out/'GLOBAL_QFQ_SOURCE_COVERAGE_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    checkpoint={
        'artifact':'FORMAL_GATE_CHECKPOINT_V481','version':'V4.81',
        'formal_ready':False,'oos_metrics_allowed':False,
        'price_history':{'status':'CLOSED_V465','p0_remaining':0},
        'pit_st':{'status':'CLOSED_V480','gate_closed':True},
        'adjustment_provenance':{
            'status':'SOURCE_CENSUS_COMPLETE__GLOBAL_PROVENANCE_OPEN',
            'scope_n':847,'sina_ready_n':len(ready),'unresolved_n':len(unresolved),
            'sample50':'CLOSED_V479','global_847':'OPEN',
            'validated_global_provenance_emitted':False,
        },
        'liquidity':{'threshold_cny':80000000,'status':'FROZEN_V370_WAITING_FOR_GLOBAL_ADJUSTMENT_PROVENANCE'},
        'locked_rule':'No Formal OOS and no VALIDATED_GLOBAL_PROVENANCE until full 847 row-level factor provenance and independent validation close.',
    }
    (out/'FORMAL_GATE_CHECKPOINT_V481.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['scope_n','status_counts','sina_ready_n','unresolved_n','factor_rows_total','formal_ready','oos_metrics_allowed']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
