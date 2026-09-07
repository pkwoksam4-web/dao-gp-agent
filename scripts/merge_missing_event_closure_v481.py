from __future__ import annotations

import argparse
import csv
import json
import pathlib
import time
from collections import Counter

BASE_MISSING_STATUS='REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH'
PASS_STATUSES={
    'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR',
    'PASS_GLOBAL_LEDGER_PROVEN_NO_ACTION',
    'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR',
}
EXACT_REVIEW_STATUSES={
    'REVIEW_GLOBAL_LEDGER_EXACT_TERMS',
    'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',
}
NA_STATUSES={'NOT_APPLICABLE_NO_FORMAL_ROWS'}


def merge_resolved_record(base: dict, resolved: dict, source_group: str) -> dict:
    if not isinstance(base,dict) or not isinstance(resolved,dict):
        raise ValueError('base and resolved records must be objects')
    symbol=str(base.get('symbol') or '').upper()
    if not symbol or str(resolved.get('symbol') or '').upper()!=symbol:
        raise ValueError('symbol mismatch')
    if base.get('status')!=BASE_MISSING_STATUS:
        raise ValueError(f'{symbol} base record is not missing-event review')
    if resolved.get('coverage_complete') is not True:
        raise ValueError(f'{symbol} resolved record lacks complete event coverage')
    status=resolved.get('status')
    if status not in {'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR','REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'}:
        raise ValueError(f'{symbol} unsupported resolved status: {status}')
    if resolved.get('error') not in (None,''):
        raise ValueError(f'{symbol} resolved record carries error')

    out=dict(base)
    prior_missing=list(base.get('missing_in_ledger') or [])
    out.update({
        'status':status,
        'missing_in_ledger':[],
        'factor_validation':resolved.get('factor_validation'),
        'events':resolved.get('events') or [],
        'formal_promotion':False,
        'validated_global_provenance_emitted':False,
    })
    for key in (
        'coverage_complete','base_event_dates','missing_event_dates','combined_event_dates',
        'action_dates','sina_factor_change_dates','new_profiles','source_meta','error',
    ):
        if key in resolved:
            out[key]=resolved.get(key)
    out['missing_event_resolution']={
        'source_group':str(source_group),
        'prior_status':BASE_MISSING_STATUS,
        'prior_missing_in_ledger':prior_missing,
        'resolved_status':status,
        'coverage_complete':True,
        'formal_promotion':False,
        'validated_global_provenance_emitted':False,
    }
    return out


def summarize_merged_records(records: list[dict]) -> dict:
    statuses=[r.get('status') for r in records]
    counts=Counter(statuses)
    return {
        'record_n':len(records),
        'status_counts':dict(sorted(counts.items(),key=lambda kv:str(kv[0]))),
        'pass_n':sum(counts.get(s,0) for s in PASS_STATUSES),
        'exact_review_n':sum(counts.get(s,0) for s in EXACT_REVIEW_STATUSES),
        'missing_event_n':counts.get(BASE_MISSING_STATUS,0),
        'not_applicable_n':sum(counts.get(s,0) for s in NA_STATUSES),
    }


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load_json(root: pathlib.Path, name: str) -> dict:
    return json.loads(_find_unique(root,name).read_text(encoding='utf-8'))


def _resolved_map(report: dict, expected_n: int, label: str) -> dict[str,dict]:
    rows=report.get('records') or []
    if len(rows)!=expected_n:
        raise RuntimeError(f'{label} record count mismatch: {len(rows)}')
    by={str(r.get('symbol') or '').upper():r for r in rows}
    if len(by)!=expected_n or '' in by:
        raise RuntimeError(f'{label} symbol partition mismatch')
    if any(r.get('coverage_complete') is not True for r in rows):
        raise RuntimeError(f'{label} contains incomplete event coverage')
    return by


def merge_reports(base_report: dict, recalc7: dict, recalc53: dict) -> dict:
    base_rows=base_report.get('records') or []
    if base_report.get('scope_n')!=847 or base_report.get('record_n')!=847 or base_report.get('partition_exact') is not True:
        raise RuntimeError('base 847 checkpoint invariant mismatch')
    if len(base_rows)!=847 or len({r.get('symbol') for r in base_rows})!=847:
        raise RuntimeError('base 847 record partition mismatch')

    by7=_resolved_map(recalc7,7,'recalc7')
    by53=_resolved_map(recalc53,53,'recalc53')
    if set(by7)&set(by53):
        raise RuntimeError('recalc7/recalc53 symbol overlap')
    resolved={**by7,**by53}
    if len(resolved)!=60:
        raise RuntimeError('resolved symbol union is not exact 60')

    base_missing={str(r.get('symbol') or '').upper() for r in base_rows if r.get('status')==BASE_MISSING_STATUS}
    if base_missing!=set(resolved):
        raise RuntimeError('resolved symbols do not exactly equal base missing-event partition')

    merged=[]
    for row in base_rows:
        symbol=str(row.get('symbol') or '').upper()
        if symbol in by7:
            merged.append(merge_resolved_record(row,by7[symbol],'recalc7'))
        elif symbol in by53:
            merged.append(merge_resolved_record(row,by53[symbol],'recalc53'))
        else:
            merged.append(row)

    summary=summarize_merged_records(merged)
    if summary!={**summary,'status_counts':summary['status_counts']}:
        raise AssertionError('unreachable')
    if summary['record_n']!=847 or summary['pass_n']!=746 or summary['exact_review_n']!=98 or summary['missing_event_n']!=0 or summary['not_applicable_n']!=3:
        raise RuntimeError(f'closure count invariant mismatch: {summary}')
    if summary['pass_n']+summary['exact_review_n']+summary['missing_event_n']+summary['not_applicable_n']!=847:
        raise RuntimeError('closure category partition does not sum to 847')

    return {
        'artifact':'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481',
        'version':'V4.81',
        'scope_n':847,
        'record_n':847,
        'partition_exact':True,
        'missing_event_status':'CLOSED_V481',
        'summary':summary,
        'formal_promotion':False,
        'validated_global_provenance_emitted':False,
        'formal_ready':False,
        'oos_metrics_allowed':False,
        'records':merged,
    }


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-dir',required=True)
    ap.add_argument('--recalc7-dir',required=True)
    ap.add_argument('--recalc53-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()

    base=_load_json(pathlib.Path(args.base_dir),'GLOBAL_QFQ_LEDGER_RECALC_V481.json')
    r7=_load_json(pathlib.Path(args.recalc7_dir),'MISSING_EVENT_FACTOR_RECALC_V481.json')
    r53=_load_json(pathlib.Path(args.recalc53_dir),'MISSING_EVENT_FACTOR_RECALC_53_V481.json')
    out=merge_reports(base,r7,r53)
    out['generated_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

    root=pathlib.Path(args.out_dir); root.mkdir(parents=True,exist_ok=True)
    (root/'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    review=[r for r in out['records'] if r.get('status') in EXACT_REVIEW_STATUSES]
    with (root/'GLOBAL_QFQ_EXACT_TERM_REVIEW_QUEUE_AFTER_MISSING_CLOSURE_V481.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['symbol','status','max_diff_bp','source_group','prior_missing_in_ledger']
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in review:
            fv=r.get('factor_validation') or {}
            mr=r.get('missing_event_resolution') or {}
            w.writerow({
                'symbol':r.get('symbol'),'status':r.get('status'),'max_diff_bp':fv.get('max_diff_bp'),
                'source_group':mr.get('source_group'),'prior_missing_in_ledger':'|'.join(mr.get('prior_missing_in_ledger') or []),
            })
    checkpoint={
        'version':'V4.81','price_history':'CLOSED_V465','pit_st':'CLOSED_V480','sample50_qfq':'CLOSED_V479',
        'sina_847_source_coverage':'CLOSED_V481','global_event_ledger_coverage':'CLOSED_V481',
        'missing_event_coverage':'CLOSED_V481','global_adjustment_provenance':'OPEN_EXACT_TERM_REVIEW_98',
        'pass_n':746,'exact_term_review_n':98,'missing_event_review_n':0,'not_applicable_n':3,
        'formal_ready':False,'oos_metrics_allowed':False,
    }
    (root/'FORMAL_READINESS_CHECKPOINT_AFTER_MISSING_EVENT_CLOSURE_V481.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'summary':out['summary'],'checkpoint':checkpoint},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
