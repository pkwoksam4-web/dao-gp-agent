from __future__ import annotations

STATE_TO_SCORE = {
    "NORMAL_RISK_ON": 0,
    "NORMAL": 1,
    "INTERNAL_FRAGILITY_WATCH": 1,
    "INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY": 2,
    "INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY": 3,
    "EXTERNAL_SHOCK": 2,
    "ACTIVE_DE_RISKING": 3,
    "REPAIR": 1,
}

PENDING_TRANSMISSION = "PENDING_TRANSMISSION"
SOURCE_ONGOING = "SOURCE_ONGOING"
SOURCE_ESCALATING = "SOURCE_ESCALATING"
OVERHEATED = "OVERHEATED"


def resolve_decision_state(
    *,
    canonical_market_state: str | None,
    data_valid: bool,
    shock_source_persistence: str | None = None,
    local_transmission_state: str | None = None,
    theme_state: str | None = None,
    lifecycle_state: str | None = None,
) -> dict:
    """Apply preregistered categorical conflict/veto semantics.

    This module deliberately does not classify raw market evidence into a
    canonical state. It consumes already-resolved categorical states and makes
    their downstream restrictions explicit without inventing numeric thresholds.
    """
    if data_valid is not True:
        return {
            "canonical_market_state": canonical_market_state,
            "theme_state": theme_state,
            "lifecycle_state": lifecycle_state,
            "risk_evidence_score": None,
            "block_new_high_beta_attack": False,
            "force_liquidate_all": False,
            "chase_veto_active": lifecycle_state == OVERHEATED,
            "full_architecture_approval_available": False,
            "reason": "DATA_UNAVAILABLE",
        }

    if canonical_market_state not in STATE_TO_SCORE:
        return {
            "canonical_market_state": canonical_market_state,
            "theme_state": theme_state,
            "lifecycle_state": lifecycle_state,
            "risk_evidence_score": None,
            "block_new_high_beta_attack": False,
            "force_liquidate_all": False,
            "chase_veto_active": lifecycle_state == OVERHEATED,
            "full_architecture_approval_available": False,
            "reason": "CANONICAL_STATE_UNRESOLVED",
        }

    market_veto = canonical_market_state == "ACTIVE_DE_RISKING"
    pending_external_veto = (
        local_transmission_state == PENDING_TRANSMISSION
        and shock_source_persistence in {SOURCE_ONGOING, SOURCE_ESCALATING}
    )

    return {
        "canonical_market_state": canonical_market_state,
        "theme_state": theme_state,
        "lifecycle_state": lifecycle_state,
        "risk_evidence_score": STATE_TO_SCORE[canonical_market_state],
        "block_new_high_beta_attack": bool(market_veto or pending_external_veto),
        "force_liquidate_all": False,
        "chase_veto_active": lifecycle_state == OVERHEATED,
        "full_architecture_approval_available": True,
        "reason": None,
    }
