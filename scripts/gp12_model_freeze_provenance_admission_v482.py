from __future__ import annotations


EXPECTED_POLICY_GAPS = {
    "full_gp12_three_way_probability_mapping",
    "ranking_topn_semantics",
    "entry_exit_thresholds",
    "holding_and_rebalance_policy",
    "position_sizing_and_risk_rules",
    "actual_fill_price_and_intraday_execution_rules",
}

CANONICAL_BLOCKER_ORDER = [
    "COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING",
    "EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING",
    "PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE",
    "FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING",
    "RANKING_TOPN_SEMANTICS_MISSING",
    "ENTRY_EXIT_THRESHOLDS_MISSING",
    "HOLDING_REBALANCE_POLICY_MISSING",
    "POSITION_SIZING_AND_RISK_RULES_MISSING",
    "ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING",
    "FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING",
]


def _validate_feature_gate(label: dict) -> None:
    p = label.get("promotion") or {}
    ok = (
        label.get("status") == "PASS_LABEL_PROVENANCE_ADMISSION"
        and p.get("adjusted_close_blocker_closed") is True
        and p.get("turnover_ratio_blocker_closed") is True
        and p.get("label_provenance_blocker_closed") is True
        and p.get("formal_feature_ready") is True
        and p.get("model_freeze_allowed") is False
        and p.get("oos_metrics_allowed") is False
    )
    if not ok:
        raise ValueError("formal feature provenance gate is not fully closed")


def _validate_calendar(calendar: dict) -> None:
    hashes = [
        calendar.get("official_evidence_sha256"),
        calendar.get("formal_calendar_sha256"),
        calendar.get("oos_calendar_sha256"),
        calendar.get("calendar_sha256"),
    ]
    ok = (
        calendar.get("status") == "OOS_CALENDAR_READY_V482"
        and calendar.get("formal_date_n") == 1426
        and calendar.get("oos_date_n") == 98
        and calendar.get("total_date_n") == 1524
        and calendar.get("first_oos_trade_date") == "2026-04-20"
        and calendar.get("last_oos_trade_date") == "2026-09-08"
        and all(isinstance(x, str) and len(x) == 64 for x in hashes)
    )
    if not ok:
        raise ValueError("official OOS calendar provenance is not exact")


def _strategy_complete(strategy: dict) -> bool:
    assets = strategy.get("recovered_assets") or []
    return bool(assets) and all(x.get("complete_12_factor_strategy") is True for x in assets) and not (strategy.get("missing_required_fields") or [])


def _validate_recovery_consistency(strategy: dict, factor: dict, decision: dict, intraday: dict) -> None:
    missing = set(strategy.get("missing_required_fields") or [])
    policy_gaps = set(decision.get("remaining_policy_gaps") or [])
    if factor.get("complete_factor_definitions_recovered") is True and (
        "non_daily_layer_factor_formulas" in missing
        or "exact_normalization_and_clipping" in missing
        or "score_layer_aggregation" in missing
    ):
        raise ValueError("inconsistent factor recovery claim")
    if factor.get("full_strategy_source_recovered") is True and "complete_12_factor_strategy_code_bytes" in missing:
        raise ValueError("inconsistent full-strategy source recovery claim")
    if decision.get("full_parameter_set_recovered") is True and (policy_gaps - {"full_gp12_three_way_probability_mapping"}):
        raise ValueError("inconsistent parameter-set recovery claim")
    if decision.get("full_strategy_probability_mapping_recovered") is True and "full_gp12_three_way_probability_mapping" in policy_gaps:
        raise ValueError("inconsistent probability recovery claim")
    if intraday.get("formal_847_minute_byte_coverage_verified") is True and (
        intraday.get("formal_847_15m_coverage_verified") is not True
        or intraday.get("formal_847_60m_coverage_verified") is not True
    ):
        raise ValueError("inconsistent intraday coverage claim")


def build_model_freeze_provenance_admission(
    label: dict,
    calendar: dict,
    strategy: dict,
    factor: dict,
    decision: dict,
    intraday: dict,
) -> dict:
    _validate_feature_gate(label)
    _validate_calendar(calendar)

    if strategy.get("artifact") != "GP_V11_STRATEGY_RECOVERY_EVIDENCE_V482" or strategy.get("strategy_id") != "GP_V11":
        raise ValueError("strategy recovery evidence identity mismatch")
    if factor.get("artifact") != "GP_V11_FACTOR_RECOVERY_MATRIX_V482":
        raise ValueError("factor recovery evidence identity mismatch")
    if decision.get("artifact") != "GP_V11_DECISION_POLICY_RECOVERY_MATRIX_V482":
        raise ValueError("decision policy recovery evidence identity mismatch")
    if intraday.get("artifact") != "GP_V11_INTRADAY_SOURCE_RECOVERY_V482":
        raise ValueError("intraday recovery evidence identity mismatch")

    _validate_recovery_consistency(strategy, factor, decision, intraday)

    missing = set(strategy.get("missing_required_fields") or [])
    policy_gaps = set(decision.get("remaining_policy_gaps") or [])
    blockers = []

    if not _strategy_complete(strategy) or "complete_12_factor_strategy_code_bytes" in missing:
        blockers.append("COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING")

    if (
        factor.get("complete_factor_definitions_recovered") is not True
        or "non_daily_layer_factor_formulas" in missing
        or "exact_normalization_and_clipping" in missing
        or "score_layer_aggregation" in missing
    ):
        blockers.append("EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING")

    sector = factor.get("sector_membership_partial_source") or {}
    fund = factor.get("fund_flow_partial_source") or {}
    if (
        sector.get("pit_membership_verified") is not True
        or sector.get("factor_formula_recovered") is not True
        or fund.get("factor_formula_recovered") is not True
        or "non_daily_layer_source_bytes" in missing
    ):
        blockers.append("PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE")

    if (
        decision.get("full_strategy_probability_mapping_recovered") is not True
        or "full_gp12_three_way_probability_mapping" in policy_gaps
        or "probability_mapping" in missing
    ):
        blockers.append("FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING")
    if "ranking_topn_semantics" in policy_gaps or "ranking_topn_semantics" in missing:
        blockers.append("RANKING_TOPN_SEMANTICS_MISSING")
    if "entry_exit_thresholds" in policy_gaps or "entry_exit_thresholds" in missing:
        blockers.append("ENTRY_EXIT_THRESHOLDS_MISSING")
    if "holding_and_rebalance_policy" in policy_gaps or "holding_and_rebalance_policy" in missing:
        blockers.append("HOLDING_REBALANCE_POLICY_MISSING")
    if "position_sizing_and_risk_rules" in policy_gaps or "position_sizing_and_risk_rules" in missing:
        blockers.append("POSITION_SIZING_AND_RISK_RULES_MISSING")
    if "actual_fill_price_and_intraday_execution_rules" in policy_gaps:
        blockers.append("ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING")

    intraday_incomplete = (
        intraday.get("formal_847_minute_byte_coverage_verified") is not True
        or intraday.get("formal_847_15m_coverage_verified") is not True
        or intraday.get("formal_847_60m_coverage_verified") is not True
        or intraday.get("resampling_contract_recovered") is not True
        or intraday.get("factor_formula_recovered") is not True
    )
    if intraday_incomplete:
        blockers.append("FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING")

    blockers = [x for x in CANONICAL_BLOCKER_ORDER if x in set(blockers)]
    provenance_complete = len(blockers) == 0

    # This checkpoint is deliberately fail-closed. Even if a later recovery
    # removes every blocker, a separate promotion gate must freeze exact bytes
    # and hashes before Model Freeze or OOS may open.
    status = "BLOCKED_MODEL_FREEZE_PROVENANCE" if blockers else "REVIEW_MODEL_FREEZE_PROMOTION_REQUIRED"

    return {
        "artifact": "GP12_MODEL_FREEZE_PROVENANCE_CHECKPOINT_V482",
        "version": "V4.82",
        "strategy_id": "GP_V11",
        "status": status,
        "formal_feature_ready": True,
        "oos_calendar_ready": True,
        "old_oos_calendar_blocker_closed": True,
        "strategy_provenance_complete": provenance_complete,
        "authoritative_weight_vector_recovered": factor.get("authoritative_weight_vector_recovered") is True,
        "daily_base_source_recovered": True,
        "candidate_substitution_allowed": False,
        "candidate_policy_values_historical_authority": False,
        "remaining_blockers": blockers,
        "recovery_state": {
            "complete_12_factor_strategy_source": _strategy_complete(strategy),
            "complete_factor_definitions": factor.get("complete_factor_definitions_recovered") is True,
            "full_strategy_source": factor.get("full_strategy_source_recovered") is True,
            "full_parameter_set": decision.get("full_parameter_set_recovered") is True,
            "full_gp12_probability_mapping": decision.get("full_strategy_probability_mapping_recovered") is True,
            "formal847_minute_inventory_membership": intraday.get("formal_847_minute_inventory_membership_verified") is True,
            "formal847_minute_byte_coverage": intraday.get("formal_847_minute_byte_coverage_verified") is True,
            "formal847_15m_coverage": intraday.get("formal_847_15m_coverage_verified") is True,
            "formal847_60m_coverage": intraday.get("formal_847_60m_coverage_verified") is True,
            "historical_intraday_resampling_contract": intraday.get("resampling_contract_recovered") is True,
            "intraday_factor_formula": intraday.get("factor_formula_recovered") is True,
        },
        "calendar": {
            "formal_date_n": calendar.get("formal_date_n"),
            "oos_date_n": calendar.get("oos_date_n"),
            "total_date_n": calendar.get("total_date_n"),
            "first_oos_trade_date": calendar.get("first_oos_trade_date"),
            "last_oos_trade_date": calendar.get("last_oos_trade_date"),
            "official_evidence_sha256": calendar.get("official_evidence_sha256"),
            "oos_calendar_sha256": calendar.get("oos_calendar_sha256"),
            "calendar_sha256": calendar.get("calendar_sha256"),
        },
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "next_gate": "RECOVER_OR_EXPLICITLY_APPROVE_COMPLETE_GP_V11_STRATEGY_CONTRACT",
    }
