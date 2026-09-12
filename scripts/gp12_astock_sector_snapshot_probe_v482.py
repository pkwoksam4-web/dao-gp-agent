from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ID = 'newbiestring-lang/astock'
EXPECTED = [
    'kline_000.parquet',
    'kline_002.parquet',
    'kline_300.parquet',
    'kline_600.parquet',
    'kline_688.parquet',
    'stock_list.parquet',
]
OPTIONAL = ['index_sh.parquet','kline_other.parquet']


def _meta(s):
    lfs=getattr(s,'lfs',None)
    if lfs is not None and not isinstance(lfs,dict):
        lfs={k:getattr(lfs,k,None) for k in ['size','sha256','pointer_size']}
    lfs=lfs or {}
    return {
        'name':getattr(s,'rfilename',None),
        'size':getattr(s,'size',None),
        'lfs_size':lfs.get('size'),
        'lfs_sha256':lfs.get('sha256'),
        'lfs_pointer_size':lfs.get('pointer_size'),
    }


def probe(limit: int=100) -> dict:
    from huggingface_hub import HfApi
    api=HfApi()
    commits=list(api.list_repo_commits(REPO_ID,repo_type='dataset'))[:limit]
    rows=[]
    for c in commits:
        cid=getattr(c,'commit_id',None)
        rec={
            'commit_id':cid,
            'title':getattr(c,'title',None),
            'created_at':str(getattr(c,'created_at',None)),
            'files':{},
            'error':None,
        }
        try:
            info=api.dataset_info(REPO_ID,revision=cid,files_metadata=True)
            by={getattr(s,'rfilename',None):s for s in (info.siblings or [])}
            for name in EXPECTED+OPTIONAL:
                if name in by:
                    rec['files'][name]=_meta(by[name])
            rec['expected_present_n']=sum(n in rec['files'] for n in EXPECTED)
            rec['all_expected_present']=rec['expected_present_n']==len(EXPECTED)
        except Exception as e:
            rec['error']=f'{type(e).__name__}: {e}'
            rec['expected_present_n']=0
            rec['all_expected_present']=False
        rows.append(rec)
    candidates=[r for r in rows if r['all_expected_present']]
    return {
        'artifact':'GP12_ASTOCK_SECTOR_SNAPSHOT_HISTORY_PROBE_V482',
        'version':'V4.82',
        'strategy_id':'GP_V11',
        'repo_id':REPO_ID,
        'commit_n':len(rows),
        'candidate_revision_n':len(candidates),
        'required_files':list(EXPECTED),
        'optional_files':list(OPTIONAL),
        'revisions':rows,
        'candidate_revisions':[r['commit_id'] for r in candidates],
        'sector_source_snapshot_identity_locked':False,
        'sector_source_bytes_hash_bound':False,
        'sector_pit_membership_verified':False,
        'model_freeze_allowed':False,
        'oos_metrics_allowed':False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True)
    ap.add_argument('--limit',type=int,default=100)
    a=ap.parse_args()
    out=probe(a.limit)
    p=Path(a.out); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='revisions'},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
