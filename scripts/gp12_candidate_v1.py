from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import statistics
from zoneinfo import ZoneInfo


STRATEGY_ID = 'GP12_REBUILD_CANDIDATE_V1'
FORMAL_END = dt.date(2026, 4, 17)
PROPOSAL_STATUS = 'UNAPPROVED'
SUPPORTED_PARAMETERS_SHA256 = '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204'
SUPPORTED_FACTORS_SHA256 = 'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e'
SHANGHAI = ZoneInfo('Asia/Shanghai')

SNAPSHOT_KEYS = {
    'strategy_id', 'symbol', 'sector_id', 'as_of', 'calendar', 'daily',
    'status', 'intraday_15m', 'intraday_60m', 'source_ids',
}
DAILY_KEYS = {
    'date', 'known_at', 'close', 'market_close', 'sector_close',
    'amount_cny', 'turnover_ratio', 'main_net_flow_cny',
    'market_breadth_ratio', 'sector_breadth_ratio',
}
STATUS_KEYS = {'known_at', 'is_st', 'tradable', 'upper_limit'}
BAR_KEYS = {'close', 'closed_at', 'known_at'}
SOURCE_KEYS = {
    'market_calendar', 'stock_adjusted_close', 'market_adjusted_close',
    'sector_adjusted_close', 'amount_turnover', 'main_net_flow',
    'market_breadth', 'sector_breadth', 'status', 'intraday_15m',
    'intraday_60m',
}
POSITION_KEYS = {
    'strategy_id', 'symbol', 'entry_close', 'current_close',
    'market_sessions_held',
}
LABEL_KEYS = {
    'symbol', 'signal_at', 'label_end_at', 'label_known_at',
    'label_source_id', 'horizon', 'score', 'outcome',
}
FACTOR_IDS = tuple(f'F{i}' for i in range(1, 13))
RAW_PANEL_FIELDS = frozenset(
    {'symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'source'})
RAW_PANEL_UNREPRESENTED_FAMILIES = (
    'stock_adjusted_close', 'market_adjusted_close', 'sector_adjusted_close',
    'amount_turnover', 'main_net_flow', 'market_breadth', 'sector_breadth',
    'intraday_15m', 'intraday_60m',
)
FEATURE_FAMILY_FIELDS = {
    'market_calendar': ('calendar',),
    'stock_adjusted_close': ('daily.close',),
    'market_adjusted_close': ('daily.market_close',),
    'sector_adjusted_close': ('daily.sector_close',),
    'amount_turnover': ('daily.amount_cny', 'daily.turnover_ratio'),
    'main_net_flow': ('daily.main_net_flow_cny',),
    'market_breadth': ('daily.market_breadth_ratio',),
    'sector_breadth': ('daily.sector_breadth_ratio',),
    'status': ('status.is_st', 'status.tradable', 'status.upper_limit'),
    'intraday_15m': ('intraday_15m',),
    'intraday_60m': ('intraday_60m',),
}


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _load_json(path: pathlib.Path | str) -> dict:
    try:
        with pathlib.Path(path).open(encoding='utf-8') as handle:
            value = json.load(
                handle,
                object_pairs_hook=_strict_object,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    ValueError(f'nonfinite JSON number: {token}')
                ),
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f'invalid JSON contract: {path}') from exc
    if not isinstance(value, dict):
        raise ValueError('JSON contract must be an object')
    return value


def _validate_parameters(parameters: object) -> str:
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be an object')
    try:
        digest = canonical_json_sha256(parameters)
    except (TypeError, ValueError) as exc:
        raise ValueError('parameters are not canonical finite JSON') from exc
    if digest != SUPPORTED_PARAMETERS_SHA256:
        raise ValueError('unsupported or modified parameter contract')
    weights = parameters['factor_weights_percent']
    if set(weights) != set(FACTOR_IDS) or sum(weights.values()) != 100:
        raise ValueError('invalid factor weights')
    return digest


def _require_exact_keys(value: object, expected: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f'{label} schema mismatch')
    return value


def _number(value: object, label: str, *, positive: bool = False,
            minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be numeric and not boolean')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f'{label} must be finite')
    if positive and result <= 0:
        raise ValueError(f'{label} must be positive')
    if minimum is not None and result < minimum:
        raise ValueError(f'{label} below minimum')
    if maximum is not None and result > maximum:
        raise ValueError(f'{label} above maximum')
    return result


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{label} must be an integer >= {minimum}')
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonempty string')
    return value


def _timestamp(value: object, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError(f'{label} must be an ISO timestamp')
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{label} must be an ISO timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f'{label} must be timezone-aware')
    return parsed


def _date(value: object, label: str) -> dt.date:
    if not isinstance(value, str):
        raise ValueError(f'{label} must be an ISO date')
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{label} must be an ISO date') from exc
    if value != parsed.isoformat():
        raise ValueError(f'{label} must use canonical ISO date format')
    return parsed


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _clean(value: float) -> float:
    if abs(value) < 5e-15:
        return 0.0
    if abs(value - 1.0) < 5e-15:
        return 1.0
    if abs(value + 1.0) < 5e-15:
        return -1.0
    return round(value, 12)


def _return(values: list[float], window: int) -> float:
    return values[-1] / values[-1 - window] - 1.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def raw_panel_gap_report(fields: object) -> dict:
    """Describe what the validated V4.82 RAW schema cannot provide by itself."""
    if not isinstance(fields, (set, frozenset, list, tuple)):
        observed = []
    else:
        observed = sorted({field for field in fields if isinstance(field, str)})
    return {
        'observed_fields': observed,
        'raw_schema_complete': set(observed) >= RAW_PANEL_FIELDS,
        'missing_raw_schema_fields': sorted(RAW_PANEL_FIELDS - set(observed)),
        'candidate_families_unrepresented_by_raw_panel': list(
            RAW_PANEL_UNREPRESENTED_FAMILIES),
        'warning': (
            'raw close/amount/volume fields are not substitutes for adjusted '
            'close, turnover, flow, breadth, or intraday families'),
    }


def _log_slope_r_squared(values: list[float]) -> tuple[float, float]:
    logs = [math.log(value) for value in values]
    count = len(logs)
    x_mean = (count - 1) / 2.0
    y_mean = _mean(logs)
    ss_x = sum((index - x_mean) ** 2 for index in range(count))
    ss_y = sum((value - y_mean) ** 2 for value in logs)
    if ss_y == 0.0:
        return 0.0, 0.0
    covariance = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(logs)
    )
    slope = covariance / ss_x
    fitted_ss = slope * slope * ss_x
    return slope, min(1.0, max(0.0, fitted_ss / ss_y))


def _validate_bar_series(value: object, label: str, expected_minutes: int,
                         as_of: dt.datetime, snapshot_date: dt.date) -> list[float]:
    if not isinstance(value, list) or len(value) != 5:
        raise ValueError(f'{label} must contain exactly five bars')
    closes = []
    prior_closed = None
    for index, raw in enumerate(value):
        row = _require_exact_keys(raw, BAR_KEYS, f'{label}[{index}]')
        close = _number(row['close'], f'{label}[{index}].close', positive=True)
        closed = _timestamp(row['closed_at'], f'{label}[{index}].closed_at')
        known = _timestamp(row['known_at'], f'{label}[{index}].known_at')
        closed_local = closed.astimezone(SHANGHAI)
        if closed_local.minute % expected_minutes != 0 or closed_local.second != 0:
            raise ValueError(f'{label} close is not on its timeframe boundary')
        if prior_closed is not None and closed <= prior_closed:
            raise ValueError(f'{label} times must strictly increase')
        if not (closed <= known <= as_of):
            raise ValueError(f'{label} availability is outside the allowed range')
        prior_closed = closed
        closes.append(close)
    if prior_closed.astimezone(SHANGHAI).date() != snapshot_date:
        raise ValueError(f'{label} is stale')
    return closes


def _validated_snapshot(snapshot: object) -> dict:
    value = _require_exact_keys(snapshot, SNAPSHOT_KEYS, 'snapshot')
    if value['strategy_id'] != STRATEGY_ID:
        raise ValueError('wrong strategy ID')
    symbol = _text(value['symbol'], 'symbol')
    sector_id = _text(value['sector_id'], 'sector_id')
    as_of = _timestamp(value['as_of'], 'as_of')
    snapshot_date = as_of.astimezone(SHANGHAI).date()
    if snapshot_date > FORMAL_END:
        raise ValueError('snapshot is outside the Formal period')

    if not isinstance(value['calendar'], list) or len(value['calendar']) != 121:
        raise ValueError('calendar must contain exactly 121 entries')
    calendar = [_date(item, 'calendar date') for item in value['calendar']]
    if any(right <= left for left, right in zip(calendar, calendar[1:])):
        raise ValueError('calendar dates must strictly increase without duplicates')
    if calendar[-1] != snapshot_date:
        raise ValueError('calendar must end on the local snapshot date')
    if any(date > FORMAL_END for date in calendar):
        raise ValueError('calendar contains a date outside the Formal period')

    if not isinstance(value['daily'], list) or len(value['daily']) != 121:
        raise ValueError('daily history must contain exactly 121 rows')
    fields = {
        'close': [], 'market_close': [], 'sector_close': [], 'amount_cny': [],
        'turnover_ratio': [], 'main_net_flow_cny': [],
        'market_breadth_ratio': [], 'sector_breadth_ratio': [],
    }
    for index, raw in enumerate(value['daily']):
        row = _require_exact_keys(raw, DAILY_KEYS, f'daily[{index}]')
        row_date = _date(row['date'], f'daily[{index}].date')
        if row_date != calendar[index]:
            raise ValueError('daily rows and calendar are not one-to-one aligned')
        known = _timestamp(row['known_at'], f'daily[{index}].known_at')
        local_close = dt.datetime.combine(row_date, dt.time(15, 0), SHANGHAI)
        if known < local_close or known > as_of:
            raise ValueError('daily availability is outside the allowed range')
        for name in ('close', 'market_close', 'sector_close', 'amount_cny',
                     'turnover_ratio'):
            fields[name].append(_number(
                row[name], f'daily[{index}].{name}', positive=True))
        flow = _number(row['main_net_flow_cny'], f'daily[{index}].main_net_flow_cny')
        if abs(flow) > fields['amount_cny'][-1]:
            raise ValueError('absolute main flow cannot exceed amount')
        fields['main_net_flow_cny'].append(flow)
        for name in ('market_breadth_ratio', 'sector_breadth_ratio'):
            fields[name].append(_number(
                row[name], f'daily[{index}].{name}', minimum=0.0, maximum=1.0))

    status = _require_exact_keys(value['status'], STATUS_KEYS, 'status')
    status_known = _timestamp(status['known_at'], 'status.known_at')
    if status_known > as_of:
        raise ValueError('status was not known by as_of')
    for name in ('is_st', 'tradable', 'upper_limit'):
        if type(status[name]) is not bool:
            raise ValueError(f'status.{name} must be a known strict boolean')

    sources = _require_exact_keys(value['source_ids'], SOURCE_KEYS, 'source_ids')
    for name, source_id in sources.items():
        _text(source_id, f'source_ids.{name}')

    closes15 = _validate_bar_series(
        value['intraday_15m'], 'intraday_15m', 15, as_of, snapshot_date)
    closes60 = _validate_bar_series(
        value['intraday_60m'], 'intraday_60m', 60, as_of, snapshot_date)
    return {
        'symbol': symbol,
        'sector_id': sector_id,
        'as_of': as_of,
        'snapshot_date': snapshot_date,
        'fields': fields,
        'status': status,
        'source_ids': dict(sources),
        'intraday_15m': closes15,
        'intraday_60m': closes60,
    }


def score_snapshot(snapshot: object, parameters: object) -> dict:
    """Validate and score one Formal-only point-in-time proposal snapshot."""
    parameter_sha256 = _validate_parameters(parameters)
    data = _validated_snapshot(snapshot)
    fields = data['fields']
    stock = fields['close']
    market = fields['market_close']
    sector = fields['sector_close']

    raw = {}
    raw['F1'] = _mean([_return(market, 5) / 0.03, _return(market, 20) / 0.10])
    raw['F2'] = 2.0 * _mean(fields['market_breadth_ratio'][-5:]) - 1.0
    raw['F3'] = _mean([
        (_return(sector, window) - _return(market, window)) / scale
        for window, scale in ((5, 0.03), (10, 0.05), (20, 0.10))
    ])
    sector_slope, sector_r2 = _log_slope_r_squared(sector[-20:])
    raw['F4'] = sector_slope * 20.0 * sector_r2 / 0.10
    raw['F5'] = 2.0 * _mean(fields['sector_breadth_ratio'][-5:]) - 1.0
    locations = []
    for window in (20, 60, 120):
        values = stock[-window:]
        low, high = min(values), max(values)
        locations.append(0.5 if high == low else (stock[-1] - low) / (high - low))
    raw['F6'] = 1.0 - 2.0 * _mean(locations)
    raw['F7'] = _mean([
        _return(stock, window) / scale
        for window, scale in ((5, 0.03), (10, 0.05), (20, 0.10), (60, 0.20))
    ])
    stock_slope, stock_r2 = _log_slope_r_squared(stock[-60:])
    raw['F8'] = stock_slope * 60.0 * stock_r2 / 0.20
    path = sum(abs(right - left) for left, right in zip(stock[-21:-1], stock[-20:]))
    raw['F9'] = 0.0 if path == 0.0 else (stock[-1] - stock[-21]) / path
    last60 = stock[-60:]
    peak = max(last60)
    latest_peak_index = len(last60) - 1 - list(reversed(last60)).index(peak)
    trough = min(last60[latest_peak_index:])
    raw['F10'] = 0.0 if peak == trough else 2.0 * (stock[-1] - trough) / (peak - trough) - 1.0
    price_efficiency = _return(stock, 5) / sum(fields['turnover_ratio'][-5:])
    flows = fields['main_net_flow_cny'][-5:]
    intensities = [
        _clip(flow / amount / 0.20) * 0.20
        for flow, amount in zip(flows, fields['amount_cny'][-5:])
    ]
    net_mean = _mean(intensities)
    if net_mean == 0.0:
        persistence = 0.0
    else:
        sign = 1 if net_mean > 0 else -1
        persistence = sum(1 for flow in flows if flow * sign > 0.0) / 5.0
    raw['F11'] = _mean([price_efficiency / 0.10, net_mean / 0.05 * persistence])
    raw['F12'] = _mean([
        (data['intraday_15m'][-1] / data['intraday_15m'][-5] - 1.0) / 0.02,
        (data['intraday_60m'][-1] / data['intraday_60m'][-5] - 1.0) / 0.04,
    ])

    raw_out = {factor: _clean(raw[factor]) for factor in FACTOR_IDS}
    factors = {
        factor: _clean(50.0 * (1.0 + _clip(raw[factor])))
        for factor in FACTOR_IDS
    }
    weights = parameters['factor_weights_percent']
    total = _clean(sum(weights[factor] * factors[factor] for factor in FACTOR_IDS) / 100.0)
    layers = {}
    for name, factor_ids in parameters['factor_layers'].items():
        layer_weight = sum(weights[factor] for factor in factor_ids)
        layers[name] = _clean(
            sum(weights[factor] * factors[factor] for factor in factor_ids) / layer_weight)

    liquidity = statistics.median(fields['amount_cny'][-20:])
    momentum20 = _return(stock, 20)
    exclusions = []
    if data['status']['is_st']:
        exclusions.append('IS_ST')
    if not data['status']['tradable']:
        exclusions.append('NONTRADABLE')
    if data['status']['upper_limit']:
        exclusions.append('UPPER_LIMIT')
    if liquidity < parameters['liquidity_rule']['minimum_amount_cny']:
        exclusions.append('LOW_LIQUIDITY')
    if momentum20 <= 0.0:
        exclusions.append('NONPOSITIVE_20D_MOMENTUM')

    return {
        'strategy_id': STRATEGY_ID,
        'proposal_status': PROPOSAL_STATUS,
        'symbol': data['symbol'],
        'sector_id': data['sector_id'],
        'snapshot_date': data['snapshot_date'].isoformat(),
        'as_of': snapshot['as_of'],
        'parameter_sha256': parameter_sha256,
        'score': total,
        'factors': factors,
        'raw_factors': raw_out,
        'layers': layers,
        'trend_diagnostics': {
            'sector_20d_r_squared': _clean(sector_r2),
            'stock_60d_r_squared': _clean(stock_r2),
        },
        'momentum_20d': _clean(momentum20),
        'liquidity_20d_median_cny': _clean(liquidity),
        'eligibility_exclusions': exclusions,
        'source_ids': data['source_ids'],
        'source_ids_verified': False,
        'real_feature_inputs_validated': False,
    }


def feature_input_readiness(snapshot: object, raw_panel_fields: object = None) -> dict:
    """Report structural feature gaps without asserting source truth.

    This is intentionally weaker than ``score_snapshot``: it is a diagnostic
    for wiring the real V4.82 inputs and never turns caller-declared source IDs
    into substantive provenance verification.
    """
    missing_families = set()
    missing_fields = set()
    reasons = []
    raw_panel_gap = (
        raw_panel_gap_report(raw_panel_fields)
        if raw_panel_fields is not None else None)
    if not isinstance(snapshot, dict):
        return {
            'structural_input_contract_complete': False,
            'missing_families': sorted(FEATURE_FAMILY_FIELDS),
            'missing_fields': ['snapshot'],
            'source_ids_present': False,
            'source_ids_substantively_verified': False,
            'real_feature_inputs_validated': False,
            'reasons': ['snapshot must be an object'],
            'raw_panel_gap': raw_panel_gap,
        }

    required_top_level = {'calendar', 'daily', 'status', 'intraday_15m',
                          'intraday_60m', 'source_ids'}
    missing_top_level = sorted(required_top_level - set(snapshot))
    if missing_top_level:
        reasons.append('missing top-level contract fields')
        missing_fields.update(missing_top_level)
        if 'calendar' in missing_top_level:
            missing_families.add('market_calendar')

    daily = snapshot.get('daily')
    if not isinstance(daily, list) or not daily:
        reasons.append('daily must be a non-empty list')
        for family in ('stock_adjusted_close', 'market_adjusted_close',
                       'sector_adjusted_close', 'amount_turnover',
                       'main_net_flow', 'market_breadth', 'sector_breadth'):
            missing_families.add(family)
    else:
        for family, paths in FEATURE_FAMILY_FIELDS.items():
            for path in paths:
                if (path.startswith('daily.') and any(
                        not isinstance(row, dict) or path[6:] not in row
                        for row in daily)):
                    missing_families.add(family)
                    missing_fields.add(path)

    status = snapshot.get('status')
    if not isinstance(status, dict):
        missing_families.add('status')
        missing_fields.add('status')
    else:
        for key in ('is_st', 'tradable', 'upper_limit'):
            if key not in status:
                missing_families.add('status')
                missing_fields.add(f'status.{key}')

    for family in ('intraday_15m', 'intraday_60m'):
        bars = snapshot.get(family)
        if not isinstance(bars, list) or len(bars) != 5:
            missing_families.add(family)
            missing_fields.add(family)

    source_ids = snapshot.get('source_ids')
    source_ids_present = isinstance(source_ids, dict) and all(
        isinstance(source_ids.get(family), str) and source_ids[family].strip()
        for family in FEATURE_FAMILY_FIELDS)
    if not source_ids_present:
        reasons.append('source_ids are missing or incomplete')

    if missing_families:
        reasons.append('one or more required feature families are structurally absent')
    return {
        'structural_input_contract_complete': not missing_families and not missing_top_level,
        'missing_families': sorted(missing_families),
        'missing_fields': sorted(missing_fields),
        'source_ids_present': source_ids_present,
        'source_ids_substantively_verified': False,
        'real_feature_inputs_validated': False,
        'reasons': sorted(set(reasons)),
        'raw_panel_gap': raw_panel_gap,
    }


def rank_candidates(scores: object, parameters: object) -> list[dict]:
    """Rank score bundles for a fresh paper portfolio and propose weights."""
    parameter_sha256 = _validate_parameters(parameters)
    if not isinstance(scores, list):
        raise ValueError('scores must be a list')
    dates = set()
    symbols = set()
    eligible = []
    required = {
        'strategy_id', 'proposal_status', 'symbol', 'sector_id', 'snapshot_date',
        'parameter_sha256', 'score', 'eligibility_exclusions',
    }
    for index, row in enumerate(scores):
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError(f'score bundle {index} schema mismatch')
        if row['strategy_id'] != STRATEGY_ID or row['proposal_status'] != PROPOSAL_STATUS:
            raise ValueError('score bundle identity mismatch')
        if row['parameter_sha256'] != parameter_sha256:
            raise ValueError('score bundle parameter mismatch')
        symbol = _text(row['symbol'], 'score symbol')
        _text(row['sector_id'], 'score sector_id')
        _date(row['snapshot_date'], 'score snapshot_date')
        score = _number(row['score'], 'score', minimum=0.0, maximum=100.0)
        if symbol in symbols:
            raise ValueError('duplicate score symbol')
        symbols.add(symbol)
        dates.add(row['snapshot_date'])
        if not isinstance(row['eligibility_exclusions'], list) or any(
                not isinstance(item, str) for item in row['eligibility_exclusions']):
            raise ValueError('invalid eligibility exclusions')
        if not row['eligibility_exclusions'] and score >= parameters['policy']['entry_score_min']:
            eligible.append(row)
    if len(dates) > 1:
        raise ValueError('mixed snapshot dates')

    eligible.sort(key=lambda item: (-float(item['score']), item['symbol']))
    chosen = eligible[:parameters['policy']['top_n']]
    sector_allocations = {}
    total_allocation = 0.0
    result = []
    policy = parameters['policy']
    risk_weight = policy['per_name_capital_risk'] / policy['adverse_price_move_threshold']
    for rank, row in enumerate(chosen, 1):
        sector = row['sector_id']
        sector_remaining = max(
            0.0, policy['per_sector_max_weight'] - sector_allocations.get(sector, 0.0))
        total_remaining = max(0.0, 1.0 - total_allocation)
        weight = _clean(min(
            policy['per_symbol_max_weight'], risk_weight,
            sector_remaining, total_remaining,
        ))
        sector_allocations[sector] = sector_allocations.get(sector, 0.0) + weight
        total_allocation += weight
        ranked = dict(row)
        ranked['rank'] = rank
        ranked['research_weight'] = weight
        ranked['portfolio_context'] = 'FRESH_PAPER_PORTFOLIO'
        result.append(ranked)
    return result


def exit_reasons(position: object, score: object, parameters: object) -> list[str]:
    """Return proposed review reasons; this function never sends orders."""
    _validate_parameters(parameters)
    value = _require_exact_keys(position, POSITION_KEYS, 'position')
    if value['strategy_id'] != STRATEGY_ID:
        raise ValueError('position strategy ID mismatch')
    _text(value['symbol'], 'position symbol')
    entry = _number(value['entry_close'], 'entry_close', positive=True)
    current = _number(value['current_close'], 'current_close', positive=True)
    sessions = _integer(value['market_sessions_held'], 'market_sessions_held')
    current_score = _number(score, 'score', minimum=0.0, maximum=100.0)
    policy = parameters['policy']
    reasons = []
    if current_score < policy['exit_score_below']:
        reasons.append('SCORE_BELOW_EXIT')
    # Compare in price space so the exact 8% boundary is not lost to binary
    # floating-point rounding (100 -> 92 is exactly the configured threshold).
    if current <= entry * (1.0 - policy['adverse_price_move_threshold']):
        reasons.append('ADVERSE_MOVE_THRESHOLD')
    if sessions >= policy['max_holding_market_sessions']:
        reasons.append('MAX_HOLDING_SESSIONS')
    return reasons


def probability_lookup(rows: object, query_score: object, horizon: object,
                       as_of: object) -> dict:
    """Map a score decile to past-only labelled Formal frequencies."""
    score = _number(query_score, 'query_score', minimum=0.0, maximum=100.0)
    query_horizon = _integer(horizon, 'horizon', minimum=1)
    if query_horizon not in (1, 2, 3):
        raise ValueError('unsupported horizon')
    cutoff = _timestamp(as_of, 'as_of')
    if cutoff.astimezone(SHANGHAI).date() > FORMAL_END:
        raise ValueError('probability as_of is outside the Formal period')
    if not isinstance(rows, list):
        raise ValueError('rows must be a list')
    seen = set()
    validated = []
    for index, raw in enumerate(rows):
        row = _require_exact_keys(raw, LABEL_KEYS, f'label row {index}')
        symbol = _text(row['symbol'], 'label symbol')
        signal = _timestamp(row['signal_at'], 'signal_at')
        label_end = _timestamp(row['label_end_at'], 'label_end_at')
        label_known = _timestamp(row['label_known_at'], 'label_known_at')
        source_id = _text(row['label_source_id'], 'label_source_id')
        row_horizon = _integer(row['horizon'], 'label horizon', minimum=1)
        if row_horizon not in (1, 2, 3):
            raise ValueError('unsupported label horizon')
        row_score = _number(row['score'], 'label score', minimum=0.0, maximum=100.0)
        if row['outcome'] not in ('UP', 'DOWN', 'FLAT'):
            raise ValueError('invalid outcome')
        if not (signal < label_end <= label_known <= cutoff):
            raise ValueError('label timing violates past-only availability')
        if (signal.astimezone(SHANGHAI).date() > FORMAL_END or
                label_end.astimezone(SHANGHAI).date() > FORMAL_END or
                label_known.astimezone(SHANGHAI).date() > FORMAL_END):
            raise ValueError('label row is outside the Formal period')
        duplicate_key = (symbol, signal.isoformat(), row_horizon)
        if duplicate_key in seen:
            raise ValueError('duplicate symbol/signal/horizon label')
        seen.add(duplicate_key)
        validated.append({
            'horizon': row_horizon,
            'decile': min(9, int(row_score / 10.0)),
            'outcome': row['outcome'],
            'label_known_at': label_known,
            'label_source_id': source_id,
        })

    decile = min(9, int(score / 10.0))
    matching = [
        row for row in validated
        if row['horizon'] == query_horizon and row['decile'] == decile
    ]
    count = len(matching)
    probabilities = None
    if count >= 30:
        counts = {outcome: 0 for outcome in ('UP', 'DOWN', 'FLAT')}
        for row in matching:
            counts[row['outcome']] += 1
        probabilities = {
            outcome: (counts[outcome] + 1) / (count + 3)
            for outcome in ('UP', 'DOWN', 'FLAT')
        }
    return {
        'strategy_id': STRATEGY_ID,
        'proposal_status': PROPOSAL_STATUS,
        'as_of': as_of,
        'formal_cutoff': FORMAL_END.isoformat(),
        'horizon': query_horizon,
        'score_decile': decile,
        'sample_count': count,
        'available': probabilities is not None,
        'probabilities': probabilities,
        'calibration_cutoff': (
            max(row['label_known_at'] for row in matching).isoformat()
            if matching else None
        ),
        'label_source_boundary': sorted({row['label_source_id'] for row in matching}),
        'label_definition': (
            'Close-to-close signed return at T+h market-calendar trading sessions; '
            'suspended or missing target close excluded.'
        ),
        'production_calibration_claimed': False,
    }


def review_package(parameters_path: pathlib.Path | str,
                   factors_path: pathlib.Path | str) -> dict:
    """Review exact candidate contracts and hash their actual representations."""
    blockers = []
    parameters = None
    factors = None
    try:
        parameters = _load_json(parameters_path)
        _validate_parameters(parameters)
    except ValueError:
        blockers.append('PARAMETER_CONTRACT_INVALID')
    try:
        factors = _load_json(factors_path)
        if canonical_json_sha256(factors) != SUPPORTED_FACTORS_SHA256:
            raise ValueError('unsupported or modified factor contract')
        if (factors.get('strategy_id') != STRATEGY_ID or
                factors.get('formula_set_id') != 'GP12_FIXED_FORMULAS' or
                factors.get('formula_set_version') != '1.0' or
                [factor.get('id') for factor in factors.get('factors', [])] != list(FACTOR_IDS)):
            raise ValueError('factor identifiers or versions are unsupported')
    except (TypeError, ValueError):
        blockers.append('FACTOR_CONTRACT_INVALID')

    valid = not blockers
    blockers.append('NEW_STRATEGY_ADOPTION_REQUIRED')
    code_path = pathlib.Path(__file__).resolve()
    asset_hashes = {
        'strategy_code_sha256': hashlib.sha256(code_path.read_bytes()).hexdigest(),
        'parameter_sha256': (
            canonical_json_sha256(parameters) if parameters is not None else None),
        'factor_definition_sha256': (
            canonical_json_sha256(factors) if factors is not None else None),
    }
    return {
        'artifact': 'GP12_CANDIDATE_PACKAGE_REVIEW_V1',
        'strategy_id': STRATEGY_ID,
        'status': 'CANDIDATE_READY_FOR_REVIEW' if valid else 'CANDIDATE_PACKAGE_INVALID',
        'adoption_status': PROPOSAL_STATUS,
        'candidate_review_passed': valid,
        'historical_strategy_recovered': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
        'real_feature_inputs_validated': False,
        'real_calibration_fitted': False,
        'source_ids_substantively_verified': False,
        'asset_hashes': asset_hashes,
        'blockers': blockers,
    }


def _main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Review the GP12 candidate package')
    parser.add_argument('--review', action='store_true', help='emit a package review')
    parser.add_argument('--out', required=True, help='output JSON path')
    parser.add_argument(
        '--parameters', default=str(root / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'))
    parser.add_argument(
        '--factors', default=str(root / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'))
    args = parser.parse_args()
    if not args.review:
        parser.error('--review is required')
    result = review_package(args.parameters, args.factors)
    output = pathlib.Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        encoding='utf-8',
    )
    return 0 if result['candidate_review_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(_main())
