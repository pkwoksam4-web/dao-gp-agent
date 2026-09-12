from __future__ import annotations


HISTORICAL_CONTRACT_BLOCKERS = [
    "COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING",
    "EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING",
    "FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING",
    "RANKING_TOPN_SEMANTICS_MISSING",
    "ENTRY_EXIT_THRESHOLDS_MISSING",
    "HOLDING_REBALANCE_POLICY_MISSING",
    "POSITION_SIZING_AND_RISK_RULES_MISSING",
    "ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING",
]

MIXED_DATA_AND_CONTRACT_BLOCKERS = [
    "PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE",
    "FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING",
]

POLICY_HIT_TO_BLOCKER = {
    "full_three_way_prob": "FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING",
    "topn_policy": "RANKING_TOPN_SEMANTICS_MISSING",
    "entry_exit_policy": "ENTRY_EXIT_THRESHOLDS_MISSING",
    "holding_rebalance": "HOLDING_REBALANCE_POLICY_MISSING",
    "position_sizing": "POSITION_SIZING_AND_RISK_RULES_MISSING",
    "intraday_formula": "ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING",
}


def _validate_checkpoint(checkpoint: dict) -> None:
    ok = (
        checkpoint.get("artifact") == "GP12_MODEL_FREEZE_PROVENANCE_CHECKPOINT_V482"
        and checkpoint.get("strategy_id") == "GP_V11"
        and checkpoint.get("status") == "BLOCKED_MODEL_FREEZE_PROVENANCE"
        and checkpoint.get("formal_feature_ready") is True
        and checkpoint.get("oos_calendar_ready") is True
        and checkpoint.get("model_freeze_allowed") is False
        and checkpoint.get("oos_metrics_allowed") is False
    )
    if not ok:
        raise ValueError("Model Freeze checkpoint is not fail-closed")


def _validate_archive_audit(audit: dict) -> list[dict]:
    if audit.get("artifact") != "GP12_HISTORICAL_ARCHIVE_EXHAUSTION_V482" or audit.get("strategy_id") != "GP_V11":
        raise ValueError("archive audit identity mismatch")
    if audit.get("accessible_archive_lineage_complete") is not True:
        raise ValueError("archive lineage is not complete")
    archives = audit.get("archives") or []
    if audit.get("archive_count") != len(archives) or len(archives) != 13:
        raise ValueError("archive lineage count mismatch")
    names = [x.get("name") for x in archives]
    if len(set(names)) != len(names):
        raise ValueError("archive lineage contains duplicate names")
    for x in archives:
        sha = x.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha.lower()):
            raise ValueError("archive sha256 is not bound")
    if audit.get("historical_conversation_contract_search_complete") is not True:
        raise ValueError("historical conversation contract search is incomplete")
    return archives


def build_model_freeze_recovery_triage(checkpoint: dict, archive_audit: dict) -> dict:
    _validate_checkpoint(checkpoint)
    archives = _validate_archive_audit(archive_audit)

    remaining = checkpoint.get("remaining_blockers") or []
    remaining_set = set(remaining)
    expected = set(HISTORICAL_CONTRACT_BLOCKERS + MIXED_DATA_AND_CONTRACT_BLOCKERS)
    if remaining_set != expected or len(remaining) != 10:
        raise ValueError("canonical Model Freeze blocker set mismatch")

    targeted_reinspection = []
    historical = []
    for blocker in HISTORICAL_CONTRACT_BLOCKERS:
        matching_keys = [k for k, v in POLICY_HIT_TO_BLOCKER.items() if v == blocker]
        has_hit = False
        for a in archives:
            kp = a.get("keyword_presence") or {}
            if any(kp.get(k) is True for k in matching_keys):
                has_hit = True
                break
        if has_hit:
            targeted_reinspection.append(blocker)
        else:
            historical.append(blocker)

    explicit_daily_n = sum(1 for a in archives if a.get("explicit_daily_base_scope") is True)
    conversation_missing = archive_audit.get("historical_conversation_found_missing_policy_contract") is False
    accessible_exhausted = (
        len(targeted_reinspection) == 0
        and explicit_daily_n == archive_audit.get("explicit_daily_base_scope_archive_n")
        and explicit_daily_n >= 10
        and conversation_missing
    )

    return {
        "artifact": "GP12_MODEL_FREEZE_RECOVERY_TRIAGE_V482",
        "version": "V4.82",
        "strategy_id": "GP_V11",
        "status": "RECOVERY_TRIAGED_MODEL_FREEZE_BLOCKED",
        "accessible_historical_archive_lineage_exhausted": accessible_exhausted,
        "historical_gp_v11_freeze_possible_from_accessible_archives": False if accessible_exhausted else None,
        "historical_contract_blockers": historical,
        "mixed_data_and_contract_blockers": list(MIXED_DATA_AND_CONTRACT_BLOCKERS),
        "pure_engineering_blockers": [],
        "requires_targeted_reinspection": targeted_reinspection,
        "archive_evidence": {
            "archive_count": len(archives),
            "explicit_daily_base_scope_archive_n": explicit_daily_n,
            "all_archive_sha256_bound": True,
            "historical_conversation_contract_search_complete": True,
            "historical_conversation_found_missing_policy_contract": archive_audit.get("historical_conversation_found_missing_policy_contract"),
        },
        "engineering_workstreams": [
            {
                "blocker": "PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE",
                "recoverable_component": "materialize and PIT-audit sector membership/series and historical fund-flow inputs",
                "non_engineering_component": "historical factor formula/normalization still requires original authority or a newly approved contract",
            },
            {
                "blocker": "FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING",
                "recoverable_component": "materialize Formal847 minute bytes and prove 15m/60m coverage",
                "non_engineering_component": "historical resampling/confirmation formula still requires original authority or a newly approved contract",
            },
        ],
        "candidate_substitution_allowed": False,
        "if_rebuild_is_approved": {
            "strategy_identity_rule": "MUST_NOT_CLAIM_GP_V11_HISTORICAL_IDENTITY",
            "require_new_frozen_contract": True,
            "require_new_hash_bound_model_freeze": True,
            "reuse_existing_formal_feature_evidence": True,
            "reuse_existing_oos_calendar_evidence": True,
            "oos_contamination_review_required_before_any_metric": True,
        },
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "next_gate": "ENGINEER_RECOVERABLE_PROVENANCE_AND_SEARCH_EXTERNAL_ORIGINAL_CONTRACT",
    }
