from __future__ import annotations

import argparse
import bisect
import json
import math
import pathlib
import re

from materialize_standard_exact_pdfs_v481 import _parse_sina_js

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
THRESHOLD_BP=5.0
FINAL_CHECKPOINT={'PASS':844,'EXACT_TERM_REVIEW':0,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3}
NA_SYMBOLS=['600074.SH','600485.SH','600677.SH']
EXPECTED_STANDARD_OVERRIDE_N=270
EXPECTED_SPECIAL_OVERRIDE_N=11


def _positive(v,label):
    x=float(v)
    if not math.isfinite(x) or x<=0:
        raise ValueError(f'{label} must be positive finite')
    return x


def _sha_ok(v) -> bool:
    return bool(re.fullmatch(r'[0-9a-fA-F]{64}',str(v or '')))


def _key(row: dict) -> tuple[str,str]:
    symbol=str(row.get('symbol') or '').upper()
    ex_date=str(row.get('ex_date') or '')[:10]
    if not symbol or len(ex_date)!=10:
        raise ValueError('override missing symbol/ex_date')
    return symbol,ex_date


def merge_standard_override_rows(stages: list[list[dict]], expected_n: int=EXPECTED_STANDARD_OVERRIDE_N,
                                 provenance_index: dict[tuple[str,str],dict]|None=None) -> dict[tuple[str,str],dict]:
    provenance_index=provenance_index or {}
    out={}
    for stage in stages:
        for raw in stage or []:
            row=dict(raw); key=_key(row)
            if key in out:
                raise ValueError(f'duplicate standard override key: {key}')
            ratio=_positive(row.get('corrected_event_ratio'),'corrected_event_ratio')
            prov=provenance_index.get(key) or {}
            announcement_id=row.get('announcement_id') or prov.get('announcement_id')
            pdf_sha=row.get('pdf_sha256') or prov.get('pdf_sha256')
            if not announcement_id or not _sha_ok(pdf_sha):
                raise ValueError(f'{key}: standard override lacks official announcement/PDF SHA provenance')
            row['symbol'],row['ex_date']=key
            row['corrected_event_ratio']=ratio
            row['announcement_id']=str(announcement_id)
            row['pdf_sha256']=str(pdf_sha).lower()
            out[key]=row
    if len(out)!=int(expected_n):
        raise ValueError(f'expected {expected_n} unique standard overrides; got {len(out)}')
    return out


def validate_na_records(records: list[dict]) -> dict:
    rows=[r for r in records or [] if r.get('status')=='NOT_APPLICABLE_NO_FORMAL_ROWS']
    symbols=sorted(str(r.get('symbol') or '').upper() for r in rows)
    if symbols!=NA_SYMBOLS:
        raise ValueError(f'N/A symbol partition mismatch: {symbols}')
    for r in rows:
        if int(r.get('formal_rows') or 0)!=0 or r.get('error') not in (None,''):
            raise ValueError(f'{r.get("symbol")}: N/A must have formal_rows=0 and no error')
        meta=r.get('source_meta') or {}
        if not _sha_ok((meta.get('sina') or {}).get('sha256')) or not _sha_ok((meta.get('sohu') or {}).get('sha256')):
            raise ValueError(f'{r.get("symbol")}: N/A source hashes missing')
    return {'count':len(rows),'symbols':symbols,'status':'PASS_3_NA_ZERO_FORMAL_ROWS'}


def classify_special_provenance(rows: list[dict], expected_n: int=EXPECTED_SPECIAL_OVERRIDE_N) -> dict:
    if len(rows or [])!=int(expected_n):
        raise ValueError(f'expected {expected_n} special overrides; got {len(rows or [])}')
    blockers=[]; materialized=0
    seen=set()
    for raw in rows:
        row=dict(raw); key=_key(row)
        if key in seen: raise ValueError(f'duplicate special override {key}')
        seen.add(key)
        _positive(row.get('corrected_event_ratio'),'special corrected_event_ratio')
        sha=row.get('materialized_sha256') or row.get('pdf_sha256') or row.get('evidence_sha256')
        if _sha_ok(sha):
            materialized+=1
        else:
            blockers.append({'symbol':key[0],'ex_date':key[1],'reason':'SPECIAL_EVIDENCE_NOT_MATERIALIZED_WITH_SHA256','evidence_url':row.get('evidence_url')})
    return {'expected_n':int(expected_n),'materialized_n':materialized,'blocker_n':len(blockers),'blockers':blockers}


def decide_gate(*,math_closed: bool,standard_provenance_ok: bool,na_ok: bool,special_provenance: dict) -> dict:
    prov_ok=bool(standard_provenance_ok and na_ok and int(special_provenance.get('blocker_n',-1))==0)
    ready=bool(math_closed and prov_ok)
    return {
        'status':'FORMAL_READY_V482' if ready else ('MATH_CLOSED_PROVENANCE_OPEN' if math_closed else 'MATH_OPEN'),
        'formal_ready':ready,
        'validated_global_provenance_emitted':ready,
        # OOS is a separate gate and is deliberately not opened by this audit.
        'oos_metrics_allowed':False,
        'adjustment_math_closed':bool(math_closed),
        'adjustment_provenance_closed':prov_ok,
    }


def _find_unique(root:pathlib.Path,name:str)->pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1: raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def _load(root:pathlib.Path,name:str)->dict:
    return json.loads(_find_unique(root,name).read_text(encoding='utf-8'))


def _reparse_provenance_index(evidence:dict)->dict[tuple[str,str],dict]:
    out={}
    for item in evidence.get('records') or []:
        key=(str(item.get('symbol') or '').upper(),str(item.get('ex_date') or '')[:10])
        if not key[0] or len(key[1])!=10: continue
        pdf=item.get('pdf_evidence') or {}
        ann=item.get('announcement') or {}
        if ann.get('announcementId') and _sha_ok(pdf.get('sha256')):
            out[key]={'announcement_id':ann.get('announcementId'),'pdf_sha256':pdf.get('sha256')}
    return out


def _factor_series(factors:list[dict]):
    rows=sorted((str(r.get('d') or '')[:10],_positive(r.get('f'),'Sina factor')) for r in factors if r.get('d'))
    if not rows: raise ValueError('empty Sina factor series')
    return [x[0] for x in rows],[x[1] for x in rows]


def _factor_at(dates,values,d):
    i=bisect.bisect_right(dates,d)-1
    if i<0: raise ValueError(f'no factor covering {d}')
    return values[i]


def recompute_record(record:dict,factors:list[dict],overrides:dict[tuple[str,str],float])->dict:
    symbol=str(record.get('symbol') or '').upper()
    dates,values=_factor_series(factors)
    anchor=_factor_at(dates,values,FORMAL_END)
    events=sorted(record.get('events') or [],key=lambda e:str(e.get('ex_date') or ''))
    event_dates=[]; ratios=[]
    for e in events:
        d=str(e.get('ex_date') or '')[:10]
        if not d: continue
        ratio=_positive(overrides.get((symbol,d),e.get('event_ratio')),'event ratio')
        event_dates.append(d); ratios.append(ratio)
    # It is sufficient to test factor-change intervals and event boundaries: both the
    # expected and actual normalized factors are piecewise constant between those dates.
    probes={FORMAL_BEG,FORMAL_END}
    probes.update(d for d in dates if FORMAL_BEG<=d<=FORMAL_END)
    probes.update(d for d in event_dates if FORMAL_BEG<=d<=FORMAL_END)
    max_bp=-1.0; worst=None
    for d in sorted(probes):
        expected=1.0
        for ed,ratio in zip(event_dates,ratios):
            if d < ed <= FORMAL_END: expected*=ratio
        actual=anchor/_factor_at(dates,values,d)
        bp=abs(actual/expected-1.0)*10000.0
        if bp>max_bp: max_bp=bp; worst=d
    return {'symbol':symbol,'max_diff_bp':max_bp,'worst_date':worst,'status':'PASS' if max_bp<=THRESHOLD_BP else 'FAIL'}


def audit(frozen_dir:pathlib.Path,special_dir:pathlib.Path,effective_dir:pathlib.Path,secondary_dir:pathlib.Path,
          reparsed_dir:pathlib.Path,reparsed_evidence_dir:pathlib.Path,recovered_dir:pathlib.Path,
          final_six_dir:pathlib.Path,final_four_dir:pathlib.Path,source_census_dir:pathlib.Path)->dict:
    frozen=_load(frozen_dir,'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json')
    special=_load(special_dir,'SPECIAL_EXRIGHT_CLOSURE_V482.json')
    effective=_load(effective_dir,'EFFECTIVE_TERM_CLOSURE_V482.json')
    secondary=_load(secondary_dir,'REMAINING_EXACT_CLOSURE_V482.json')
    reparsed=_load(reparsed_dir,'REPARSED_REMAINING_CLOSURE_V482.json')
    reparsed_evidence=_load(reparsed_evidence_dir,'REMAINING_EXACT_REPARSED_EVIDENCE_V482.json')
    recovered=_load(recovered_dir,'RECOVERED_REMAINING_CLOSURE_V482.json')
    final_six=_load(final_six_dir,'FINAL_SIX_CLOSURE_V482.json')
    final_four=_load(final_four_dir,'FINAL_FOUR_CLOSURE_V482.json')

    if final_four.get('checkpoint_after_final_four_terms')!=FINAL_CHECKPOINT:
        raise ValueError('final 844/0/0/3 checkpoint mismatch')
    if sum(FINAL_CHECKPOINT.values())!=847: raise ValueError('847 checkpoint invariant failed')
    na=validate_na_records(frozen.get('records') or [])

    prov_idx=_reparse_provenance_index(reparsed_evidence)
    standard=merge_standard_override_rows([
        effective.get('event_overrides') or [],
        secondary.get('accepted_overrides') or [],
        reparsed.get('new_overrides') or [],
        recovered.get('accepted_overrides') or [],
        final_six.get('accepted_overrides') or [],
        final_four.get('accepted_overrides') or [],
    ],provenance_index=prov_idx)

    special_rows=[]; special_map={}
    for r in special.get('records') or []:
        key=_key(r); ratio=_positive(r.get('corrected_event_ratio'),'special corrected_event_ratio')
        if key in standard or key in special_map: raise ValueError(f'override collision: {key}')
        special_map[key]=ratio
        special_rows.append(dict(r))
    if len(special_map)!=EXPECTED_SPECIAL_OVERRIDE_N: raise ValueError('special override count mismatch')
    combined={k:v['corrected_event_ratio'] for k,v in standard.items()}; combined.update(special_map)
    if len(combined)!=281: raise ValueError(f'expected 281 total overrides; got {len(combined)}')

    validations=[]; failures=[]; formal_n=0
    for record in frozen.get('records') or []:
        symbol=str(record.get('symbol') or '').upper()
        if symbol in NA_SYMBOLS: continue
        formal_n+=1
        code,exchange=symbol.split('.')
        raw=_find_unique(source_census_dir,f'{code}_{exchange}_sina_qfq.js').read_bytes()
        result=recompute_record(record,_parse_sina_js(raw),combined)
        validations.append(result)
        if result['status']!='PASS': failures.append(result)
    if formal_n!=844: raise ValueError(f'expected 844 formal symbols; got {formal_n}')
    math_closed=(not failures and all(float(r['max_diff_bp'])<=THRESHOLD_BP for r in validations))

    special_prov=classify_special_provenance(special_rows)
    gate=decide_gate(math_closed=math_closed,standard_provenance_ok=True,na_ok=(na['count']==3),special_provenance=special_prov)
    return {
        'artifact':'FORMAL_READINESS_AUDIT_V482','version':'V4.82','threshold_bp':THRESHOLD_BP,
        'checkpoint':FINAL_CHECKPOINT,'universe_n':847,'formal_symbol_n':formal_n,'na':na,
        'standard_override_n':len(standard),'special_override_n':len(special_map),'total_override_n':len(combined),
        'standard_provenance_ok':True,'special_provenance':special_prov,
        'full_path_pass_n':sum(r['status']=='PASS' for r in validations),'full_path_fail_n':len(failures),
        'max_full_path_diff_bp':max(float(r['max_diff_bp']) for r in validations),
        'failures':failures,'gate':gate,
        'formal_ready':gate['formal_ready'],'validated_global_provenance_emitted':gate['validated_global_provenance_emitted'],
        'oos_metrics_allowed':False,
    }


def main():
    ap=argparse.ArgumentParser()
    for name in ('frozen-dir','special-dir','effective-dir','secondary-dir','reparsed-dir','reparsed-evidence-dir','recovered-dir','final-six-dir','final-four-dir','source-census-dir','out-dir'):
        ap.add_argument('--'+name,required=True)
    a=ap.parse_args()
    x=audit(pathlib.Path(a.frozen_dir),pathlib.Path(a.special_dir),pathlib.Path(a.effective_dir),pathlib.Path(a.secondary_dir),
            pathlib.Path(a.reparsed_dir),pathlib.Path(a.reparsed_evidence_dir),pathlib.Path(a.recovered_dir),
            pathlib.Path(a.final_six_dir),pathlib.Path(a.final_four_dir),pathlib.Path(a.source_census_dir))
    out=pathlib.Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'FORMAL_READINESS_AUDIT_V482.json').write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({
        'checkpoint':x['checkpoint'],'full_path_pass_n':x['full_path_pass_n'],'full_path_fail_n':x['full_path_fail_n'],
        'max_full_path_diff_bp':x['max_full_path_diff_bp'],'standard_override_n':x['standard_override_n'],
        'special_override_n':x['special_override_n'],'special_provenance_blocker_n':x['special_provenance']['blocker_n'],
        'gate':x['gate'],
    },ensure_ascii=False,indent=2))

if __name__=='__main__': main()
