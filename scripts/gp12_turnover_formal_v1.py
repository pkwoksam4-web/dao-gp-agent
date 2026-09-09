from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import date
from typing import Any

from gp12_sina_share_amount_v1 import resolve_share_state


VERSION = '1.0'
STRATEGY_ID = 'GP12_REBUILD_CANDIDATE_V1'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
FORMAL_ARTIFACT_SHA256 = 'e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796'
FORMAL_CALENDAR_SHA256 = '5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7'
UNIVERSE_SHA256 = 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb'
PARAMETERS_SHA256 = '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204'
FACTORS_SHA256 = 'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e'
RAW_ARTIFACT_NAME = 'gp-sohu-full-raw-v482-reaudit'
RAW_ARTIFACT_SHA256 = 'cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550'
PRODUCTION_EXPECTED_TRADE_ROWS = 1_011_607
PRODUCTION_EXPECTED_SYMBOL_N = 847
ROW_FIELDS = (
    'symbol',
    'date',
    'volume_shares',
    'outstanding_share_shares',
    'turnover_ratio',
    'raw_volume_source_artifact',
    'raw_volume_source_sha256',
    'share_source',
    'share_record_date',
    'share_raw_sha256',
)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _iso_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError('date must be a string')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('date must be ISO YYYY-MM-DD') from exc
    if parsed.isoformat() != value:
        raise ValueError('date must use canonical ISO format')
    return value


def _normalize_symbol(value: Any) -> str:
    if not isinstance(value, str) or '.' not in value:
        raise ValueError('exchange-qualified symbol required')
    code, exchange = value.strip().upper().split('.', 1)
    if exchange not in {'SH', 'SZ'} or not code.isdigit() or len(code) > 6:
        raise ValueError('invalid symbol')
    return f'{code.zfill(6)}.{exchange}'


def _finite_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError('boolean is not numeric')
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('numeric value required') from exc
    if not math.isfinite(number):
        raise ValueError('finite numeric value required')
    return number


def canonical_turnover_csv_bytes(rows: list[dict]) -> bytes:
    if not isinstance(rows, list):
        raise ValueError('rows must be a list')
    ordered = sorted(
        (dict(row) for row in rows),
        key=lambda row: (str(row.get('symbol')), str(row.get('date'))),
    )
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(ROW_FIELDS), lineterminator='\n')
    writer.writeheader()
    for row in ordered:
        writer.writerow({field: row.get(field) for field in ROW_FIELDS})
    return buffer.getvalue().encode('utf-8')


def _share_manifest_hash(manifest: dict) -> str:
    if not isinstance(manifest, dict):
        raise ValueError('share manifest must be an object')
    return canonical_json_sha256(manifest)


def _summary_template(
    *,
    symbol_n: int,
    expected_trade_rows: int,
    share_manifest_sha256: str,
) -> dict:
    return {
        'artifact': 'GP12_TURNOVER_FORMAL_V1',
        'version': VERSION,
        'strategy_id': STRATEGY_ID,
        'formal_start': FORMAL_START,
        'formal_end': FORMAL_END,
        'formal_artifact_sha256': FORMAL_ARTIFACT_SHA256,
        'formal_calendar_sha256': FORMAL_CALENDAR_SHA256,
        'universe_sha256': UNIVERSE_SHA256,
        'candidate_parameters_sha256': PARAMETERS_SHA256,
        'candidate_factors_sha256': FACTORS_SHA256,
        'raw_volume_source_artifact': RAW_ARTIFACT_NAME,
        'raw_volume_source_sha256': RAW_ARTIFACT_SHA256,
        'share_manifest_sha256': share_manifest_sha256,
        'turnover_rows_sha256': None,
        'symbol_n': symbol_n,
        'expected_trade_rows': expected_trade_rows,
        'materialized_trade_rows': 0,
        'duplicate_row_n': 0,
        'missing_turnover_row_n': 0,
        'extra_turnover_row_n': 0,
        'nonpositive_volume_n': 0,
        'nonpositive_outstanding_share_n': 0,
        'nonfinite_turnover_n': 0,
        'future_share_record_violation_n': 0,
        'unresolved_prior_share_record_n': 0,
        'pit_state': 'PIT_UNVERIFIED',
        'status': 'BLOCKED_FORMAL_TURNOVER_V1',
        'blockers': [],
        'formal_feature_ready': False,
        'candidate_freeze_ready': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def materialize_turnover(
    raw_rows: list[dict],
    share_records_by_symbol: dict[str, list[dict]],
    universe: list[str],
    share_manifest: dict,
    *,
    share_date_semantics_verified: bool,
) -> tuple[list[dict], dict]:
    if not isinstance(raw_rows, list):
        raise ValueError('raw_rows must be a list')
    if not isinstance(share_records_by_symbol, dict):
        raise ValueError('share_records_by_symbol must be an object')
    if not isinstance(universe, list) or not universe:
        raise ValueError('universe must be a nonempty list')

    normalized_universe = [_normalize_symbol(symbol) for symbol in universe]
    if len(normalized_universe) != len(set(normalized_universe)):
        raise ValueError('universe contains duplicate symbols')
    universe_order = {symbol: i for i, symbol in enumerate(normalized_universe)}

    manifest_hash = _share_manifest_hash(share_manifest)
    summary = _summary_template(
        symbol_n=len(normalized_universe),
        expected_trade_rows=len(raw_rows),
        share_manifest_sha256=manifest_hash,
    )
    blockers: set[str] = set()
    blockers.update(share_manifest.get('blockers') or [])
    if not share_date_semantics_verified:
        blockers.add('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED')

    raw_keys: list[tuple[str, str]] = []
    seen_raw_keys: set[tuple[str, str]] = set()
    duplicate_row_n = 0
    materialized: list[dict] = []
    materialized_keys: set[tuple[str, str]] = set()

    normalized_shares = {
        _normalize_symbol(symbol): records
        for symbol, records in share_records_by_symbol.items()
    }

    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ValueError('RAW row must be an object')
        symbol = _normalize_symbol(raw.get('symbol'))
        if symbol not in universe_order:
            raise ValueError('RAW row symbol outside provided universe')
        trade_date = _iso_date(raw.get('date'))
        if trade_date < FORMAL_START or trade_date > FORMAL_END:
            raise ValueError('FORMAL_BOUNDARY_VIOLATION')
        key = (symbol, trade_date)
        raw_keys.append(key)
        if key in seen_raw_keys:
            duplicate_row_n += 1
            blockers.add('TURNOVER_DUPLICATE_ROW')
            continue
        seen_raw_keys.add(key)

        try:
            volume = _finite_number(raw.get('volume'))
        except ValueError:
            summary['nonfinite_turnover_n'] += 1
            blockers.add('TURNOVER_NONFINITE_VALUE')
            continue
        if volume <= 0:
            summary['nonpositive_volume_n'] += 1
            blockers.add('RAW_VOLUME_UNIT_INVALID')
            continue

        records = normalized_shares.get(symbol, [])
        try:
            resolved = resolve_share_state(records, trade_date)
        except ValueError:
            summary['nonpositive_outstanding_share_n'] += 1
            blockers.add('SINA_SHARE_VALUE_INVALID')
            continue
        if resolved is None:
            summary['unresolved_prior_share_record_n'] += 1
            blockers.add('TURNOVER_PRIOR_SHARE_RECORD_MISSING')
            continue

        record_date = _iso_date(resolved.get('record_date'))
        if record_date > trade_date:
            summary['future_share_record_violation_n'] += 1
            blockers.add('TURNOVER_FUTURE_SHARE_RECORD_VIOLATION')
            continue
        try:
            outstanding = _finite_number(resolved.get('outstanding_share_shares'))
        except ValueError:
            summary['nonpositive_outstanding_share_n'] += 1
            blockers.add('SINA_SHARE_VALUE_INVALID')
            continue
        if outstanding <= 0:
            summary['nonpositive_outstanding_share_n'] += 1
            blockers.add('SINA_SHARE_VALUE_INVALID')
            continue
        turnover = volume / outstanding
        if not math.isfinite(turnover):
            summary['nonfinite_turnover_n'] += 1
            blockers.add('TURNOVER_NONFINITE_VALUE')
            continue

        share_raw_sha = resolved.get('share_raw_sha256')
        if not isinstance(share_raw_sha, str) or len(share_raw_sha) != 64:
            share_raw_sha = '0' * 64
        row = {
            'symbol': symbol,
            'date': trade_date,
            'volume_shares': volume,
            'outstanding_share_shares': outstanding,
            'turnover_ratio': turnover,
            'raw_volume_source_artifact': RAW_ARTIFACT_NAME,
            'raw_volume_source_sha256': RAW_ARTIFACT_SHA256,
            'share_source': 'SINA_STOCKSERVICE_SHARE_AMOUNT',
            'share_record_date': record_date,
            'share_raw_sha256': share_raw_sha,
        }
        materialized.append(row)
        materialized_keys.add(key)

    raw_key_set = set(raw_keys)
    summary['duplicate_row_n'] = duplicate_row_n
    summary['materialized_trade_rows'] = len(materialized)
    summary['missing_turnover_row_n'] = len(raw_key_set - materialized_keys)
    summary['extra_turnover_row_n'] = len(materialized_keys - raw_key_set)
    if summary['missing_turnover_row_n'] or summary['extra_turnover_row_n']:
        blockers.add('TURNOVER_ROWSET_MISMATCH')

    materialized.sort(key=lambda row: (universe_order[row['symbol']], row['date']))
    summary['turnover_rows_sha256'] = hashlib.sha256(
        canonical_turnover_csv_bytes(materialized)
    ).hexdigest()

    if blockers:
        summary['pit_state'] = (
            'PIT_UNVERIFIED'
            if 'SINA_SHARE_DATE_SEMANTICS_UNVERIFIED' in blockers
            else 'PIT_VERIFIED' if share_date_semantics_verified else 'PIT_UNVERIFIED'
        )
        summary['status'] = 'BLOCKED_FORMAL_TURNOVER_V1'
        summary['formal_feature_ready'] = False
    else:
        summary['pit_state'] = 'PIT_VERIFIED'
        summary['status'] = 'PASS_FORMAL_TURNOVER_V1'
        summary['formal_feature_ready'] = True

    summary['blockers'] = sorted(set(blockers))
    return materialized, summary


def validate_production_summary(summary: dict) -> None:
    """Production-only guard; unit tests may use smaller synthetic fixtures."""
    if summary.get('symbol_n') != PRODUCTION_EXPECTED_SYMBOL_N:
        raise ValueError('UNIVERSE_BINDING_INVALID')
    if summary.get('expected_trade_rows') != PRODUCTION_EXPECTED_TRADE_ROWS:
        raise ValueError('RAW_VOLUME_ARTIFACT_INVALID')
    if summary.get('formal_artifact_sha256') != FORMAL_ARTIFACT_SHA256:
        raise ValueError('FORMAL_EVIDENCE_INVALID')
    if summary.get('formal_calendar_sha256') != FORMAL_CALENDAR_SHA256:
        raise ValueError('CALENDAR_BINDING_INVALID')
    if summary.get('universe_sha256') != UNIVERSE_SHA256:
        raise ValueError('UNIVERSE_BINDING_INVALID')
    if summary.get('raw_volume_source_artifact') != RAW_ARTIFACT_NAME:
        raise ValueError('RAW_VOLUME_ARTIFACT_INVALID')
    if summary.get('raw_volume_source_sha256') != RAW_ARTIFACT_SHA256:
        raise ValueError('RAW_VOLUME_ARTIFACT_INVALID')
