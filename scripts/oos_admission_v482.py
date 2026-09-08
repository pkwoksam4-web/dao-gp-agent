from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re


VERSION = 'V4.82'
ARTIFACT = 'OOS_ADMISSION_V482'
FORMAL_END = '2026-04-17'
FORMAL_END_DATE = dt.date(2026, 4, 17)
LIQUIDITY_THRESHOLD_CNY = 80_000_000
RAW_TRADE_ROWS = 1_011_607
EXPECTED_CHECKPOINT = {
    'PASS': 844,
    'EXACT_TERM_REVIEW': 0,
    'MISSING_EVENT_REVIEW': 0,
    'NOT_APPLICABLE': 3,
}
NA_SYMBOLS = ['600074.SH', '600485.SH', '600677.SH']
SHA_RE = re.compile(r'^[0-9a-f]{64}$')

MODEL_KEYS = {
    'artifact',
    'version',
    'strategy_id',
    'strategy_code_sha256',
    'parameter_sha256',
    'universe_sha256',
    'factor_definition_sha256',
    'calendar_sha256',
    'formal_artifact_sha256',
    'liquidity_threshold_cny',
    'formal_end',
    'frozen',
}
MODEL_SHA_KEYS = {
    'strategy_code_sha256',
    'parameter_sha256',
    'universe_sha256',
    'factor_definition_sha256',
    'calendar_sha256',
    'formal_artifact_sha256',
}
SCOPE_KEYS = {
    'artifact',
    'version',
    'formal_end',
    'oos_start',
    'oos_end',
    'calendar_sha256',
    'universe_sha256',
    'model_freeze_sha256',
    'scope_frozen',
}
SCOPE_SHA_KEYS = {'calendar_sha256', 'universe_sha256', 'model_freeze_sha256'}
RESERVED_METRIC_KEYS = {
    'return',
    'returns',
    'pnl',
    'alpha',
    'sharpe',
    'drawdown',
    'hit_rate',
    'win_rate',
    'performance',
    'metrics',
}


def canonical_bytes(obj: object) -> bytes:
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def canonical_sha256(obj: object) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def find_forbidden_metric_paths(value: object, path: str = '$') -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child_value in value.items():
            child_path = f'{path}.{key}'
            if str(key).lower() in RESERVED_METRIC_KEYS:
                hits.append(child_path)
            hits.extend(find_forbidden_metric_paths(child_value, child_path))
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            hits.extend(find_forbidden_metric_paths(child_value, f'{path}[{index}]'))
    return hits


def _add(blockers: list[str], code: str) -> None:
    blockers.append(code)


def _sha_ok(value: object) -> bool:
    return bool(SHA_RE.fullmatch(str(value or '')))


def _date(value: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _formal_invalid(formal: dict, blockers: list[str]) -> None:
    if formal.get('artifact') != 'FORMAL_READINESS_FINAL_V482':
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if formal.get('version') != VERSION:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if formal.get('formal_ready') is not True:
        _add(blockers, 'FORMAL_NOT_READY')
    if formal.get('validated_global_provenance_emitted') is not True:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if formal.get('oos_metrics_allowed') is not False:
        if formal.get('oos_metrics_allowed') is True:
            _add(blockers, 'UPSTREAM_OOS_ALREADY_OPEN')
        else:
            _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if formal.get('checkpoint') != EXPECTED_CHECKPOINT:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if int(formal.get('universe_n') or 0) != 847:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if int(formal.get('formal_symbol_n') or 0) != 844:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if int(formal.get('full_path_pass_n') or 0) != 844:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    if int(formal.get('full_path_fail_n') or 0) != 0:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    try:
        max_bp = float(formal.get('max_full_path_diff_bp'))
    except (TypeError, ValueError):
        max_bp = float('inf')
    if max_bp > 5.0:
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')

    na = formal.get('na')
    if not isinstance(na, dict):
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    else:
        if int(na.get('count') or 0) != 3 or na.get('symbols') != NA_SYMBOLS:
            _add(blockers, 'FORMAL_ARTIFACT_INVALID')

    special = formal.get('special_provenance')
    if not isinstance(special, dict):
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    else:
        if int(special.get('materialized_n') or 0) != 11:
            _add(blockers, 'FORMAL_ARTIFACT_INVALID')
        if int(special.get('blocker_n') or 0) != 0:
            _add(blockers, 'FORMAL_ARTIFACT_INVALID')

    market = formal.get('market_data')
    if not isinstance(market, dict):
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
        return
    checks = (
        market.get('market_data_ready') is True,
        int(market.get('symbol_n') or 0) == 847,
        int(market.get('raw_trade_rows') or 0) == RAW_TRADE_ROWS,
        int(market.get('missing_trade_dates_n') or 0) == 0,
        int(market.get('extra_trade_dates_n') or 0) == 0,
        int(market.get('duplicate_symbol_dates') or 0) == 0,
        market.get('zero_trade_symbols') == NA_SYMBOLS,
        int(market.get('liquidity_threshold_cny') or 0) == LIQUIDITY_THRESHOLD_CNY,
        market.get('raw_pitst_status') == 'PASS_EXACT_RAW_PITST',
        int(market.get('current_trade_violation_n') or 0) == 0,
        int(market.get('st_overlay_violation_n') or 0) == 0,
    )
    if not all(checks):
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')


def _validate_model(model: dict, blockers: list[str]) -> None:
    if set(model) != MODEL_KEYS:
        _add(blockers, 'MODEL_FREEZE_INVALID')
    if model.get('artifact') != 'MODEL_FREEZE_V482' or model.get('version') != VERSION:
        _add(blockers, 'MODEL_FREEZE_INVALID')
    if not isinstance(model.get('strategy_id'), str) or not model.get('strategy_id').strip():
        _add(blockers, 'MODEL_FREEZE_INVALID')
    if any(not _sha_ok(model.get(key)) for key in MODEL_SHA_KEYS):
        _add(blockers, 'MODEL_FREEZE_INVALID')
    if int(model.get('liquidity_threshold_cny') or 0) != LIQUIDITY_THRESHOLD_CNY:
        _add(blockers, 'MODEL_FREEZE_INVALID')
    if model.get('formal_end') != FORMAL_END:
        _add(blockers, 'MODEL_FREEZE_INVALID')
    if model.get('frozen') is not True:
        _add(blockers, 'MODEL_NOT_FROZEN')


def _validate_scope(scope: dict, blockers: list[str]) -> None:
    if set(scope) != SCOPE_KEYS:
        _add(blockers, 'OOS_SCOPE_INVALID')
    if scope.get('artifact') != 'OOS_SCOPE_V482' or scope.get('version') != VERSION:
        _add(blockers, 'OOS_SCOPE_INVALID')
    if scope.get('formal_end') != FORMAL_END:
        _add(blockers, 'OOS_SCOPE_INVALID')
    if any(not _sha_ok(scope.get(key)) for key in SCOPE_SHA_KEYS):
        _add(blockers, 'OOS_SCOPE_INVALID')
    if scope.get('scope_frozen') is not True:
        _add(blockers, 'OOS_WINDOW_NOT_FROZEN')

    start = _date(scope.get('oos_start'))
    end = _date(scope.get('oos_end'))
    if start is None or end is None:
        _add(blockers, 'OOS_SCOPE_INVALID')
        return
    if start <= FORMAL_END_DATE:
        _add(blockers, 'OOS_WINDOW_OVERLAP')
    if end < start:
        _add(blockers, 'OOS_SCOPE_INVALID')


def _decision(
    blockers: list[str],
    formal: dict | None,
    model: dict | None,
    scope: dict | None,
    formal_sha: str | None,
    model_sha: str | None,
    scope_sha: str | None,
    data_isolation_pass: bool,
) -> dict:
    final_blockers = sorted(set(blockers))
    admitted = not final_blockers
    return {
        'artifact': ARTIFACT,
        'version': VERSION,
        'status': 'OOS_ADMITTED_V482' if admitted else 'OOS_BLOCKED_V482',
        'formal_ready': bool(isinstance(formal, dict) and formal.get('formal_ready') is True),
        'model_frozen': bool(isinstance(model, dict) and model.get('frozen') is True),
        'oos_window_frozen': bool(isinstance(scope, dict) and scope.get('scope_frozen') is True),
        'data_isolation_pass': bool(data_isolation_pass),
        'formal_artifact_sha256': formal_sha,
        'model_freeze_sha256': model_sha,
        'oos_scope_sha256': scope_sha,
        'blockers': final_blockers,
        'oos_metrics_allowed': admitted,
    }


def evaluate(
    formal: dict | None,
    model: dict | None,
    scope: dict | None,
    initial_blockers: list[str] | None = None,
) -> dict:
    blockers = list(initial_blockers or [])

    metric_paths: list[str] = []
    if isinstance(model, dict):
        metric_paths.extend(find_forbidden_metric_paths(model, '$.model'))
    if isinstance(scope, dict):
        metric_paths.extend(find_forbidden_metric_paths(scope, '$.scope'))
    data_isolation_pass = not metric_paths
    if metric_paths:
        _add(blockers, 'FORBIDDEN_OOS_METRIC_FIELD')

    formal_sha = canonical_sha256(formal) if isinstance(formal, dict) else None
    model_sha = canonical_sha256(model) if isinstance(model, dict) else None
    scope_sha = canonical_sha256(scope) if isinstance(scope, dict) else None

    if not isinstance(formal, dict):
        _add(blockers, 'FORMAL_ARTIFACT_INVALID')
    else:
        _formal_invalid(formal, blockers)

    if not isinstance(model, dict):
        _add(blockers, 'MODEL_FREEZE_INVALID')
    else:
        _validate_model(model, blockers)

    if not isinstance(scope, dict):
        _add(blockers, 'OOS_SCOPE_INVALID')
    else:
        _validate_scope(scope, blockers)

    if formal_sha is not None and isinstance(model, dict):
        if model.get('formal_artifact_sha256') != formal_sha:
            _add(blockers, 'FORMAL_HASH_MISMATCH')

    if model_sha is not None and isinstance(scope, dict):
        if scope.get('model_freeze_sha256') != model_sha:
            _add(blockers, 'MODEL_FREEZE_HASH_MISMATCH')

    if isinstance(model, dict) and isinstance(scope, dict):
        if scope.get('calendar_sha256') != model.get('calendar_sha256'):
            _add(blockers, 'CALENDAR_HASH_MISMATCH')
        if scope.get('universe_sha256') != model.get('universe_sha256'):
            _add(blockers, 'UNIVERSE_HASH_MISMATCH')
        if scope.get('formal_end') != model.get('formal_end'):
            _add(blockers, 'OOS_SCOPE_INVALID')

    return _decision(
        blockers=blockers,
        formal=formal,
        model=model,
        scope=scope,
        formal_sha=formal_sha,
        model_sha=model_sha,
        scope_sha=scope_sha,
        data_isolation_pass=data_isolation_pass,
    )


def _load_json_dict(path: pathlib.Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def run_paths(
    formal_path: pathlib.Path,
    model_path: pathlib.Path,
    scope_path: pathlib.Path,
) -> dict:
    formal = _load_json_dict(pathlib.Path(formal_path))
    model = _load_json_dict(pathlib.Path(model_path))
    scope = _load_json_dict(pathlib.Path(scope_path))
    initial: list[str] = []
    if formal is None:
        initial.append('FORMAL_ARTIFACT_INVALID')
    if model is None:
        initial.append('MODEL_FREEZE_INVALID')
    if scope is None:
        initial.append('OOS_SCOPE_INVALID')
    return evaluate(formal, model, scope, initial_blockers=initial)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--formal', required=True)
    ap.add_argument('--model-freeze', required=True)
    ap.add_argument('--oos-scope', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()

    decision = run_paths(
        pathlib.Path(args.formal),
        pathlib.Path(args.model_freeze),
        pathlib.Path(args.oos_scope),
    )
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'OOS_ADMISSION_V482.json').write_text(
        json.dumps(decision, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(json.dumps({
        'status': decision['status'],
        'blockers': decision['blockers'],
        'oos_metrics_allowed': decision['oos_metrics_allowed'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
