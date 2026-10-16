from __future__ import annotations

EXPECTED_BASELINE_VERSION = "MOMENTUM_VOL_REGIME_V1"
EXPECTED_SCORE_MAPPING_VERSION = "RISK_EVIDENCE_SCORE_MAPPING_V1"
EXPECTED_INFERENCE_VERSION = "PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1"
EXPECTED_POWER_PLAN_VERSION = "POWER_SAMPLE_PLAN_V1"
EXPECTED_ATOMIC_LEDGER_VERSION = "ATOMIC_EVIDENCE_LEDGER_V1"
EXPECTED_TRADABILITY_POLICY_VERSION = "A_SHARE_TRADABILITY_GATE_V1"
EXPECTED_PRIMARY_HORIZON = 3
EXPECTED_PRIMARY_ALPHA = 0.05
EXPECTED_DATA_CUTOFF_POLICY = "COMPLETED_SESSION_ONLY"


def _positive_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def check_manifest(manifest: dict) -> dict:
    reasons: list[str] = []

    if manifest.get("baseline_version") != EXPECTED_BASELINE_VERSION:
        reasons.append("BASELINE_VERSION_MISMATCH")
    if manifest.get("score_mapping_version") != EXPECTED_SCORE_MAPPING_VERSION:
        reasons.append("SCORE_MAPPING_VERSION_MISMATCH")
    if manifest.get("inference_version") != EXPECTED_INFERENCE_VERSION:
        reasons.append("INFERENCE_VERSION_MISMATCH")
    if manifest.get("power_plan_version") != EXPECTED_POWER_PLAN_VERSION:
        reasons.append("POWER_PLAN_VERSION_MISMATCH")
    if manifest.get("atomic_ledger_version") != EXPECTED_ATOMIC_LEDGER_VERSION:
        reasons.append("ATOMIC_LEDGER_VERSION_MISMATCH")
    if manifest.get("primary_horizon_sessions") != EXPECTED_PRIMARY_HORIZON:
        reasons.append("PRIMARY_HORIZON_MISMATCH")
    if manifest.get("primary_alpha") != EXPECTED_PRIMARY_ALPHA:
        reasons.append("PRIMARY_ALPHA_MISMATCH")
    if manifest.get("data_cutoff_policy") != EXPECTED_DATA_CUTOFF_POLICY:
        reasons.append("DATA_CUTOFF_POLICY_MISMATCH")

    target_power = manifest.get("target_power")
    if not isinstance(target_power, (int, float)) or isinstance(target_power, bool) or not (0 < target_power < 1):
        reasons.append("TARGET_POWER_NOT_FROZEN")

    minimum_effect = manifest.get("minimum_effect_delta_tau")
    if not _positive_number(minimum_effect):
        reasons.append("MINIMUM_EFFECT_NOT_FROZEN")

    minimum_sample = manifest.get("minimum_sample_required")
    if not isinstance(minimum_sample, int) or isinstance(minimum_sample, bool) or minimum_sample < 2:
        reasons.append("MINIMUM_SAMPLE_NOT_FROZEN")

    if manifest.get("unused_set") is not True:
        reasons.append("EVALUATION_SET_NOT_MARKED_UNUSED")
    if manifest.get("definitions_locked_before_set_open") is not True:
        reasons.append("DEFINITIONS_NOT_LOCKED_BEFORE_SET_OPEN")

    evaluation_set_id = manifest.get("evaluation_set_id")
    if not evaluation_set_id:
        reasons.append("EVALUATION_SET_ID_MISSING")
    if not manifest.get("evaluation_set_hash"):
        reasons.append("EVALUATION_SET_HASH_MISSING")

    consumed = set(manifest.get("consumed_set_ids") or [])
    if evaluation_set_id and evaluation_set_id in consumed:
        reasons.append("EVALUATION_SET_ALREADY_CONSUMED")

    if not manifest.get("complex_classifier_version"):
        reasons.append("COMPLEX_CLASSIFIER_VERSION_MISSING")
    if not manifest.get("complex_classifier_hash"):
        reasons.append("COMPLEX_CLASSIFIER_HASH_MISSING")
    if manifest.get("classifier_ledger_pit_valid") is not True:
        reasons.append("CLASSIFIER_LEDGER_NOT_PIT_VALID")
    if not manifest.get("classifier_evidence_hash"):
        reasons.append("CLASSIFIER_EVIDENCE_HASH_MISSING")

    if not manifest.get("universe_snapshot_hash"):
        reasons.append("UNIVERSE_SNAPSHOT_HASH_MISSING")
    if manifest.get("universe_pit_valid") is not True:
        reasons.append("UNIVERSE_NOT_PIT_VALID")
    if manifest.get("tradability_policy_version") != EXPECTED_TRADABILITY_POLICY_VERSION:
        reasons.append("TRADABILITY_POLICY_VERSION_MISMATCH")
    if manifest.get("tradability_filter_applied_before_ranking") is not True:
        reasons.append("TRADABILITY_FILTER_NOT_APPLIED_BEFORE_RANKING")
    if not manifest.get("market_structure_regime_schedule_version"):
        reasons.append("MARKET_STRUCTURE_REGIME_SCHEDULE_VERSION_MISSING")

    return {
        "eligible": not reasons,
        "reasons": reasons,
        "production_authorized": False,
        "preflight_scope": "FORMAL_EVALUATION_ONLY",
    }
