from __future__ import annotations

from sample50_validate import Action, merge_actions
from missing_event_terms_v481 import parse_impl_plan_profile
from missing_event_factor_recalc_v481 import extract_f10_target_profile


def action_from_base_event(symbol: str, ev: dict) -> Action:
    if not isinstance(ev, dict):
        raise ValueError('base event must be an object')
    ex_date=str(ev.get('ex_date') or '')[:10]
    if len(ex_date)!=10:
        raise ValueError('base event missing ex_date')
    return Action(
        symbol=str(symbol).upper(),
        ex_date=ex_date,
        cash_per_share=float(ev.get('cash_per_share_nominal') or 0.0),
        stock_ratio=float(ev.get('stock_ratio') or 0.0),
        cap_ratio=float(ev.get('capitalization_ratio') or 0.0),
        rights_ratio=float(ev.get('rights_ratio') or 0.0),
        rights_price=(None if ev.get('rights_price') in (None,'') else float(ev.get('rights_price'))),
        source=str(ev.get('source') or 'GLOBAL_LEDGER_BASE_EVENT'),
    )


def _target_map(f10_record: dict) -> dict[str,dict]:
    targets={}
    for target in f10_record.get('targets') or []:
        if not isinstance(target,dict):
            continue
        date=str(target.get('date') or '')[:10]
        if not date:
            continue
        if date in targets:
            raise ValueError(f'duplicate F10 target date {date}')
        targets[date]=target
    return targets


def build_combined_actions(symbol: str, base_record: dict, f10_record: dict) -> tuple[list[Action],dict]:
    symbol=str(symbol).upper()
    if str(base_record.get('symbol') or '').upper()!=symbol:
        raise ValueError('base record symbol mismatch')
    if str(f10_record.get('symbol') or '').upper()!=symbol:
        raise ValueError('F10 record symbol mismatch')

    missing_dates=sorted(set(base_record.get('missing_in_ledger') or []))
    if not missing_dates:
        raise ValueError(f'{symbol} has no missing event dates')

    targets=_target_map(f10_record)
    if set(targets)!=set(missing_dates):
        raise ValueError(
            f'{symbol} F10 target partition mismatch expected={missing_dates} actual={sorted(targets)}'
        )

    base_actions=[action_from_base_event(symbol,ev) for ev in (base_record.get('events') or [])]
    new_actions=[]
    new_profiles={}
    for date in missing_dates:
        target=targets[date]
        profile=extract_f10_target_profile(target)
        terms=parse_impl_plan_profile(profile)
        new_profiles[date]=profile
        new_actions.append(Action(
            symbol=symbol,
            ex_date=date,
            cash_per_share=terms['cash_per_share'],
            stock_ratio=terms['stock_ratio'],
            cap_ratio=terms['capitalization_ratio'],
            rights_ratio=terms['rights_ratio'],
            rights_price=terms['rights_price'],
            source='EASTMONEY_F10_PAGEAJAX_IMPLEMENTED',
        ))

    actions=merge_actions(base_actions+new_actions)
    combined_dates=sorted(a.ex_date for a in actions)
    sina_dates=sorted(set(base_record.get('sina_event_dates') or []))
    coverage_complete=(combined_dates==sina_dates)
    evidence={
        'coverage_complete':coverage_complete,
        'new_profiles':new_profiles,
        'base_event_dates':sorted(a.ex_date for a in base_actions),
        'new_event_dates':sorted(a.ex_date for a in new_actions),
        'combined_event_dates':combined_dates,
        'sina_event_dates':sina_dates,
    }
    return actions,evidence
