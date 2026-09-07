from __future__ import annotations

import argparse
import csv
import json
import pathlib

import effective_term_closure_v482 as base
from materialize_standard_exact_pdfs_v481 import _parse_sina_js

THRESHOLD_BP = 5.0
EXPECTED_CURRENT_REMAINING_N = 52
EXPECTED_NEW_EVIDENCE_N = 203
EXPECTED_NEW_EFFECTIVE_N = 128
EXPECTED_NEW_ACCEPTED_N = 124
EXPECTED_NEW_REJECTED_N = 4
EXPECTED_TOTAL_OVERRIDE_N = 191
EXPECTED_NEW_CLOSED_N = 29
EXPECTED_FINAL_REMAINING_N = 23
CURRENT_CHECKPOINT = {
    'PASS':792,
    'EXACT_TERM_REVIEW':52,
    'MISSING_EVENT_REVIEW':0,
    'NOT_APPLICABLE':3,
}


def validate_new_term(event: dict, terms: dict, actual_factor_jump: float, threshold_bp: float=THRESHOLD_BP) -> dict:
    actual=base._positive(actual_factor_jump,'actual_factor_jump')
    try:
        ratio=base.corrected_event_ratio(event,terms)
    except (TypeError, ValueError) as e:
        return {
            'accepted':False,
            'corrected_event_ratio':None,
            'corrected_event_diff_bp':None,
            'threshold_bp':float(threshold_bp),
            'rejection_reason':f'INVALID_EFFECTIVE_TERM:{type(e).__name__}:{e}',
        }
    diff=abs(actual/ratio-1.0)*10000.0
    return {
        'accepted':diff<=float(threshold_bp),
        'corrected_event_ratio':ratio,
        'corrected_event_diff_bp':diff,
        'threshold_bp':float(threshold_bp),
        'rejection_reason':None if diff<=float(threshold_bp) else 'EVENT_JUMP_EXCEEDS_THRESHOLD',
    }


def merge_override_maps(existing: dict[tuple[str,str],float], new: dict[tuple[str,str],float]) -> dict[tuple[str,str],float]:
    overlap=set(existing)&set(new)
    if overlap:
        raise ValueError(f'duplicate override keys: {sorted(overlap)}')
    out=dict(existing); out.update(new); return out


def updated_checkpoint_from_current(current: dict, newly_closed_n: int) -> dict:
    if dict(current)!=CURRENT_CHECKPOINT:
        raise ValueError(f'current checkpoint mismatch: {current}')
    n=int(newly_closed_n)
    if n<0 or n>current['EXACT_TERM_REVIEW']:
        raise ValueError('invalid newly-closed count')
    out=dict(current)
    out['PASS']+=n
    out['EXACT_TERM_REVIEW']-=n
    if sum(out.values())!=847:
        raise ValueError('847 partition invariant failed')
    return out


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _frozen_by_symbol(frozen: dict) -> dict[str,dict]:
    return {str(r.get('symbol') or '').upper():r for r in (frozen.get('records') or [])}


def _event_by_date(record: dict, ex_date: str) -> dict:
    hits=[e for e in (record.get('events') or []) if str(e.get('ex_date') or '')[:10]==ex_date]
    if len(hits)!=1:
        raise ValueError(f'{record.get("symbol")} {ex_date}: expected one frozen event; found={len(hits)}')
    return hits[0]


def close_remaining(
    frozen_closure_dir: pathlib.Path,
    current_closure_dir: pathlib.Path,
    new_evidence_dir: pathlib.Path,
    source_census_dir: pathlib.Path,
) -> dict:
    frozen=_load(_find_unique(frozen_closure_dir,'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json'))
    current=_load(_find_unique(current_closure_dir,'EFFECTIVE_TERM_CLOSURE_V482.json'))
    evidence=_load(_find_unique(new_evidence_dir,'REMAINING_EXACT_MATCHED_PDF_EVIDENCE_V482.json'))

    if current.get('checkpoint_after_effective_terms')!=CURRENT_CHECKPOINT:
        raise ValueError('input closure is not the verified 792/52 checkpoint')
    if current.get('remaining_exact_review_symbol_n')!=EXPECTED_CURRENT_REMAINING_N:
        raise ValueError('remaining-symbol partition changed')
    if current.get('effective_override_event_n')!=67:
        raise ValueError('current 67-term override partition changed')
    if evidence.get('matched_candidate_event_n')!=EXPECTED_NEW_EVIDENCE_N or evidence.get('pdf_text_ok_event_n')!=EXPECTED_NEW_EVIDENCE_N:
        raise ValueError('secondary PDF evidence partition changed')
    if evidence.get('effective_term_event_n')!=EXPECTED_NEW_EFFECTIVE_N:
        raise ValueError('secondary effective-term count changed')
    for obj in (current,evidence):
        if obj.get('formal_promotion') is not False or obj.get('validated_global_provenance_emitted') is not False:
            raise ValueError('non-Formal evidence guard violated')

    frozen_by=_frozen_by_symbol(frozen)
    remaining=set(current.get('remaining_symbols') or [])
    existing={}
    for row in current.get('event_overrides') or []:
        key=(str(row.get('symbol') or '').upper(),str(row.get('ex_date') or '')[:10])
        existing[key]=base._positive(row.get('corrected_event_ratio'),'existing corrected_event_ratio')
    if len(existing)!=67:
        raise ValueError('existing override map is not 67')

    accepted_map={}; accepted_rows=[]; rejected_rows=[]; no_term_rows=[]
    for item in evidence.get('records') or []:
        symbol=str(item.get('symbol') or '').upper(); ex_date=str(item.get('ex_date') or '')[:10]
        if symbol not in remaining:
            raise ValueError(f'secondary evidence outside current remaining scope: {symbol}')
        pdf=item.get('pdf_evidence') or {}; terms=pdf.get('effective_terms') or {}
        if not any(terms.get(k) is not None for k in ('cash_per_share','cap_ratio')):
            no_term_rows.append({'symbol':symbol,'ex_date':ex_date,'pdf_sha256':pdf.get('sha256')})
            continue
        if pdf.get('text_extract_ok') is not True or not (item.get('announcement') or {}):
            raise ValueError(f'{symbol} {ex_date}: parsed term lacks materialized official PDF')
        event=_event_by_date(frozen_by[symbol],ex_date)
        check=validate_new_term(event,terms,item.get('actual_factor_jump'),THRESHOLD_BP)
        row={
            'symbol':symbol,'ex_date':ex_date,
            'nominal_event_ratio':float(item.get('nominal_event_ratio')),
            'actual_factor_jump':float(item.get('actual_factor_jump')),
            'nominal_event_diff_bp':float(item.get('nominal_event_diff_bp')),
            'corrected_event_ratio':check['corrected_event_ratio'],
            'corrected_event_diff_bp':check['corrected_event_diff_bp'],
            'rejection_reason':check.get('rejection_reason'),
            'cash_per_share_effective':terms.get('cash_per_share'),
            'cap_ratio_effective':terms.get('cap_ratio'),
            'cash_evidence_kind':terms.get('cash_evidence_kind'),
            'cap_evidence_kind':terms.get('cap_evidence_kind'),
            'announcement_id':(item.get('announcement') or {}).get('announcementId'),
            'pdf_sha256':pdf.get('sha256'),
        }
        if check['accepted']:
            key=(symbol,ex_date)
            if key in accepted_map:
                raise ValueError(f'duplicate accepted secondary term {key}')
            accepted_map[key]=check['corrected_event_ratio']
            accepted_rows.append(row)
        else:
            rejected_rows.append(row)

    if len(accepted_rows)!=EXPECTED_NEW_ACCEPTED_N or len(rejected_rows)!=EXPECTED_NEW_REJECTED_N:
        raise ValueError(f'expected accepted/rejected {EXPECTED_NEW_ACCEPTED_N}/{EXPECTED_NEW_REJECTED_N}; got {len(accepted_rows)}/{len(rejected_rows)}')
    overrides=merge_override_maps(existing,accepted_map)
    if len(overrides)!=EXPECTED_TOTAL_OVERRIDE_N:
        raise ValueError(f'expected {EXPECTED_TOTAL_OVERRIDE_N} total overrides; got {len(overrides)}')

    symbol_rows=[]
    for symbol in sorted(remaining):
        record=frozen_by[symbol]
        code,exchange=symbol.split('.')
        raw=_find_unique(source_census_dir,f'{code}_{exchange}_sina_qfq.js').read_bytes()
        factors=_parse_sina_js(raw)
        result=base.recompute_symbol_max_diff_bp(record,factors,overrides)
        result['previous_max_diff_bp']=next(r['max_diff_bp'] for r in current['symbol_validation'] if r['symbol']==symbol)
        result['total_override_event_n']=sum(1 for s,_ in overrides if s==symbol)
        result['new_secondary_override_event_n']=sum(1 for s,_ in accepted_map if s==symbol)
        symbol_rows.append(result)

    newly_closed=sorted(r['symbol'] for r in symbol_rows if r['status']=='PASS_EFFECTIVE_TERMS_V482')
    remaining_after=sorted(r['symbol'] for r in symbol_rows if r['status']!='PASS_EFFECTIVE_TERMS_V482')
    if len(newly_closed)!=EXPECTED_NEW_CLOSED_N or len(remaining_after)!=EXPECTED_FINAL_REMAINING_N:
        raise ValueError(f'expected close/remain {EXPECTED_NEW_CLOSED_N}/{EXPECTED_FINAL_REMAINING_N}; got {len(newly_closed)}/{len(remaining_after)}')
    checkpoint=updated_checkpoint_from_current(current['checkpoint_after_effective_terms'],len(newly_closed))
    return {
        'artifact':'REMAINING_EXACT_CLOSURE_V482','version':'V4.82',
        'input_checkpoint':CURRENT_CHECKPOINT,
        'secondary_pdf_event_n':EXPECTED_NEW_EVIDENCE_N,
        'secondary_effective_term_n':EXPECTED_NEW_EFFECTIVE_N,
        'secondary_accepted_override_n':len(accepted_rows),
        'secondary_rejected_override_n':len(rejected_rows),
        'secondary_no_term_n':len(no_term_rows),
        'total_standard_override_n':len(overrides),
        'newly_closed_symbol_n':len(newly_closed),
        'remaining_exact_review_symbol_n':len(remaining_after),
        'newly_closed_symbols':newly_closed,
        'remaining_symbols':remaining_after,
        'checkpoint_after_secondary_exact_terms':checkpoint,
        'accepted_overrides':sorted(accepted_rows,key=lambda r:(r['symbol'],r['ex_date'])),
        'rejected_overrides':sorted(rejected_rows,key=lambda r:(r['symbol'],r['ex_date'])),
        'no_term_events':sorted(no_term_rows,key=lambda r:(r['symbol'],r['ex_date'])),
        'symbol_validation':symbol_rows,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
        'formal_ready':False,'oos_metrics_allowed':False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frozen-closure-dir',required=True)
    ap.add_argument('--current-closure-dir',required=True)
    ap.add_argument('--new-evidence-dir',required=True)
    ap.add_argument('--source-census-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()
    x=close_remaining(pathlib.Path(args.frozen_closure_dir),pathlib.Path(args.current_closure_dir),pathlib.Path(args.new_evidence_dir),pathlib.Path(args.source_census_dir))
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'REMAINING_EXACT_CLOSURE_V482.json').write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'REMAINING_EXACT_CLOSURE_V482.csv').open('w',encoding='utf-8-sig',newline='') as fh:
        fields=['symbol','status','previous_max_diff_bp','max_diff_bp','worst_date','total_override_event_n','new_secondary_override_event_n']
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader()
        for row in x['symbol_validation']: w.writerow({k:row.get(k) for k in fields})
    print(json.dumps({
        'secondary_accepted_override_n':x['secondary_accepted_override_n'],
        'secondary_rejected_override_n':x['secondary_rejected_override_n'],
        'total_standard_override_n':x['total_standard_override_n'],
        'newly_closed_symbol_n':x['newly_closed_symbol_n'],
        'remaining_exact_review_symbol_n':x['remaining_exact_review_symbol_n'],
        'checkpoint':x['checkpoint_after_secondary_exact_terms'],
        'newly_closed_symbols':x['newly_closed_symbols'],
    },ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
