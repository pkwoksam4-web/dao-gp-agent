from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import time
from collections import Counter, defaultdict

from sample50_validate import (
    Action,
    compare_factor_path,
    event_ratio,
    expected_factor_for_date,
    parse_sina_qfq,
    parse_sohu_history_bytes,
    prev_close_before,
    sina_normalized_for_date,
)
from missing_event_terms_v481 import parse_impl_plan_profile
from missing_event_factor_recalc_v481 import (
    canonical_supplemental_profile,
    extract_f10_target_profile,
    classify_missing_event_recalc,
)
from recalc_global_qfq_from_ledger_v481_fixed import sina_factor_change_dates

FORMAL_BEG='2020-06-01'
FORMAL_END='2026-04-17'
THRESHOLD_BP=5.0
TARGET_SYMBOLS=(
    '000564.SZ','000981.SZ','002076.SZ','300117.SZ','300262.SZ','600070.SH','600190.SH',
)
BASE_COUNTS={
    'PASS':702,
    'EXACT_TERM_REVIEW':82,
    'MISSING_EVENT_REVIEW':60,
    'NOT_APPLICABLE':3,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits=[p for p in root.rglob(name) if p.is_file()]
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def build_basename_index(root: pathlib.Path, suffix: str) -> dict[str,list[pathlib.Path]]:
    out=defaultdict(list)
    for p in root.rglob('*'+suffix):
        if p.is_file(): out[p.name].append(p)
    return dict(out)


def unique_from_index(index: dict[str,list[pathlib.Path]], name: str) -> pathlib.Path:
    hits=index.get(name,[])
    if len(hits)!=1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def split_dates(text: str) -> list[str]:
    return [x for x in str(text or '').split('|') if x]


def target_dates_for_symbol(symbol: str) -> list[str]:
    out=[]
    for d in (
        '2020-07-02','2020-07-10','2020-07-20','2020-08-11','2021-06-25','2021-07-07',
        '2021-08-20','2021-12-31','2022-02-25','2022-06-24','2022-12-21','2024-06-26',
    ):
        try:
            canonical_supplemental_profile(symbol,d)
        except KeyError:
            continue
        out.append(d)
    return sorted(out)


def load_base_review(path: pathlib.Path) -> dict[str,dict]:
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    by={r['symbol']:r for r in rows if r.get('symbol') in TARGET_SYMBOLS}
    if set(by)!=set(TARGET_SYMBOLS):
        raise RuntimeError(f'base review target partition mismatch: {sorted(by)}')
    for symbol,row in by.items():
        if row.get('status')!='REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH':
            raise RuntimeError(f'{symbol} is not base missing-event review')
        expected=target_dates_for_symbol(symbol)
        missing=sorted(split_dates(row.get('missing_in_ledger')))
        sina=sorted(split_dates(row.get('sina_event_dates')))
        ledger=sorted(split_dates(row.get('ledger_event_dates')))
        if missing!=expected:
            raise RuntimeError(f'{symbol} missing-date contract mismatch expected={expected} actual={missing}')
        if sina!=expected:
            raise RuntimeError(f'{symbol} Sina-date contract mismatch expected={expected} actual={sina}')
        if ledger:
            raise RuntimeError(f'{symbol} unexpectedly has global-ledger events: {ledger}')
    return by


def decode_html(raw: bytes) -> str:
    for enc in ('gb18030','utf-8-sig','gbk'):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode('gb18030',errors='replace')


def compact_text(html: str) -> str:
    s=re.sub(r'<script\b[^>]*>.*?</script>',' ',html,flags=re.I|re.S)
    s=re.sub(r'<style\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S)
    s=re.sub(r'<[^>]+>',' ',s)
    s=s.replace('&nbsp;',' ')
    return re.sub(r'\s+',' ',s).strip()


def sina_sharebonus_profiles(raw: bytes) -> dict[str,str]:
    text=compact_text(decode_html(raw))
    # Row grammar in frozen Sina share-bonus pages:
    # announcement-date send cap cash 实施 ex-date record-date red-stock-date 查看
    rx=re.compile(
        r'(\d{4}-\d{2}-\d{2})\s+'
        r'([0-9]+(?:\.[0-9]+)?)\s+'
        r'([0-9]+(?:\.[0-9]+)?)\s+'
        r'([0-9]+(?:\.[0-9]+)?)\s+实施\s+'
        r'(\d{4}-\d{2}-\d{2})\s+'
    )
    out={}
    for _,send,cap,cash,ex_date in rx.findall(text):
        parts=[]
        if float(send)!=0: parts.append(f'送{send}')
        if float(cap)!=0: parts.append(f'转{cap}')
        if float(cash)!=0: parts.append(f'派{cash}元')
        if not parts: continue
        profile='10'+''.join(parts)
        if ex_date in out and out[ex_date]!=profile:
            raise ValueError(f'conflicting Sina profiles at {ex_date}: {out[ex_date]} vs {profile}')
        out[ex_date]=profile
    if not out:
        raise ValueError('no implemented rows parsed from frozen Sina sharebonus HTML')
    return out


def normalize_profile(profile: str) -> dict:
    return parse_impl_plan_profile(profile)


def validate_term_equal(a: str, b: str) -> None:
    x=normalize_profile(a); y=normalize_profile(b)
    keys=('cash_per_share','stock_ratio','capitalization_ratio','rights_ratio')
    if any(abs(float(x[k])-float(y[k]))>1e-12 for k in keys):
        raise ValueError(f'implementation term mismatch: {a!r} vs {b!r}')


def load_evidence(
    supplemental_dir: pathlib.Path,
    f10_dir: pathlib.Path,
) -> dict[tuple[str,str],dict]:
    supp_path=find_unique(supplemental_dir,'SUPPLEMENTAL_MISSING_EVENT_EVIDENCE_V481.json')
    supp=json.loads(supp_path.read_text(encoding='utf-8'))
    if supp.get('artifact')!='SUPPLEMENTAL_MISSING_EVENT_EVIDENCE_V481' or supp.get('positive_n')!=6 or supp.get('unresolved_n')!=0:
        raise RuntimeError('supplemental artifact is not exact 6/6 positive evidence')
    supp_records={r['symbol']:r for r in supp.get('records',[])}

    f10_path=find_unique(f10_dir,'F10_UNRESOLVED_HISTORY_PROBE_V481.json')
    f10=json.loads(f10_path.read_text(encoding='utf-8'))
    if f10.get('artifact')!='F10_UNRESOLVED_HISTORY_PROBE_V481' or f10.get('resolved_n')!=1:
        raise RuntimeError('F10 unresolved-history artifact does not have the expected one resolved target')
    f10_records={r['symbol']:r for r in f10.get('records',[])}

    evidence={}

    # Three special restructuring/large-capitalization rows are already positively
    # matched by date+term in the supplemental manifest. Retain and verify raw SHA.
    for symbol in ('000564.SZ','000981.SZ','002076.SZ'):
        r=supp_records.get(symbol)
        if not r or r.get('status')!='SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE' or not r.get('target_term_near'):
            raise RuntimeError(f'{symbol} supplemental positive evidence missing')
        raw=find_unique(supplemental_dir,r['raw_file']); b=raw.read_bytes()
        if sha256_bytes(b)!=r.get('sha256'):
            raise RuntimeError(f'{symbol} supplemental raw SHA mismatch')
        date=r['target_date']; source_profile=r['expected_term']
        canonical=canonical_supplemental_profile(symbol,date)
        validate_term_equal(source_profile,canonical)
        evidence[(symbol,date)]={
            'profile':canonical,'source':r['source'],'raw_sha256':r['sha256'],
            'raw_file':r['raw_file'],'evidence_status':r['status'],
        }

    # Frozen Sina pages contain the complete Formal-window rows for these symbols,
    # including dates beyond the first date originally targeted by the manifest.
    for symbol in ('300117.SZ','600070.SH','600190.SH'):
        r=supp_records.get(symbol)
        if not r or r.get('status')!='SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE':
            raise RuntimeError(f'{symbol} frozen Sina evidence manifest missing')
        raw=find_unique(supplemental_dir,r['raw_file']); b=raw.read_bytes()
        if sha256_bytes(b)!=r.get('sha256'):
            raise RuntimeError(f'{symbol} frozen Sina raw SHA mismatch')
        profiles=sina_sharebonus_profiles(b)
        for date in target_dates_for_symbol(symbol):
            if date not in profiles:
                raise RuntimeError(f'{symbol} target {date} absent from frozen Sina sharebonus table')
            canonical=canonical_supplemental_profile(symbol,date)
            validate_term_equal(profiles[date],canonical)
            evidence[(symbol,date)]={
                'profile':canonical,'source':'SINA_SHAREBONUS_FROZEN_HTML',
                'raw_sha256':r['sha256'],'raw_file':r['raw_file'],
                'evidence_status':'FROZEN_SINA_IMPLEMENTED_ROW_DATE_TERM_MATCH',
            }

    # 300262 is the one target positively resolved by the frozen EastMoney F10 PageAjax.
    symbol='300262.SZ'; date='2020-08-11'; r=f10_records.get(symbol)
    if not r or not r.get('resolved'):
        raise RuntimeError('300262.SZ F10 target not resolved')
    hits=(r.get('pageajax') or {}).get('hits') or []
    target={'date':date,'status':'F10_PAGEAJAX_TARGET_DATE_HIT','hits':hits}
    source_profile=extract_f10_target_profile(target)
    canonical=canonical_supplemental_profile(symbol,date)
    validate_term_equal(source_profile,canonical)
    pa=r['pageajax']
    evidence[(symbol,date)]={
        'profile':canonical,'source':'EASTMONEY_F10_PAGEAJAX_FROZEN',
        'raw_sha256':pa.get('decoded_sha256'),'raw_file':pa.get('decoded_file'),
        'evidence_status':'F10_PAGEAJAX_TARGET_DATE_HIT',
    }

    expected={(s,d) for s in TARGET_SYMBOLS for d in target_dates_for_symbol(s)}
    if set(evidence)!=expected or len(evidence)!=12:
        raise RuntimeError(f'evidence partition is not exact 12 dates: have={sorted(evidence)}')
    return evidence


def make_actions(symbol: str, evidence: dict[tuple[str,str],dict]) -> list[Action]:
    out=[]
    for date in target_dates_for_symbol(symbol):
        e=evidence[(symbol,date)]
        t=normalize_profile(e['profile'])
        out.append(Action(
            symbol=symbol, ex_date=date,
            cash_per_share=t['cash_per_share'], stock_ratio=t['stock_ratio'], cap_ratio=t['capitalization_ratio'],
            rights_ratio=t['rights_ratio'], rights_price=t['rights_price'], source=e['source'],
        ))
    return out


def recalc_symbol(symbol: str, evidence, sina_index, sohu_index) -> dict:
    code,exch=symbol.split('.')
    prefix=f'{code}_{exch}'
    rec={'symbol':symbol,'status':None,'coverage_complete':False,'action_dates':[],
         'sina_factor_change_dates':[],'factor_validation':None,'events':[],'error':None,
         'formal_promotion':False,'validated_global_provenance_emitted':False}
    try:
        sina_path=unique_from_index(sina_index,prefix+'_sina_qfq.js')
        sohu_path=unique_from_index(sohu_index,prefix+'_sohu_raw_history.js')
        sina_raw=sina_path.read_bytes(); sohu_raw=sohu_path.read_bytes()
        factors=parse_sina_qfq(sina_raw); raw_rows=parse_sohu_history_bytes(sohu_raw)
        formal_rows=[r for r in raw_rows if FORMAL_BEG<=r['date']<=FORMAL_END]
        if not formal_rows: raise ValueError('no Formal RAW rows')
        actions=make_actions(symbol,evidence)
        action_dates=sorted(a.ex_date for a in actions)
        sina_dates=sina_factor_change_dates(factors,FORMAL_BEG,FORMAL_END)
        rec['action_dates']=action_dates; rec['sina_factor_change_dates']=sina_dates
        rec['coverage_complete']=action_dates==sina_dates==target_dates_for_symbol(symbol)
        rec['source_meta']={
            'sina_sha256':sha256_bytes(sina_raw),'sohu_sha256':sha256_bytes(sohu_raw),
            'sina_source':'corrected V4.81 source census run 34009079533',
            'sohu_source':'V4.81 nominal shard raw run 34009535349',
        }
        if not rec['coverage_complete']:
            rec['status']=classify_missing_event_recalc(False,None)
            return rec
        ratios={}
        for a in actions:
            pc=prev_close_before(raw_rows,a.ex_date); ratio=event_ratio(a,pc); ratios[a.ex_date]=ratio
            ev=evidence[(symbol,a.ex_date)]
            rec['events'].append({
                'ex_date':a.ex_date,'profile':ev['profile'],'source':ev['source'],'evidence_raw_sha256':ev['raw_sha256'],
                'cash_per_share':a.cash_per_share,'stock_ratio':a.stock_ratio,'capitalization_ratio':a.cap_ratio,
                'prev_actual_close':pc,'event_ratio':ratio,
            })
        expected={r['date']:expected_factor_for_date(r['date'],actions,ratios,FORMAL_END) for r in formal_rows}
        actual={r['date']:sina_normalized_for_date(factors,r['date'],FORMAL_END) for r in formal_rows}
        cmp=compare_factor_path(formal_rows,expected,actual,THRESHOLD_BP)
        rec['factor_validation']=cmp
        rec['status']=classify_missing_event_recalc(True,cmp['status'])
        return rec
    except Exception as e:
        rec['status']='BLOCKED_MISSING_EVENT_FACTOR_COMPARISON'
        rec['error']=f'{type(e).__name__}: {e}'
        return rec


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-review',required=True)
    ap.add_argument('--supplemental-dir',required=True)
    ap.add_argument('--f10-dir',required=True)
    ap.add_argument('--source-census',required=True)
    ap.add_argument('--nominal-shards',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()

    base_review=load_base_review(pathlib.Path(args.base_review))
    evidence=load_evidence(pathlib.Path(args.supplemental_dir),pathlib.Path(args.f10_dir))
    sina_index=build_basename_index(pathlib.Path(args.source_census),'_sina_qfq.js')
    sohu_index=build_basename_index(pathlib.Path(args.nominal_shards),'_sohu_raw_history.js')

    records=[recalc_symbol(s,evidence,sina_index,sohu_index) for s in TARGET_SYMBOLS]
    if len(records)!=7 or len({r['symbol'] for r in records})!=7:
        raise RuntimeError('missing-event recalc output is not exact 7 partition')
    counts=Counter(r['status'] for r in records)
    pass_n=counts.get('PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR',0)
    exact_n=counts.get('REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',0)
    blocked_n=7-pass_n-exact_n
    after={
        'PASS':BASE_COUNTS['PASS']+pass_n,
        'EXACT_TERM_REVIEW':BASE_COUNTS['EXACT_TERM_REVIEW']+exact_n,
        'MISSING_EVENT_REVIEW':BASE_COUNTS['MISSING_EVENT_REVIEW']-7 if blocked_n==0 else None,
        'NOT_APPLICABLE':BASE_COUNTS['NOT_APPLICABLE'],
    }
    after['REVIEW_TOTAL']=(after['EXACT_TERM_REVIEW']+after['MISSING_EVENT_REVIEW']) if after['MISSING_EVENT_REVIEW'] is not None else None
    report={
        'artifact':'MISSING_EVENT_FACTOR_RECALC_V481','version':'V4.81',
        'generated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'formal_window':[FORMAL_BEG,FORMAL_END],'threshold_bp':THRESHOLD_BP,
        'base_checkpoint':{'PASS':702,'EXACT_TERM_REVIEW':82,'MISSING_EVENT_REVIEW':60,'NOT_APPLICABLE':3,'REVIEW_TOTAL':142},
        'target_symbol_n':7,'target_event_date_n':12,'status_counts':dict(sorted(counts.items())),
        'resolved_pass_n':pass_n,'resolved_to_exact_review_n':exact_n,'blocked_n':blocked_n,
        'nominal_checkpoint_after_7':after,
        'formal_promotion':False,'validated_global_provenance_emitted':False,'formal_ready':False,'oos_metrics_allowed':False,
        'records':records,
    }
    out=pathlib.Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'MISSING_EVENT_FACTOR_RECALC_V481.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'MISSING_EVENT_FACTOR_RECALC_V481.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['symbol','status','coverage_complete','action_dates','sina_factor_change_dates','max_diff_bp','error'])
        w.writeheader()
        for r in records:
            fv=r.get('factor_validation') or {}
            w.writerow({'symbol':r['symbol'],'status':r['status'],'coverage_complete':r['coverage_complete'],
                        'action_dates':'|'.join(r['action_dates']),'sina_factor_change_dates':'|'.join(r['sina_factor_change_dates']),
                        'max_diff_bp':fv.get('max_diff_bp'),'error':r.get('error')})
    print(json.dumps({k:report[k] for k in ['status_counts','resolved_pass_n','resolved_to_exact_review_n','blocked_n','nominal_checkpoint_after_7']},ensure_ascii=False,indent=2))
    if blocked_n:
        raise SystemExit(f'fail-closed: {blocked_n} of 7 missing-event symbols remain blocked')

if __name__=='__main__': main()
