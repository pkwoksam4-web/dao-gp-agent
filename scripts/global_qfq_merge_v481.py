from __future__ import annotations
from collections import Counter


def merge_records(scope, shards):
    scope=[str(s).strip().upper() for s in scope]
    flat=[r for shard in shards for r in shard]
    counts=Counter(str(r.get('symbol','')).strip().upper() for r in flat)
    duplicates=sorted(s for s,n in counts.items() if s and n>1)
    scope_set=set(scope)
    got_set={s for s in counts if s}
    missing=sorted(scope_set-got_set)
    extra=sorted(got_set-scope_set)
    statuses=Counter(str(r.get('status') or 'MISSING_STATUS') for r in flat)
    return {
        'scope_n':len(scope),
        'record_n':len(flat),
        'partition_exact': len(scope)==len(set(scope)) and not duplicates and not missing and not extra and len(flat)==len(scope),
        'duplicate_symbols':duplicates,
        'missing_symbols':missing,
        'extra_symbols':extra,
        'status_counts':dict(sorted(statuses.items())),
        'records':sorted(flat,key=lambda r:str(r.get('symbol',''))),
    }
