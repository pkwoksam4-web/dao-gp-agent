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


def build_sector_fund_source_provenance() -> dict:
    """Bind only source facts already recovered from historical V3.10.

    This deliberately does not promote source clues into PIT factor provenance.
    The fund-flow snapshot target has a historical byte identity contract, but
    its bytes/full Formal-window coverage are not established here. Sector
    labels are only known as passthrough columns from a Silver adapter; their
    historical snapshot/membership authority remains unbound.
    """
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
        "fund_flow": {
            "adapter_path_recovered": True,
            "adapter_path": "src/prepare_ashare21_hf.py",
            "adapter_sha256": "739e5e24a817283dcd6234e067a73c2ee12b46cb1e13bd9e3857cf864ec3cfe7",
            "snapshot_fetcher_path": "src/fetch_ashare21_snapshot.py",
            "repo_id": "ellendan/a-share-21",
            "filename": "all-prices-with-values-250423.csv",
            "expected_size_bytes": 2134704074,
            "expected_sha256": "034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea",
            "candidate_snapshot_identity_locked": True,
            "actual_snapshot_bytes_verified_in_current_recovery": False,
            "auto_converted_hf_parquet_allowed": False,
            "snapshot_policy": "EXACTLY_ONE_ORIGINAL_SOURCE_SNAPSHOT_FAIL_CLOSED",
            "preserved_flow_columns": list(FLOW_COLUMNS),
            "documented_public_coverage": ["2021-01-01", "2025-02-27"],
            "documented_public_coverage_precision": "APPROXIMATE_HISTORICAL_PACKAGE_DOCUMENTATION",
            "formal_window_coverage_complete": False,
            "pit_known_at_semantics_recovered": False,
            "pit_provenance_complete": False,
            "factor_formula_recovered": False,
        },
        "remaining_data_gaps": [
            "SECTOR_SOURCE_SNAPSHOT_IDENTITY_UNBOUND",
            "SECTOR_SOURCE_BYTES_NOT_HASH_BOUND",
            "SECTOR_PIT_MEMBERSHIP_UNVERIFIED",
            "FUND_FLOW_SOURCE_BYTES_NOT_VERIFIED_IN_CURRENT_RECOVERY",
            "FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE",
            "FUND_FLOW_PIT_KNOWN_AT_UNBOUND",
        ],
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
            "locate_and hash-bind the exact historical Silver sector snapshot/membership source",
            "materialize or independently verify the locked a-share-21 original snapshot bytes",
            "measure actual date/symbol coverage against the Formal window without forward fill",
            "keep formula/normalization recovery as a separate historical-contract requirement",
        ],
    }
