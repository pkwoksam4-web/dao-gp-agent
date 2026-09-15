from __future__ import annotations

from gp12_pit_adjusted_close_v482 import (
    build_forward_pit_adjusted_path,
    build_qfq_adjusted_path,
    compare_constant_scale_paths,
    resolve_final_event_availability,
    validate_event_availability,
)


def _key(symbol: str, ex_date: object) -> tuple[str, str]:
    normalized_symbol = str(symbol or '').upper()
    normalized_date = str(ex_date or '')[:10]
    if not normalized_symbol or len(normalized_date) != 10:
        raise ValueError('event key requires symbol and ex_date')
    return normalized_symbol, normalized_date


def finalize_symbol_events(
    symbol: str,
    frozen_events: list[dict],
    nominal_availability: dict[tuple[str, str], str],
    overrides: dict[tuple[str, str], float],
    override_availability: dict[tuple[str, str], str],
) -> list[dict]:
    """Pair every final event ratio with the availability date of that exact ratio."""
    normalized_symbol = str(symbol or '').upper()
    if not normalized_symbol:
        raise ValueError('symbol is required')

    rows = []
    seen = set()
    for raw in frozen_events or []:
        if not isinstance(raw, dict):
            raise ValueError('frozen event must be an object')
        key = _key(normalized_symbol, raw.get('ex_date'))
        if key in seen:
            raise ValueError(f'duplicate frozen event: {key}')
        seen.add(key)

        nominal_date = nominal_availability.get(key)
        if not nominal_date:
            raise ValueError(f'MISSING_EVENT_AVAILABILITY:{key[0]}:{key[1]}')

        if key in overrides:
            final_date = override_availability.get(key)
            if not final_date:
                raise ValueError(f'MISSING_OVERRIDE_AVAILABILITY:{key[0]}:{key[1]}')
            availability = resolve_final_event_availability(
                ex_date=key[1],
                nominal_availability_date=nominal_date,
                final_override_availability_date=final_date,
            )
            ratio = overrides[key]
            kind = 'FINAL_OVERRIDE'
        else:
            availability = resolve_final_event_availability(
                ex_date=key[1],
                nominal_availability_date=nominal_date,
            )
            ratio = raw.get('event_ratio')
            kind = 'NOMINAL_SOURCE'

        validated = validate_event_availability({
            'symbol': key[0],
            'ex_date': key[1],
            'availability_date': availability,
            'event_ratio': ratio,
        })
        row = dict(raw)
        row.update(validated)
        row['availability_kind'] = kind
        rows.append(row)

    return sorted(rows, key=lambda row: row['ex_date'])


def audit_symbol_path(
    *,
    symbol: str,
    raw_rows: list[dict],
    qfq_factors: list[dict],
    frozen_events: list[dict],
    nominal_availability: dict[tuple[str, str], str],
    overrides: dict[tuple[str, str], float],
    override_availability: dict[tuple[str, str], str],
    threshold_bp: float = 5.0,
) -> dict:
    final_events = finalize_symbol_events(
        symbol,
        frozen_events,
        nominal_availability,
        overrides,
        override_availability,
    )
    pit_path = build_forward_pit_adjusted_path(raw_rows, final_events)
    qfq_path = build_qfq_adjusted_path(raw_rows, qfq_factors)
    result = compare_constant_scale_paths(pit_path, qfq_path, threshold_bp=threshold_bp)
    result = dict(result)
    result['symbol'] = str(symbol or '').upper()
    result['final_event_n'] = len(final_events)
    result['final_override_n'] = sum(row.get('availability_kind') == 'FINAL_OVERRIDE' for row in final_events)
    return result
