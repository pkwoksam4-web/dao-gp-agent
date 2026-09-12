from __future__ import annotations


FLOW_COLUMNS = [
    "dde_l",
    "l_net_value",
    "net_flow_rate",
    "act_buy_xl",
    "pas_buy_xl",
    "act_sell_xl",
    "pas_sell_xl",
    "act_buy_l",
    "pas_buy_l",
    "act_sell_l",
    "pas_sell_l",
    "act_buy_m",
    "pas_buy_m",
    "act_sell_m",
    "pas_sell_m",
    "buy_l",
    "sell_l",
]

EXPECTED_REPO_ID = "ellendan/a-share-21"
EXPECTED_SOURCE_COMMIT = "227be520b89ed737dd65bea4785a41ae39a9b7a4"
EXPECTED_FILENAME = "all-prices-with-values-250423.csv"
EXPECTED_SIZE_BYTES = 2134704074
EXPECTED_SHA256 = "034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea"


def _require(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError(msg)


def _validate_fund_flow_admission(a: dict) -> dict:
    _require(a.get('artifact') == 'GP12_FUND_FLOW_SNAPSHOT_ADMISSION_V482', 'fund-flow admission identity mismatch')
    _require(a.get('version') == 'V4.82' and a.get('strategy_id') == 'GP_V11', 'fund-flow admission identity mismatch')
    _require(a.get('status') == 'PASS_LOCKED_FUND_FLOW_SNAPSHOT_PAYLOAD_VERIFIED_PARTIAL_WINDOW', 'fund-flow admission status mismatch')
    _require(a.get('remote_pointer_identity_verified') is True, 'fund-flow remote pointer unverified')
    _require(a.get('actual_snapshot_bytes_verified_in_current_recovery') is True, 'fund-flow payload bytes unverified')
    _require(a.get('single_original_snapshot_policy_verified') is True, 'fund-flow single snapshot policy unverified')
    _require(a.get('formal_window_coverage_complete') is False, 'fund-flow unexpectedly covers Formal window')
    _require(a.get('pit_known_at_semantics_recovered') is False, 'fund-flow PIT semantics unexpectedly recovered')
    _require(a.get('factor_formula_recovered') is False, 'fund-flow factor formula unexpectedly recovered')
    _require(a.get('blocker_closed') is False and a.get('model_freeze_allowed') is False and a.get('oos_metrics_allowed') is False, 'fund-flow admission not fail-closed')
    s=a.get('source') or {}
    identity=(
        s.get('repo_id') == EXPECTED_REPO_ID
        and s.get('source_commit') == EXPECTED_SOURCE_COMMIT
        and s.get('filename') == EXPECTED_FILENAME
        and int(s.get('expected_size_bytes',-1)) == EXPECTED_SIZE_BYTES
        and int(s.get('actual_size_bytes',-1)) == EXPECTED_SIZE_BYTES
        and s.get('expected_sha256') == EXPECTED_SHA256
        and s.get('actual_sha256') == EXPECTED_SHA256
        and set(s.get('flow_columns') or []) == set(FLOW_COLUMNS)
    )
    _require(identity, 'fund-flow admission source identity mismatch')
    _require(int(s.get('rows',0)) > 0 and int(s.get('symbols',0)) > 0, 'fund-flow admission empty source scan')
    _require(bool(s.get('first_date')) and bool(s.get('last_date')), 'fund-flow admission date coverage missing')
    return a


def build_sector_fund_source_provenance(fund_flow_admission: dict | None = None) -> dict:
    """Bind recovered historical source facts without promoting missing strategy semantics.

    With no admission this reproduces the historical V3.10 source-clue state. When an exact
    fund-flow snapshot admission is supplied, the source-byte subgap is closed because the
    historical 2.13GB payload has been downloaded and independently SHA256-verified. Formal
    window coverage, PIT known-at semantics, sector membership provenance and factor formulas
    remain explicitly open.
    """
    verified = _validate_fund_flow_admission(fund_flow_admission) if fund_flow_admission is not None else None
    source = (verified or {}).get('source') or {}
    fund_bytes_verified = verified is not None

    fund_flow = {
        "adapter_path_recovered": True,
        "adapter_path": "src/prepare_ashare21_hf.py",
        "adapter_sha256": "739e5e24a817283dcd6234e067a73c2ee12b46cb1e13bd9e3857cf864ec3cfe7",
        "snapshot_fetcher_path": "src/fetch_ashare21_snapshot.py",
        "repo_id": EXPECTED_REPO_ID,
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "filename": EXPECTED_FILENAME,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "expected_sha256": EXPECTED_SHA256,
        "candidate_snapshot_identity_locked": True,
        "remote_pointer_identity_verified": bool(fund_bytes_verified),
        "actual_snapshot_bytes_verified_in_current_recovery": bool(fund_bytes_verified),
        "auto_converted_hf_parquet_allowed": False,
        "snapshot_policy": "EXACTLY_ONE_ORIGINAL_SOURCE_SNAPSHOT_FAIL_CLOSED",
        "preserved_flow_columns": list(FLOW_COLUMNS),
        "documented_public_coverage": ["2021-01-01", "2025-02-27"],
        "documented_public_coverage_precision": "APPROXIMATE_HISTORICAL_PACKAGE_DOCUMENTATION",
        "formal_window_coverage_complete": False,
        "pit_known_at_semantics_recovered": False,
        "pit_provenance_complete": False,
        "factor_formula_recovered": False,
    }
    if fund_bytes_verified:
        fund_flow.update({
            'verified_rows': int(source['rows']),
            'verified_symbols': int(source['symbols']),
            'verified_coverage': [str(source['first_date'])[:10], str(source['last_date'])[:10]],
            'verified_payload_size_bytes': int(source['actual_size_bytes']),
            'verified_payload_sha256': source['actual_sha256'],
        })

    remaining_data_gaps = [
        "SECTOR_SOURCE_SNAPSHOT_IDENTITY_UNBOUND",
        "SECTOR_SOURCE_BYTES_NOT_HASH_BOUND",
        "SECTOR_PIT_MEMBERSHIP_UNVERIFIED",
    ]
    if fund_bytes_verified:
        remaining_data_gaps.extend(list(verified.get('remaining_data_gaps') or []))
    else:
        remaining_data_gaps.extend([
            "FUND_FLOW_SOURCE_BYTES_NOT_VERIFIED_IN_CURRENT_RECOVERY",
            "FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE",
            "FUND_FLOW_PIT_KNOWN_AT_UNBOUND",
        ])

    return {
        "artifact": "GP12_SECTOR_FUND_SOURCE_PROVENANCE_V482",
        "version": "V4.82",
        "strategy_id": "GP_V11",
        "status": "PARTIAL_SOURCE_PROVENANCE_BOUND",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "historical_package": {
            "archive": "v11_offline_backtest_v3_10.zip",
            "archive_sha256": "d526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d",
            "scope": "DAILY_BASE_PLUS_INPUT_ADAPTERS_NOT_COMPLETE_12_FACTOR_STRATEGY",
        },
        "sector": {
            "adapter_path_recovered": True,
            "adapter_path": "src/prepare_datalake_silver.py",
            "adapter_sha256": "4e41c7f0da2de74f3243b3ab433c94c87fe38fc344eb4f87834d898afdbb2175",
            "documented_source_family": "leo-quant-research/data_lake Silver daily_panel",
            "passthrough_columns": ["citic_l1", "citic_l3"],
            "passthrough_semantics": "row-for-row passthrough when present in the upstream Silver panel",
            "source_snapshot_identity_locked": False,
            "source_bytes_materialized_and_hash_bound": False,
            "pit_membership_verified": False,
            "sector_series_construction_recovered": False,
            "factor_formula_recovered": False,
        },
        "fund_flow": fund_flow,
        "remaining_data_gaps": remaining_data_gaps,
        "remaining_contract_gaps": [
            "SECTOR_RS_BREADTH_SLOPE_NORMALIZATION_AND_AGGREGATION_MISSING",
            "PRICE_FUND_EFFICIENCY_FORMULA_PULSE_FILTER_AND_NORMALIZATION_MISSING",
        ],
        "historical_factor_formula_recovered": False,
        "data_completion_would_close_blocker_by_itself": False,
        "blocker": "PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE",
        "blocker_closed": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "next_engineering_actions": [
            "locate and hash-bind the exact historical Silver sector snapshot/membership source",
            "measure/extend fund-flow coverage to the full Formal window without forward fill",
            "recover fund-flow PIT known-at semantics rather than assuming same-day availability",
            "keep formula/normalization recovery as a separate historical-contract requirement",
        ],
    }
