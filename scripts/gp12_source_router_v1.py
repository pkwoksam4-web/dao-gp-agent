from __future__ import annotations

from collections.abc import Iterable, Mapping


REQUIRED_FAMILIES = (
    'market_calendar',
    'stock_adjusted_close',
    'market_adjusted_close',
    'sector_adjusted_close',
    'amount_turnover',
    'main_net_flow',
    'market_breadth',
    'sector_breadth',
    'status',
    'intraday_15m',
    'intraday_60m',
)
PASS_STATUS = 'PASS'


def _priority_order(priority: Iterable[str] | None) -> list[str]:
    if priority is None:
        priority = ('sohu_sina_qfq', 'eastmoney')
    result = [str(item).strip() for item in priority]
    if not result or any(not item for item in result) or len(result) != len(set(result)):
        raise ValueError('priority must contain unique non-empty source IDs')
    return result


def _source_observation(source_id: object, observation: object) -> tuple[str, dict]:
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError('source ID must be a non-empty string')
    if not isinstance(observation, Mapping):
        raise ValueError(f'source report must be an object: {source_id}')
    families = observation.get('families')
    if not isinstance(families, Mapping):
        raise ValueError(f'source report has no families object: {source_id}')
    normalized = {}
    for family, value in families.items():
        if not isinstance(family, str) or family not in REQUIRED_FAMILIES:
            continue
        if not isinstance(value, Mapping):
            raise ValueError(f'family report must be an object: {source_id}/{family}')
        status = value.get('status')
        rows = value.get('rows', 0)
        if not isinstance(status, str) or not status:
            raise ValueError(f'family status is missing: {source_id}/{family}')
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
            raise ValueError(f'family rows must be a non-negative integer: {source_id}/{family}')
        normalized[family] = {'status': status, 'rows': rows}
    return source_id.strip(), {
        'families': normalized,
        'point_in_time_known_at': observation.get('point_in_time_known_at') is True,
        'source_ids_substantively_verified': (
            observation.get('source_ids_substantively_verified') is True),
    }


def build_source_switch_report(
        source_reports: Mapping[str, object], *,
        priority: Iterable[str] | None = None) -> dict:
    """Select a deterministic source per feature family and preserve failures.

    A PASS response only establishes structural coverage. This router therefore
    never promotes a route to substantive provenance, PIT validation, model
    freeze, or OOS eligibility.
    """
    if not isinstance(source_reports, Mapping):
        raise ValueError('source_reports must be an object')
    source_order = _priority_order(priority)
    normalized = {}
    for source_id, observation in source_reports.items():
        key, value = _source_observation(source_id, observation)
        normalized[key] = value

    # Sources not listed in the explicit priority still participate, but only
    # after listed sources and in lexical order for reproducibility.
    ordered_sources = list(source_order)
    ordered_sources.extend(sorted(key for key in normalized if key not in source_order))
    routes = {}
    missing = []
    failed = {}
    for family in REQUIRED_FAMILIES:
        candidates = []
        failures = []
        for source_id in ordered_sources:
            observation = normalized.get(source_id)
            if observation is None:
                continue
            entry = observation['families'].get(family)
            if entry is None:
                continue
            if entry['status'] == PASS_STATUS and entry['rows'] > 0:
                candidates.append((source_id, entry))
            else:
                failures.append(source_id)
        if candidates:
            source_id, entry = candidates[0]
            routes[family] = {
                'source_id': source_id,
                'status': entry['status'],
                'rows': entry['rows'],
                'validation_status': 'STRUCTURAL_ONLY',
            }
        else:
            missing.append(family)
            if failures:
                failed[family] = failures

    return {
        'required_families': list(REQUIRED_FAMILIES),
        'priority': source_order,
        'routes': routes,
        'missing_families': missing,
        'failed_families': failed,
        'structural_feature_families_complete': not missing,
        'point_in_time_known_at': False,
        'source_ids_substantively_verified': False,
        'real_feature_inputs_validated': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
