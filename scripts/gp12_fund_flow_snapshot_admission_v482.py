from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REPO_ID = 'ellendan/a-share-21'
SOURCE_COMMIT = '227be520b89ed737dd65bea4785a41ae39a9b7a4'
FILENAME = 'all-prices-with-values-250423.csv'
EXPECTED_SIZE_BYTES = 2_134_704_074
EXPECTED_SHA256 = '034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
FLOW_COLUMNS = [
    'dde_l','l_net_value','net_flow_rate','act_buy_xl','pas_buy_xl','act_sell_xl','pas_sell_xl',
    'act_buy_l','pas_buy_l','act_sell_l','pas_sell_l','act_buy_m','pas_buy_m','act_sell_m',
    'pas_sell_m','buy_l','sell_l',
]


def _require(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError(msg)


def sha256_file(path: str | Path, block: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def validate_remote_pointer(text: str) -> dict:
    lines=[x.strip() for x in str(text).splitlines() if x.strip()]
    _require(len(lines) == 3, 'remote pointer line count mismatch')
    _require(lines[0] == 'version https://git-lfs.github.com/spec/v1', 'remote pointer version mismatch')
    m=re.fullmatch(r'oid sha256:([0-9a-f]{64})', lines[1])
    _require(m is not None, 'remote pointer oid malformed')
    sm=re.fullmatch(r'size (\d+)', lines[2])
    _require(sm is not None, 'remote pointer size malformed')
    digest=m.group(1)
    size=int(sm.group(1))
    _require(digest == EXPECTED_SHA256, 'remote pointer SHA256 mismatch')
    _require(size == EXPECTED_SIZE_BYTES, 'remote pointer size mismatch')
    return {'sha256': digest, 'size_bytes': size}


def build_fund_flow_snapshot_admission(scan: dict, remote_pointer_verified: bool) -> dict:
    _require(remote_pointer_verified is True, 'remote pointer identity not verified')
    identity=(
        scan.get('repo_id') == REPO_ID
        and scan.get('source_commit') == SOURCE_COMMIT
        and scan.get('filename') == FILENAME
        and int(scan.get('actual_size_bytes', -1)) == EXPECTED_SIZE_BYTES
        and str(scan.get('actual_sha256','')).lower() == EXPECTED_SHA256
    )
    _require(identity, 'payload identity mismatch')
    cols=set(scan.get('columns_present') or [])
    missing=[c for c in FLOW_COLUMNS if c not in cols]
    _require(not missing, 'missing required flow columns: '+','.join(missing))
    _require('code' in cols and 'date' in cols, 'code/date columns missing')
    _require(int(scan.get('rows',0)) > 0 and int(scan.get('symbols',0)) > 0, 'empty snapshot scan')
    first=str(scan.get('first_date') or '')[:10]
    last=str(scan.get('last_date') or '')[:10]
    _require(bool(first and last), 'snapshot date coverage missing')
    formal_complete=(first <= FORMAL_START and last >= FORMAL_END)
    non_null={c:int((scan.get('flow_non_null_rows') or {}).get(c,0)) for c in FLOW_COLUMNS}
    _require(all(v >= 0 for v in non_null.values()), 'invalid flow non-null counts')
    return {
        'artifact':'GP12_FUND_FLOW_SNAPSHOT_ADMISSION_V482',
        'version':'V4.82',
        'strategy_id':'GP_V11',
        'status':'PASS_LOCKED_FUND_FLOW_SNAPSHOT_PAYLOAD_VERIFIED_PARTIAL_WINDOW',
        'formal_window':[FORMAL_START,FORMAL_END],
        'source':{
            'repo_id':REPO_ID,
            'source_commit':SOURCE_COMMIT,
            'filename':FILENAME,
            'expected_size_bytes':EXPECTED_SIZE_BYTES,
            'expected_sha256':EXPECTED_SHA256,
            'actual_size_bytes':int(scan['actual_size_bytes']),
            'actual_sha256':str(scan['actual_sha256']).lower(),
            'rows':int(scan['rows']),
            'symbols':int(scan['symbols']),
            'first_date':first,
            'last_date':last,
            'flow_columns':list(FLOW_COLUMNS),
            'flow_non_null_rows':non_null,
        },
        'remote_pointer_identity_verified':True,
        'actual_snapshot_bytes_verified_in_current_recovery':True,
        'single_original_snapshot_policy_verified':True,
        'auto_converted_hf_parquet_allowed':False,
        'formal_window_coverage_complete':bool(formal_complete),
        'pit_known_at_semantics_recovered':False,
        'factor_formula_recovered':False,
        'remaining_data_gaps':[
            *([] if formal_complete else ['FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE']),
            'FUND_FLOW_PIT_KNOWN_AT_UNBOUND',
        ],
        'remaining_contract_gaps':[
            'PRICE_FUND_EFFICIENCY_FORMULA_PULSE_FILTER_AND_NORMALIZATION_MISSING',
        ],
        'blocker':'PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE',
        'blocker_closed':False,
        'model_freeze_allowed':False,
        'oos_metrics_allowed':False,
    }


def scan_snapshot(path: str | Path) -> dict:
    p=Path(path)
    _require(p.is_file(), 'snapshot file missing')
    size=p.stat().st_size
    digest=sha256_file(p)
    _require(size == EXPECTED_SIZE_BYTES and digest == EXPECTED_SHA256, 'payload identity mismatch')
    try:
        import pandas as pd
    except Exception as e:
        raise RuntimeError('pandas is required for snapshot scan') from e
    header=list(pd.read_csv(p,nrows=0).columns)
    use=['code','date',*FLOW_COLUMNS]
    missing=[c for c in use if c not in header]
    _require(not missing, 'missing required flow columns: '+','.join(missing))
    rows=0
    symbols=set()
    first=None
    last=None
    non_null={c:0 for c in FLOW_COLUMNS}
    for chunk in pd.read_csv(p,usecols=use,chunksize=200_000,low_memory=False):
        rows += len(chunk)
        symbols.update(chunk['code'].dropna().astype(str).str.strip().tolist())
        d=pd.to_datetime(chunk['date'],errors='coerce')
        if d.notna().any():
            lo=d.min(); hi=d.max()
            first=lo if first is None or lo < first else first
            last=hi if last is None or hi > last else last
        for c in FLOW_COLUMNS:
            non_null[c] += int(chunk[c].notna().sum())
    return {
        'repo_id':REPO_ID,
        'source_commit':SOURCE_COMMIT,
        'filename':FILENAME,
        'actual_size_bytes':size,
        'actual_sha256':digest,
        'rows':rows,
        'symbols':len(symbols),
        'first_date':None if first is None else first.strftime('%Y-%m-%d'),
        'last_date':None if last is None else last.strftime('%Y-%m-%d'),
        'columns_present':header,
        'flow_non_null_rows':non_null,
    }


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--snapshot',required=True)
    ap.add_argument('--pointer',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    pointer=validate_remote_pointer(Path(a.pointer).read_text(encoding='utf-8'))
    scan=scan_snapshot(a.snapshot)
    out=build_fund_flow_snapshot_admission(scan,remote_pointer_verified=bool(pointer))
    dst=Path(a.out); dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
