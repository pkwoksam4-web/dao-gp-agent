from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import re


VERSION = 'V4.82'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
OOS_START = '2026-04-18'
OOS_END = '2026-09-08'
LIQUIDITY_THRESHOLD_CNY = 80_000_000
EXPECTED_UNIVERSE_N = 847
EXPECTED_FORMAL_N = 844
FROZEN_CALENDAR_LEGACY_SHA256 = '0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0'
FROZEN_CALENDAR_N = 1426
FROZEN_CALENDAR_FIRST = FORMAL_START
FROZEN_CALENDAR_LAST = FORMAL_END
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
SCOPE_KEYS = {
    'artifact', 'version', 'formal_end', 'oos_start', 'oos_end',
    'intent_frozen', 'pre_exposure_confirmed',
}
RESERVED_KEYS = {
    'return', 'returns', 'pnl', 'alpha', 'sharpe', 'drawdown',
    'hit_rate', 'win_rate', 'performance', 'metrics',
    'signal_result', 'signal_results',
}
MODEL_KEYS = {
    'artifact', 'version', 'strategy_id', 'strategy_code_sha256',
    'parameter_sha256', 'universe_sha256', 'factor_definition_sha256',
    'calendar_sha256', 'formal_artifact_sha256', 'liquidity_threshold_cny',
    'formal_end', 'frozen',
}


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')
    ).encode('utf-8')


def canonical_json_sha256(obj: object) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def _sha_ok(value: object) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def canonical_universe(
    text: str,
    expected_count: int = EXPECTED_UNIVERSE_N,
    expected_symbols: list[str] | None = None,
) -> tuple[list[str], str]:
    rows = [line.strip() for line in text.splitlines()]
    if not rows or any(not row for row in rows):
        raise ValueError('blank universe symbol')
    if len(rows) != expected_count:
        raise ValueError('universe count mismatch')
    if len(set(rows)) != len(rows):
        raise ValueError('duplicate universe symbol')
    if expected_symbols is not None and rows != expected_symbols:
        raise ValueError('universe order/content mismatch')
    payload = '\n'.join(rows).encode('utf-8')
    return rows, hashlib.sha256(payload).hexdigest()


def decode_calendar_representations(b64_text: str, hex_text: str) -> bytes:
    """Legacy/synthetic dual-wrapper decoder retained for regression tests.

    Production recovery does not depend on repository wrapper equivalence; it
    uses the V4.80 final-audit calendar CSV artifact instead.
    """
    try:
        normalized = ''.join(b64_text.split())
        normalized += '=' * ((-len(normalized)) % 4)
        b64_payload = base64.b64decode(normalized, validate=True)
        hex_payload = bytes.fromhex(''.join(hex_text.split()))
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid calendar representation') from exc
    if b64_payload != hex_payload:
        raise ValueError('calendar representation mismatch')
    return b64_payload


def _validate_date_sequence(dates: list[str]) -> list[str]:
    if not dates:
        raise ValueError('empty calendar')
    for value in dates:
        if not DATE_RE.fullmatch(value):
            raise ValueError('invalid calendar date')
        try:
            dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError('invalid calendar date') from exc
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError('calendar dates not strictly increasing')
    return dates


def parse_calendar_dates(gzip_bytes: bytes) -> list[str]:
    try:
        decoded = gzip.decompress(gzip_bytes).decode('utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise ValueError('invalid gzip calendar payload') from exc

    dates: list[str] = []
    reader = csv.reader(io.StringIO(decoded))
    for row_index, row in enumerate(reader):
        if not row:
            continue
        candidates = [cell.strip() for cell in row if cell.strip()]
        date_value = next((cell for cell in candidates if DATE_RE.fullmatch(cell)), None)
        if date_value is None:
            if row_index == 0:
                continue
            raise ValueError('calendar row has no ISO date')
        dates.append(date_value)
    return _validate_date_sequence(dates)


def calendar_range_sha256(
    dates: list[str], start: str, end: str
) -> tuple[list[str], str]:
    try:
        start_date = dt.date.fromisoformat(start)
        end_date = dt.date.fromisoformat(end)
    except ValueError as exc:
        raise ValueError('invalid range date') from exc
    if end_date < start_date:
        raise ValueError('invalid calendar range')

    selected = [d for d in dates if start <= d <= end]
    if not selected:
        raise ValueError('calendar range empty')
    if selected[0] != start or selected[-1] != end:
        raise ValueError('calendar range boundary missing')
    payload = '\n'.join(selected).encode('ascii')
    return selected, hashlib.sha256(payload).hexdigest()


def verify_authoritative_calendar_csv(
    csv_text: str,
    expected_n: int = FROZEN_CALENDAR_N,
    expected_first: str = FROZEN_CALENDAR_FIRST,
    expected_last: str = FROZEN_CALENDAR_LAST,
    expected_legacy_sha256: str = FROZEN_CALENDAR_LEGACY_SHA256,
) -> dict:
    """Verify the calendar CSV emitted by successful V4.80 final audit.

    The legacy V4.80 hash has a trailing newline after every date. The recovery
    semantic hash has no trailing newline. Both namespaces are recorded.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
        fields = list(reader.fieldnames or [])
        date_field = 'trade_date' if 'trade_date' in fields else ('date' if 'date' in fields else None)
        if date_field is None:
            raise ValueError('calendar CSV missing date field')
        dates = [str(row.get(date_field, '')).strip() for row in reader]
    except (csv.Error, TypeError) as exc:
        raise ValueError('invalid calendar CSV') from exc

    if any(not value for value in dates):
        raise ValueError('blank calendar date')
    _validate_date_sequence(dates)
    if len(dates) != expected_n:
        raise ValueError(f'calendar count mismatch: {len(dates)} != {expected_n}')
    if dates[0] != expected_first or dates[-1] != expected_last:
        raise ValueError('calendar bounds mismatch')

    legacy_payload = ''.join(value + '\n' for value in dates).encode('ascii')
    legacy_sha = hashlib.sha256(legacy_payload).hexdigest()
    if legacy_sha != expected_legacy_sha256:
        raise ValueError('calendar legacy hash mismatch')

    semantic_payload = '\n'.join(dates).encode('ascii')
    semantic_sha = hashlib.sha256(semantic_payload).hexdigest()
    return {
        'dates': dates,
        'date_n': len(dates),
        'first': dates[0],
        'last': dates[-1],
        'legacy_frozen_calendar_sha256': legacy_sha,
        'formal_calendar_sha256': semantic_sha,
    }


def _find_reserved(value: object, path: str = '$') -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f'{path}.{key}'
            if str(key).lower() in RESERVED_KEYS:
                hits.append(child_path)
            hits.extend(_find_reserved(child, child_path))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            hits.extend(_find_reserved(child, f'{path}[{i}]'))
    return hits


def _formal_blockers(formal: dict) -> list[str]:
    blockers: list[str] = []
    if formal.get('artifact') != 'FORMAL_READINESS_FINAL_V482':
        blockers.append('FORMAL_ARTIFACT_INVALID')
    if formal.get('version') != VERSION:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    if formal.get('formal_ready') is not True:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    if formal.get('validated_global_provenance_emitted') is not True:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    if formal.get('oos_metrics_allowed') is not False:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    if formal.get('universe_n') != EXPECTED_UNIVERSE_N:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    if formal.get('formal_symbol_n') != EXPECTED_FORMAL_N:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    market = formal.get('market_data')
    if not isinstance(market, dict) or market.get('market_data_ready') is not True:
        blockers.append('FORMAL_ARTIFACT_INVALID')
    elif market.get('liquidity_threshold_cny') != LIQUIDITY_THRESHOLD_CNY:
        blockers.append('LIQUIDITY_RULE_MISMATCH')
    return sorted(set(blockers))


def _strategy_hashes(
    blockers: list[str],
    strategy_code_bytes: bytes | None,
    parameters: dict | None,
    factor_definition: dict | None,
) -> dict:
    if strategy_code_bytes is None:
        strategy_sha = None
        blockers.append('STRATEGY_CODE_MISSING')
    elif not isinstance(strategy_code_bytes, (bytes, bytearray)) or not strategy_code_bytes:
        strategy_sha = None
        blockers.append('STRATEGY_CODE_INVALID')
    else:
        strategy_sha = hashlib.sha256(bytes(strategy_code_bytes)).hexdigest()

    if parameters is None:
        parameter_sha = None
        blockers.append('PARAMETER_SET_MISSING')
    elif not isinstance(parameters, dict) or not parameters:
        parameter_sha = None
        blockers.append('PARAMETER_SET_INVALID')
    else:
        parameter_sha = canonical_json_sha256(parameters)

    if factor_definition is None:
        factor_sha = None
        blockers.append('FACTOR_DEFINITION_MISSING')
    elif not isinstance(factor_definition, dict) or not factor_definition:
        factor_sha = None
        blockers.append('FACTOR_DEFINITION_INVALID')
    else:
        factor_sha = canonical_json_sha256(factor_definition)

    return {
        'strategy_code_sha256': strategy_sha,
        'parameter_sha256': parameter_sha,
        'factor_definition_sha256': factor_sha,
    }


def _checkpoint_from_calendar_info(
    formal: dict,
    universe_text: str,
    calendar_info: dict | None,
    calendar_blockers: list[str],
    strategy_code_bytes: bytes | None,
    parameters: dict | None,
    factor_definition: dict | None,
    source_evidence: dict,
) -> dict:
    blockers = _formal_blockers(formal) if isinstance(formal, dict) else ['FORMAL_ARTIFACT_INVALID']
    blockers.extend(calendar_blockers)
    formal_sha = canonical_json_sha256(formal) if isinstance(formal, dict) else None

    universe_sha = None
    universe_rows: list[str] = []
    try:
        universe_rows, universe_sha = canonical_universe(universe_text)
    except (TypeError, ValueError):
        blockers.append('UNIVERSE_INVALID')

    formal_calendar_sha = calendar_info.get('formal_calendar_sha256') if calendar_info else None
    legacy_calendar_sha = calendar_info.get('legacy_frozen_calendar_sha256') if calendar_info else None
    calendar_first = calendar_info.get('first') if calendar_info else None
    calendar_last = calendar_info.get('last') if calendar_info else None
    calendar_n = int(calendar_info.get('date_n') or 0) if calendar_info else 0
    if calendar_info and calendar_last < OOS_END:
        blockers.append('OOS_CALENDAR_COVERAGE_MISSING')

    strategy_assets = _strategy_hashes(
        blockers, strategy_code_bytes, parameters, factor_definition
    )
    blockers = sorted(set(blockers))
    complete = not blockers

    formal_bad = 'FORMAL_ARTIFACT_INVALID' in blockers
    return {
        'artifact': 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
        'version': VERSION,
        'status': 'MODEL_ASSETS_COMPLETE_V482' if complete else 'MODEL_ASSETS_INCOMPLETE_V482',
        'formal_artifact_sha256': formal_sha,
        'universe_sha256': universe_sha,
        'formal_calendar_sha256': formal_calendar_sha,
        'liquidity_threshold_cny': LIQUIDITY_THRESHOLD_CNY,
        'formal_end': FORMAL_END,
        'recoverable': {
            'formal_artifact': isinstance(formal, dict) and not formal_bad,
            'universe': universe_sha is not None,
            'formal_calendar': calendar_info is not None and formal_calendar_sha is not None,
            'liquidity_rule': 'LIQUIDITY_RULE_MISMATCH' not in blockers,
        },
        'strategy_assets': strategy_assets,
        'evidence': {
            'universe': {
                'path': 'data/pit_st_scope_v480.txt',
                'count': len(universe_rows),
                'sha256': universe_sha,
            },
            'formal_calendar': {
                **source_evidence,
                'start': FORMAL_START,
                'end': FORMAL_END,
                'date_n': calendar_n,
                'decoded_min': calendar_first,
                'decoded_max': calendar_last,
                'legacy_frozen_calendar_sha256': legacy_calendar_sha,
                'sha256': formal_calendar_sha,
            },
        },
        'blockers': blockers,
        'model_freeze_allowed': complete,
    }


def recover_checkpoint(
    formal: dict,
    universe_text: str,
    calendar_b64_text: str,
    calendar_hex_text: str,
    strategy_code_bytes: bytes | None = None,
    parameters: dict | None = None,
    factor_definition: dict | None = None,
) -> dict:
    """Legacy wrapper path retained for synthetic/backward tests."""
    calendar_info = None
    calendar_blockers: list[str] = []
    payload_sha = None
    try:
        payload = decode_calendar_representations(calendar_b64_text, calendar_hex_text)
        payload_sha = hashlib.sha256(payload).hexdigest()
        all_dates = parse_calendar_dates(payload)
        selected, semantic_sha = calendar_range_sha256(all_dates, FORMAL_START, FORMAL_END)
        legacy_sha = hashlib.sha256(
            ''.join(value + '\n' for value in selected).encode('ascii')
        ).hexdigest()
        calendar_info = {
            'first': selected[0], 'last': selected[-1], 'date_n': len(selected),
            'legacy_frozen_calendar_sha256': legacy_sha,
            'formal_calendar_sha256': semantic_sha,
        }
    except ValueError as exc:
        if 'representation mismatch' in str(exc):
            calendar_blockers.append('FORMAL_CALENDAR_REPRESENTATION_MISMATCH')
        else:
            calendar_blockers.append('FORMAL_CALENDAR_INVALID')

    return _checkpoint_from_calendar_info(
        formal, universe_text, calendar_info, calendar_blockers,
        strategy_code_bytes, parameters, factor_definition,
        {
            'source_kind': 'legacy_repository_wrappers',
            'b64_path': 'data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.b64',
            'hex_path': 'data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.hex',
            'decoded_payload_sha256': payload_sha,
        },
    )


def recover_checkpoint_from_authoritative_calendar(
    formal: dict,
    universe_text: str,
    calendar_csv_text: str,
    strategy_code_bytes: bytes | None = None,
    parameters: dict | None = None,
    factor_definition: dict | None = None,
) -> dict:
    calendar_info = None
    blockers: list[str] = []
    try:
        calendar_info = verify_authoritative_calendar_csv(calendar_csv_text)
    except ValueError:
        blockers.append('FORMAL_CALENDAR_INVALID')
    return _checkpoint_from_calendar_info(
        formal, universe_text, calendar_info, blockers,
        strategy_code_bytes, parameters, factor_definition,
        {
            'source_kind': 'v480_final_audit_artifact',
            'workflow_run_id': 33977325822,
            'artifact_id': 9972698555,
            'artifact_name': 'gp-pit-st-v480-final-audit',
            'file': 'OFFICIAL_A_SHARE_OPEN_DATES_V357.csv',
        },
    )


def validate_scope_intent(scope: dict) -> list[str]:
    blockers: list[str] = []
    if not isinstance(scope, dict):
        return ['SCOPE_INTENT_INVALID']
    if _find_reserved(scope):
        blockers.append('FORBIDDEN_OOS_METRIC_FIELD')
    if set(scope) != SCOPE_KEYS:
        blockers.append('SCOPE_INTENT_INVALID')
    expected = {
        'artifact': 'OOS_SCOPE_INTENT_V482', 'version': VERSION,
        'formal_end': FORMAL_END, 'oos_start': OOS_START, 'oos_end': OOS_END,
        'intent_frozen': True, 'pre_exposure_confirmed': True,
    }
    if any(scope.get(key) != value for key, value in expected.items()):
        blockers.append('SCOPE_INTENT_INVALID')
    return sorted(set(blockers))


def promote_model_freeze(checkpoint: dict, strategy_id: str, calendar_sha256: str) -> dict:
    if not isinstance(checkpoint, dict):
        raise ValueError('checkpoint invalid')
    required = (
        checkpoint.get('artifact') == 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
        checkpoint.get('version') == VERSION,
        checkpoint.get('status') == 'MODEL_ASSETS_COMPLETE_V482',
        checkpoint.get('model_freeze_allowed') is True,
        checkpoint.get('blockers') == [],
        checkpoint.get('liquidity_threshold_cny') == LIQUIDITY_THRESHOLD_CNY,
        checkpoint.get('formal_end') == FORMAL_END,
    )
    if not all(required):
        raise ValueError('checkpoint incomplete')
    if not isinstance(strategy_id, str) or not strategy_id.strip():
        raise ValueError('strategy id invalid')
    if not _sha_ok(calendar_sha256):
        raise ValueError('calendar hash invalid')
    assets = checkpoint.get('strategy_assets') or {}
    hashes = {
        'strategy_code_sha256': assets.get('strategy_code_sha256'),
        'parameter_sha256': assets.get('parameter_sha256'),
        'universe_sha256': checkpoint.get('universe_sha256'),
        'factor_definition_sha256': assets.get('factor_definition_sha256'),
        'calendar_sha256': calendar_sha256,
        'formal_artifact_sha256': checkpoint.get('formal_artifact_sha256'),
    }
    if any(not _sha_ok(value) for value in hashes.values()):
        raise ValueError('checkpoint hash invalid')
    return {
        'artifact': 'MODEL_FREEZE_V482', 'version': VERSION,
        'strategy_id': strategy_id.strip(), **hashes,
        'liquidity_threshold_cny': LIQUIDITY_THRESHOLD_CNY,
        'formal_end': FORMAL_END, 'frozen': True,
    }


def _validate_model(model: dict) -> None:
    if not isinstance(model, dict) or set(model) != MODEL_KEYS:
        raise ValueError('model freeze invalid')
    if model.get('artifact') != 'MODEL_FREEZE_V482' or model.get('version') != VERSION:
        raise ValueError('model freeze invalid')
    if model.get('frozen') is not True or model.get('formal_end') != FORMAL_END:
        raise ValueError('model freeze invalid')
    if model.get('liquidity_threshold_cny') != LIQUIDITY_THRESHOLD_CNY:
        raise ValueError('model freeze invalid')
    if not isinstance(model.get('strategy_id'), str) or not model.get('strategy_id').strip():
        raise ValueError('model freeze invalid')
    for key in MODEL_KEYS:
        if key.endswith('_sha256') and not _sha_ok(model.get(key)):
            raise ValueError('model freeze invalid')


def promote_oos_scope(intent: dict, model_freeze: dict, calendar_sha256: str) -> dict:
    if validate_scope_intent(intent):
        raise ValueError('scope intent invalid')
    _validate_model(model_freeze)
    if not _sha_ok(calendar_sha256):
        raise ValueError('calendar hash invalid')
    if model_freeze.get('calendar_sha256') != calendar_sha256:
        raise ValueError('calendar hash mismatch')
    return {
        'artifact': 'OOS_SCOPE_V482', 'version': VERSION,
        'formal_end': intent['formal_end'], 'oos_start': intent['oos_start'],
        'oos_end': intent['oos_end'], 'calendar_sha256': calendar_sha256,
        'universe_sha256': model_freeze['universe_sha256'],
        'model_freeze_sha256': canonical_json_sha256(model_freeze),
        'scope_frozen': True,
    }


def _read_json(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'{path} must contain JSON object')
    return value


def _strategy_inputs(
    strategy_code_path: pathlib.Path | None,
    parameters_path: pathlib.Path | None,
    factor_definition_path: pathlib.Path | None,
) -> tuple[bytes | None, dict | None, dict | None]:
    return (
        strategy_code_path.read_bytes() if strategy_code_path else None,
        _read_json(parameters_path) if parameters_path else None,
        _read_json(factor_definition_path) if factor_definition_path else None,
    )


def _scope_validation(scope: dict) -> dict:
    blockers = validate_scope_intent(scope)
    return {
        'artifact': 'OOS_SCOPE_INTENT_VALIDATION_V482', 'version': VERSION,
        'status': 'SCOPE_INTENT_VALID_V482' if not blockers else 'SCOPE_INTENT_INVALID_V482',
        'blockers': blockers,
        'scope_intent_sha256': canonical_json_sha256(scope),
    }


def run_paths(
    formal_path: pathlib.Path,
    universe_path: pathlib.Path,
    calendar_b64_path: pathlib.Path,
    calendar_hex_path: pathlib.Path,
    scope_intent_path: pathlib.Path,
    strategy_code_path: pathlib.Path | None = None,
    parameters_path: pathlib.Path | None = None,
    factor_definition_path: pathlib.Path | None = None,
) -> tuple[dict, dict]:
    formal = _read_json(formal_path)
    scope = _read_json(scope_intent_path)
    strategy_bytes, parameters, factor_definition = _strategy_inputs(
        strategy_code_path, parameters_path, factor_definition_path
    )
    checkpoint = recover_checkpoint(
        formal, universe_path.read_text(encoding='utf-8'),
        calendar_b64_path.read_text(encoding='utf-8'),
        calendar_hex_path.read_text(encoding='utf-8'),
        strategy_bytes, parameters, factor_definition,
    )
    return checkpoint, _scope_validation(scope)


def run_authoritative_paths(
    formal_path: pathlib.Path,
    universe_path: pathlib.Path,
    calendar_csv_path: pathlib.Path,
    scope_intent_path: pathlib.Path,
    strategy_code_path: pathlib.Path | None = None,
    parameters_path: pathlib.Path | None = None,
    factor_definition_path: pathlib.Path | None = None,
) -> tuple[dict, dict]:
    formal = _read_json(formal_path)
    scope = _read_json(scope_intent_path)
    strategy_bytes, parameters, factor_definition = _strategy_inputs(
        strategy_code_path, parameters_path, factor_definition_path
    )
    checkpoint = recover_checkpoint_from_authoritative_calendar(
        formal, universe_path.read_text(encoding='utf-8'),
        calendar_csv_path.read_text(encoding='utf-8'),
        strategy_bytes, parameters, factor_definition,
    )
    return checkpoint, _scope_validation(scope)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--formal', required=True)
    ap.add_argument('--universe', required=True)
    ap.add_argument('--calendar-csv')
    ap.add_argument('--calendar-b64')
    ap.add_argument('--calendar-hex')
    ap.add_argument('--scope-intent', required=True)
    ap.add_argument('--strategy-code')
    ap.add_argument('--parameters')
    ap.add_argument('--factor-definition')
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()

    strategy_path = pathlib.Path(args.strategy_code) if args.strategy_code else None
    parameters_path = pathlib.Path(args.parameters) if args.parameters else None
    factor_path = pathlib.Path(args.factor_definition) if args.factor_definition else None

    if args.calendar_csv:
        checkpoint, scope_validation = run_authoritative_paths(
            pathlib.Path(args.formal), pathlib.Path(args.universe),
            pathlib.Path(args.calendar_csv), pathlib.Path(args.scope_intent),
            strategy_path, parameters_path, factor_path,
        )
    else:
        if not args.calendar_b64 or not args.calendar_hex:
            raise SystemExit('provide --calendar-csv or both --calendar-b64 and --calendar-hex')
        checkpoint, scope_validation = run_paths(
            pathlib.Path(args.formal), pathlib.Path(args.universe),
            pathlib.Path(args.calendar_b64), pathlib.Path(args.calendar_hex),
            pathlib.Path(args.scope_intent), strategy_path, parameters_path, factor_path,
        )

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482.json').write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (out_dir / 'OOS_SCOPE_INTENT_VALIDATION_V482.json').write_text(
        json.dumps(scope_validation, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    cal = checkpoint['evidence']['formal_calendar']
    print(json.dumps({
        'status': checkpoint['status'], 'blockers': checkpoint['blockers'],
        'model_freeze_allowed': checkpoint['model_freeze_allowed'],
        'formal_artifact_sha256': checkpoint['formal_artifact_sha256'],
        'universe_sha256': checkpoint['universe_sha256'],
        'formal_calendar_sha256': checkpoint['formal_calendar_sha256'],
        'legacy_frozen_calendar_sha256': cal.get('legacy_frozen_calendar_sha256'),
        'calendar_decoded_min': cal.get('decoded_min'),
        'calendar_decoded_max': cal.get('decoded_max'),
        'formal_calendar_date_n': cal.get('date_n'),
        'scope_intent_status': scope_validation['status'],
        'scope_intent_sha256': scope_validation['scope_intent_sha256'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
