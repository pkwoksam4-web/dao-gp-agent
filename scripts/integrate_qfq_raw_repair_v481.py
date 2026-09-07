from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil

TARGETS=('000069.SZ','001379.SZ')
REPAIR_RUN=34073387924
REPAIR_ARTIFACT='gp-qfq-raw-blocker-repair-v481'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_repair(repair_dir: pathlib.Path) -> tuple[dict,dict[str,dict]]:
    p=repair_dir/'QFQ_RAW_BLOCKER_REPAIR_V481.json'
    if not p.exists():
        raise RuntimeError(f'missing repair report: {p}')
    doc=json.loads(p.read_text(encoding='utf-8'))
    if doc.get('artifact')!='QFQ_RAW_BLOCKER_REPAIR_V481':
        raise RuntimeError('unexpected repair artifact')
    if doc.get('formal_promotion') is not False or doc.get('validated_global_provenance_emitted') is not False:
        raise RuntimeError('repair artifact unexpectedly promoted Formal state')
    recs={r['symbol']:r for r in doc.get('records',[])}
    if set(recs)!=set(TARGETS):
        raise RuntimeError(f'repair target mismatch: {sorted(recs)}')
    return doc,recs


def apply_repairs(repair_dir: pathlib.Path, nominal_dir: pathlib.Path) -> list[dict]:
    _,recs=load_repair(repair_dir)
    applied=[]
    for symbol in TARGETS:
        r=recs[symbol]
        if r.get('raw_provider')!='SOHU_RAW':
            raise RuntimeError(f'{symbol}: only validated SOHU_RAW can replace Sohu input; provider={r.get("raw_provider")}')
        sm=(r.get('source_meta') or {}).get('sohu_repair') or {}
        if sm.get('ok') is not True or sm.get('status')!=200:
            raise RuntimeError(f'{symbol}: repaired Sohu source not HTTP 200')
        rel=sm.get('raw_file')
        if not rel:
            raise RuntimeError(f'{symbol}: repaired Sohu raw_file missing')
        src=repair_dir/rel
        if not src.exists():
            raise RuntimeError(f'{symbol}: repair raw bytes missing: {src}')
        body=src.read_bytes()
        if not body:
            raise RuntimeError(f'{symbol}: repair raw bytes empty')
        if sha256(body)!=sm.get('sha256'):
            raise RuntimeError(f'{symbol}: repair raw SHA mismatch')
        code,ex=symbol.split('.')
        basename=f'{code}_{ex}_sohu_raw_history.js'
        hits=[p for p in nominal_dir.rglob(basename) if p.is_file()]
        if len(hits)!=1:
            raise RuntimeError(f'{symbol}: expected exactly one nominal raw target, found={len(hits)}')
        dst=hits[0]
        old=dst.read_bytes()
        old_sha=sha256(old)
        shutil.copyfile(src,dst)
        new=dst.read_bytes()
        if sha256(new)!=sm['sha256']:
            raise RuntimeError(f'{symbol}: copied repair SHA mismatch')
        applied.append({
            'symbol':symbol,
            'provider':'SOHU_RAW',
            'repair_run':REPAIR_RUN,
            'repair_artifact':REPAIR_ARTIFACT,
            'repair_source_path':str(src),
            'destination_path':str(dst),
            'old_bytes':len(old),
            'old_sha256':old_sha,
            'new_bytes':len(new),
            'new_sha256':sha256(new),
            'repair_status':r.get('status'),
            'repair_max_diff_bp':(r.get('factor_validation') or {}).get('max_diff_bp'),
        })
    return applied


def patch_recalc_output(out_dir: pathlib.Path, applied: list[dict]) -> None:
    report_path=out_dir/'GLOBAL_QFQ_LEDGER_RECALC_V481.json'
    checkpoint_path=out_dir/'FORMAL_GATE_CHECKPOINT_V481_LEDGER_RECALC.json'
    if not report_path.exists() or not checkpoint_path.exists():
        raise RuntimeError('recalc outputs missing for provenance patch')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    amap={r['symbol']:r for r in applied}
    for rec in report.get('records',[]):
        a=amap.get(rec.get('symbol'))
        if not a:
            continue
        sohu=(rec.get('source_meta') or {}).get('sohu') or {}
        if sohu.get('sha256')!=a['new_sha256']:
            raise RuntimeError(f'{rec["symbol"]}: recalc did not consume repaired SHA')
        sohu['provenance']=f'V4.81 repaired Sohu RAW run {REPAIR_RUN} artifact {REPAIR_ARTIFACT}'
        sohu['repair_integrated']=True
        rec['source_meta']['sohu']=sohu
    report['raw_repairs']={
        'status':'INTEGRATED_FROZEN_REPAIR_ARTIFACT',
        'source_run':REPAIR_RUN,
        'source_artifact':REPAIR_ARTIFACT,
        'applied':applied,
    }
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

    checkpoint=json.loads(checkpoint_path.read_text(encoding='utf-8'))
    checkpoint['raw_repairs']={
        'status':'INTEGRATED_FROZEN_REPAIR_ARTIFACT',
        'source_run':REPAIR_RUN,
        'source_artifact':REPAIR_ARTIFACT,
        'symbols':[r['symbol'] for r in applied],
    }
    checkpoint_path.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repair-dir',required=True)
    p.add_argument('--nominal-dir',required=True)
    p.add_argument('--out-dir')
    p.add_argument('--patch-output',action='store_true')
    args=p.parse_args()
    repair=pathlib.Path(args.repair_dir); nominal=pathlib.Path(args.nominal_dir)
    manifest_path=nominal/'RAW_REPAIR_INTEGRATION_V481.json'
    if args.patch_output:
        if not manifest_path.exists():
            raise RuntimeError('integration manifest missing before patch-output')
        applied=json.loads(manifest_path.read_text(encoding='utf-8'))['applied']
        patch_recalc_output(pathlib.Path(args.out_dir),applied)
        print(json.dumps({'patched':True,'out_dir':args.out_dir,'symbols':[r['symbol'] for r in applied]},ensure_ascii=False))
        return
    applied=apply_repairs(repair,nominal)
    doc={
        'artifact':'RAW_REPAIR_INTEGRATION_V481','version':'V4.81','applied':applied,
        'formal_promotion':False,'validated_global_provenance_emitted':False,
    }
    manifest_path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(doc,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
