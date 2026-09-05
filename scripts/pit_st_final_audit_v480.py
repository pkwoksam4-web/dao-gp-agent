#!/usr/bin/env python3
import argparse,csv,json
from collections import defaultdict,Counter
from datetime import datetime, timezone
from pathlib import Path


def audit_symbol_lifecycle(symbol, ipo_date, out_date, rows, calendar_dates):
    ipo = str(ipo_date or '')
    out = str(out_date or '')
    rows = list(rows or [])
    cal = sorted(str(d) for d in calendar_dates)
    row_by_date = {str(r['date']): r for r in rows}

    required = [d for d in cal if (not ipo or d >= ipo) and (not out or d < out)]
    missing = [d for d in required if d not in row_by_date]

    pre_ipo_trading = [d for d, r in row_by_date.items() if ipo and d < ipo and str(r.get('tradestatus')) == '1']
    post_out_trading = [d for d, r in row_by_date.items() if out and d >= out and str(r.get('tradestatus')) == '1']
    outdate_bookkeeping = [d for d, r in row_by_date.items() if out and d == out and str(r.get('tradestatus')) == '0']

    base = {
        'symbol': symbol,
        'required_dates': required,
        'missing_required_dates': missing,
        'outdate_bookkeeping_rows': sorted(outdate_bookkeeping),
        'pre_ipo_trading_dates': sorted(pre_ipo_trading),
        'post_outdate_trading_dates': sorted(post_out_trading),
    }
    if pre_ipo_trading:
        return {**base, 'status': 'UNKNOWN_PRE_IPO_TRADING'}
    if post_out_trading:
        return {**base, 'status': 'UNKNOWN_POST_OUTDATE_TRADING'}
    if missing:
        return {**base, 'status': 'UNKNOWN_COVERAGE_GAP'}
    return {**base, 'status': 'PASS_LIFECYCLE_COVERAGE'}


def crosscheck_transitions(observed_by_symbol, evidence_rows):
    results=[]
    for e in evidence_rows:
        src=str(e.get('source_url') or '').strip()
        base={k:e.get(k) for k in ['symbol','effective_date','from_isST','to_isST','source_url']}
        if not src:
            results.append({**base,'status':'FAIL_MISSING_INDEPENDENT_SOURCE'})
            continue
        obs=observed_by_symbol.get(e.get('symbol'),[])
        match=next((t for t in obs if str(t.get('effective_observed_date'))==str(e.get('effective_date')) and str(t.get('from_isST'))==str(e.get('from_isST')) and str(t.get('to_isST'))==str(e.get('to_isST'))),None)
        if match is None:
            results.append({**base,'status':'FAIL_NO_EXACT_OBSERVED_TRANSITION'})
        else:
            results.append({**base,'status':'PASS_EXACT_TRANSITION','observed':match})
    matched=sum(r['status']=='PASS_EXACT_TRANSITION' for r in results)
    return {'evidence_n':len(evidence_rows),'matched_n':matched,'all_pass':matched==len(evidence_rows) and len(evidence_rows)>0,'results':results}


FORMAL_START='2020-06-01'
FORMAL_END='2026-04-17'
DELISTED_CONTROLS=['002359.SZ','600634.SH']


def gate_decision(m):
    checks={
        'scope_exact_847': m.get('scope_n')==847,
        'materialized_exact_847': m.get('materialized_symbol_n')==847,
        'no_unresolved_symbols': m.get('unresolved_symbol_n')==0,
        'lifecycle_exact_847': m.get('lifecycle_pass_n')==847,
        'calendar_exact_1426': m.get('calendar_n')==1426,
        'no_duplicate_daily_keys': m.get('duplicate_daily_keys')==0,
        'no_invalid_daily_rows': m.get('invalid_daily_rows')==0,
        'no_outside_calendar_rows': m.get('outside_calendar_rows')==0,
        'delisted_controls_pass': m.get('delisted_controls_pass') is True,
        'transition_crosscheck_all_pass': m.get('transition_crosscheck_all_pass') is True,
    }
    closed=all(checks.values())
    return {
        'pit_st_gate_closed': closed,
        'pit_st_status': 'CLOSED_V480' if closed else 'OPEN_V480_AUDIT_FAILED',
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'checks': checks,
    }


def read_calendar(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    dates=[str(r['trade_date']).strip() for r in rows]
    return dates


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--daily',required=True)
    ap.add_argument('--merged-audit',required=True)
    ap.add_argument('--calendar',required=True)
    ap.add_argument('--transition-evidence',required=True)
    ap.add_argument('--out-dir',required=True)
    args=ap.parse_args()
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)

    calendar=read_calendar(args.calendar)
    calendar_set=set(calendar)
    calendar_ok=(len(calendar)==1426 and len(calendar_set)==1426 and min(calendar)==FORMAL_START and max(calendar)==FORMAL_END)

    merged=json.load(open(args.merged_audit,encoding='utf-8'))
    audit_by_symbol={a['symbol']:a for a in merged['audits']}

    rows_by_symbol=defaultdict(list)
    seen=set(); duplicate_daily_keys=0; invalid_daily_rows=0; outside_calendar_rows=0
    with open(args.daily,encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            symbol=str(r.get('symbol','')).strip().upper(); date=str(r.get('date','')).strip()
            ts=str(r.get('tradestatus','')).strip(); st=str(r.get('isST','')).strip()
            key=(symbol,date)
            if key in seen: duplicate_daily_keys+=1
            else: seen.add(key)
            if ts not in {'0','1'} or st not in {'0','1'}: invalid_daily_rows+=1
            if date not in calendar_set: outside_calendar_rows+=1
            rows_by_symbol[symbol].append({'date':date,'tradestatus':ts,'isST':st})

    lifecycle=[]
    for symbol,a in sorted(audit_by_symbol.items()):
        basics=(a.get('basic') or {}).get('rows') or []
        if len(basics)!=1:
            lifecycle.append({'symbol':symbol,'status':'UNKNOWN_BASIC_LIFECYCLE_METADATA','missing_required_dates':[],'outdate_bookkeeping_rows':[],'pre_ipo_trading_dates':[],'post_outdate_trading_dates':[]})
            continue
        b=basics[0]
        lifecycle.append(audit_symbol_lifecycle(symbol,b.get('ipoDate',''),b.get('outDate',''),rows_by_symbol[symbol],calendar))

    lifecycle_counts=Counter(x['status'] for x in lifecycle)
    lifecycle_pass_n=lifecycle_counts.get('PASS_LIFECYCLE_COVERAGE',0)
    bookkeeping_outdate_n=sum(len(x.get('outdate_bookkeeping_rows',[])) for x in lifecycle)
    missing_required_n=sum(len(x.get('missing_required_dates',[])) for x in lifecycle)

    controls={}
    for symbol in DELISTED_CONTROLS:
        lr=next((x for x in lifecycle if x['symbol']==symbol),None)
        controls[symbol]={
            'lifecycle_status': lr.get('status') if lr else 'MISSING',
            'daily_rows': len(rows_by_symbol.get(symbol,[])),
            'pass': bool(lr and lr.get('status')=='PASS_LIFECYCLE_COVERAGE' and len(rows_by_symbol.get(symbol,[]))>0),
        }
    delisted_controls_pass=all(v['pass'] for v in controls.values())

    evidence_doc=json.load(open(args.transition_evidence,encoding='utf-8'))
    observed={s:a.get('transitions',[]) for s,a in audit_by_symbol.items()}
    transition=crosscheck_transitions(observed,evidence_doc['evidence'])
    transition['artifact']='PIT_ST_TRANSITION_CROSSCHECK_V480'
    transition['version']='V4.80'
    transition['generated_at_utc']=datetime.now(timezone.utc).isoformat()
    transition['sample_symbols']=sorted({e['symbol'] for e in evidence_doc['evidence']})
    transition['provider']='BaoStock observed transitions vs independent CNINFO company disclosures'
    (out/'PIT_ST_TRANSITION_CROSSCHECK_V480.json').write_text(json.dumps(transition,ensure_ascii=False,indent=2),encoding='utf-8')

    # Formal overlay includes only lifecycle-required dates: [ipoDate, outDate), never provider bookkeeping on outDate.
    lifecycle_by_symbol={x['symbol']:x for x in lifecycle}
    overlay_rows=0; overlay_st=0; overlay_not_st=0
    with (out/'PIT_ST_FORMAL_OVERLAY_V480.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['symbol','date','tradestatus','isST','pit_st_state','validation_status','provenance'])
        w.writeheader()
        for symbol in sorted(rows_by_symbol):
            required=set(lifecycle_by_symbol.get(symbol,{}).get('required_dates',[]))
            for r in sorted(rows_by_symbol[symbol], key=lambda x:x['date']):
                if r['date'] not in required: continue
                state='ST' if r['isST']=='1' else 'NOT_ST'
                w.writerow({'symbol':symbol,'date':r['date'],'tradestatus':r['tradestatus'],'isST':r['isST'],'pit_st_state':state,'validation_status':'VALIDATED_PIT_ST_V480','provenance':'BaoStock:query_history_k_data_plus|V480'})
                overlay_rows+=1; overlay_st+=(state=='ST'); overlay_not_st+=(state=='NOT_ST')

    metrics={
        'scope_n': merged.get('scope_n'),
        'materialized_symbol_n': merged.get('materialized_symbol_n'),
        'unresolved_symbol_n': merged.get('unresolved_symbol_n'),
        'calendar_n': len(calendar) if calendar_ok else -1,
        'duplicate_daily_keys': duplicate_daily_keys,
        'invalid_daily_rows': invalid_daily_rows,
        'outside_calendar_rows': outside_calendar_rows,
        'lifecycle_pass_n': lifecycle_pass_n,
        'delisted_controls_pass': delisted_controls_pass,
        'transition_crosscheck_all_pass': transition['all_pass'],
    }
    decision=gate_decision(metrics)

    lifecycle_report={
        'artifact':'PIT_ST_CALENDAR_LIFECYCLE_AUDIT_V480','version':'V4.80','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'formal_window':[FORMAL_START,FORMAL_END],
        'calendar_n':len(calendar),'calendar_unique_n':len(calendar_set),'calendar_bounds':[min(calendar),max(calendar)],'calendar_exact_ok':calendar_ok,
        'scope_n':merged.get('scope_n'),'materialized_symbol_n':merged.get('materialized_symbol_n'),'unresolved_symbol_n':merged.get('unresolved_symbol_n'),
        'daily_rows':sum(len(v) for v in rows_by_symbol.values()),'duplicate_daily_keys':duplicate_daily_keys,'invalid_daily_rows':invalid_daily_rows,'outside_calendar_rows':outside_calendar_rows,
        'lifecycle_rule':'Formal eligibility requires official open dates d with d >= ipoDate and (outDate empty or d < outDate). Provider rows exactly on outDate are permitted only when tradestatus=0 and are excluded from Formal overlay.',
        'lifecycle_status_counts':dict(lifecycle_counts),'lifecycle_pass_n':lifecycle_pass_n,'missing_required_dates_total':missing_required_n,'outdate_bookkeeping_rows_total':bookkeeping_outdate_n,
        'delisted_controls':controls,'formal_overlay_rows':overlay_rows,'formal_overlay_st_rows':overlay_st,'formal_overlay_not_st_rows':overlay_not_st,
        'all_pass': decision['pit_st_gate_closed'],
        'fail_closed_rule':'UNKNOWN/FAILED never defaults to NOT_ST; no current-name inference is used for historical dates.',
        'symbols':[{'symbol':x['symbol'],'status':x['status'],'missing_required_dates':x.get('missing_required_dates',[]),'outdate_bookkeeping_rows':x.get('outdate_bookkeeping_rows',[]),'pre_ipo_trading_dates':x.get('pre_ipo_trading_dates',[]),'post_outdate_trading_dates':x.get('post_outdate_trading_dates',[])} for x in lifecycle],
    }
    (out/'PIT_ST_CALENDAR_LIFECYCLE_AUDIT_V480.json').write_text(json.dumps(lifecycle_report,ensure_ascii=False,indent=2),encoding='utf-8')

    checkpoint={
        'artifact':'FORMAL_GATE_CHECKPOINT_V480_FINAL','version':'V4.80','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'formal_ready':False,'oos_metrics_allowed':False,
        'price_history':{'status':'CLOSED_V465','p0_remaining':0},
        'pit_st':{
            'status':decision['pit_st_status'],'gate_closed':decision['pit_st_gate_closed'],'scope_n':metrics['scope_n'],'materialized_symbol_n':metrics['materialized_symbol_n'],'unresolved_symbol_n':metrics['unresolved_symbol_n'],
            'calendar_lifecycle':'PASS_847_OF_847' if lifecycle_pass_n==847 else f'FAIL_{lifecycle_pass_n}_OF_847',
            'transition_crosscheck':f"PASS_{transition['matched_n']}_OF_{transition['evidence_n']}" if transition['all_pass'] else f"FAIL_{transition['matched_n']}_OF_{transition['evidence_n']}",
            'delisted_controls':controls,'formal_overlay_rows':overlay_rows,
            'source':'BaoStock query_history_k_data_plus(date,code,tradestatus,isST)',
            'independent_evidence':'CNINFO company disclosures for sampled ST transitions',
            'rule':'UNKNOWN/FAILED never defaults to NOT_ST; no current-name inference.'
        },
        'adjustment_provenance':{'sample50':'CLOSED_V479','global_847':'OPEN'},
        'liquidity':{'threshold_cny':80000000,'status':'FROZEN_V370_WAITING_FOR_GLOBAL_ADJUSTMENT_PROVENANCE'},
        'locked_rule':'Formal OOS remains OFF until global 847 adjustment provenance closes and downstream full-panel re-audit passes.',
        'gate_checks':decision['checks'],
    }
    (out/'FORMAL_GATE_CHECKPOINT_V480_FINAL.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2),encoding='utf-8')

    print(json.dumps({
        'pit_st_gate_closed':decision['pit_st_gate_closed'],'lifecycle_pass_n':lifecycle_pass_n,'missing_required_dates_total':missing_required_n,
        'outdate_bookkeeping_rows_total':bookkeeping_outdate_n,'transition_matched_n':transition['matched_n'],'transition_evidence_n':transition['evidence_n'],
        'delisted_controls_pass':delisted_controls_pass,'overlay_rows':overlay_rows,'duplicate_daily_keys':duplicate_daily_keys,'invalid_daily_rows':invalid_daily_rows,'outside_calendar_rows':outside_calendar_rows,
        'formal_ready':False,'oos_metrics_allowed':False
    },ensure_ascii=False,indent=2))
    if not decision['pit_st_gate_closed']:
        raise SystemExit(2)

if __name__=='__main__': main()
