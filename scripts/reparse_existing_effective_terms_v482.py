from __future__ import annotations

import argparse
import copy
import json
import pathlib

from cninfo_effective_terms_v481 import extract_effective_terms


def _has_effective_term(terms: dict | None) -> bool:
    return bool(terms) and any(terms.get(k) is not None for k in ('cash_per_share','cap_ratio'))


def _resolve_text(root: pathlib.Path, text_file: str) -> pathlib.Path:
    name=str(text_file or '').strip()
    if not name:
        raise FileNotFoundError('missing text_file')
    direct=root/name
    nested=root/'text'/name
    hits=[p for p in (direct,nested) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one frozen text {name}; found={len(hits)}')
    return hits[0]


def reparse_report(report: dict, evidence_root: pathlib.Path) -> dict:
    if report.get('formal_promotion') is not False or report.get('validated_global_provenance_emitted') is not False:
        raise ValueError('input evidence violated non-Formal guard')
    records=copy.deepcopy(report.get('records') or [])
    expected=int(report.get('matched_candidate_event_n') or len(records))
    if len(records)!=expected:
        raise ValueError(f'record partition mismatch: expected={expected} records={len(records)}')

    reparsed=0
    parse_errors=0
    effective=0
    changed=0
    for row in records:
        pdf=row.get('pdf_evidence') or {}
        if pdf.get('text_extract_ok') is not True:
            pdf['reparse_error']='TEXT_NOT_EXTRACTED'
            parse_errors+=1
            row['pdf_evidence']=pdf
            continue
        old_terms=copy.deepcopy(pdf.get('effective_terms'))
        try:
            text_path=_resolve_text(evidence_root,str(pdf.get('text_file') or ''))
            terms=extract_effective_terms(text_path.read_text(encoding='utf-8',errors='replace'))
            pdf['effective_terms']=terms
            pdf['reparse_error']=None
            pdf['reparse_text_file']=text_path.name
            reparsed+=1
            if terms!=old_terms:
                changed+=1
            if _has_effective_term(terms):
                effective+=1
        except Exception as e:
            pdf['effective_terms']=None
            pdf['reparse_error']=f'{type(e).__name__}: {e}'
            parse_errors+=1
        row['pdf_evidence']=pdf

    return {
        'artifact':'REMAINING_EXACT_REPARSED_EVIDENCE_V482',
        'version':'V4.82',
        'source_artifact':report.get('artifact'),
        'source_matched_candidate_event_n':expected,
        'reparsed_event_n':reparsed,
        'parse_error_event_n':parse_errors,
        'effective_term_event_n':effective,
        'changed_term_event_n':changed,
        'records':records,
        'formal_promotion':False,
        'validated_global_provenance_emitted':False,
        'formal_ready':False,
        'oos_metrics_allowed':False,
    }


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--evidence-dir',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()
    root=pathlib.Path(args.evidence_dir)
    source=_find_unique(root,'REMAINING_EXACT_MATCHED_PDF_EVIDENCE_V482.json')
    report=json.loads(source.read_text(encoding='utf-8'))
    out_report=reparse_report(report,root)
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'REMAINING_EXACT_REPARSED_EVIDENCE_V482.json').write_text(
        json.dumps(out_report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({
        'source_matched_candidate_event_n':out_report['source_matched_candidate_event_n'],
        'reparsed_event_n':out_report['reparsed_event_n'],
        'parse_error_event_n':out_report['parse_error_event_n'],
        'effective_term_event_n':out_report['effective_term_event_n'],
        'changed_term_event_n':out_report['changed_term_event_n'],
    },ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
