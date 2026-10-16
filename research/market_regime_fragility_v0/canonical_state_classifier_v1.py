from __future__ import annotations

from state_resolution_v1 import STATE_TO_SCORE


CLASSIFIER_VERSION = "CANONICAL_STATE_CLASSIFIER_V1"

UNAVAILABLE_VALUES = {
    "external_shock": "UNAVAILABLE",
    "local_transmission_state": "UNRESOLVED",
    "breadth_state": "UNAVAILABLE",
    "leadership_state": "UNAVAILABLE",
    "small_mid_state": "UNAVAILABLE",
    "turnover_state": "UNAVAILABLE",
    "repair_state": "UNAVAILABLE",
}


def _result(
    *,
    state: str,
    reason_codes: list[str],
    ledger_result: dict,
    available: bool,
) -> dict:
    return {
        "classifier_version": CLASSIFIER_VERSION,
        "canonical_market_state": state,
        "risk_evidence_score": STATE_TO_SCORE.get(state) if available else None,
        "reason_codes": list(reason_codes),
        "missing_fields": list(ledger_result.get("missing_fields") or []),
        "invalid_fields": list(ledger_result.get("invalid_fields") or []),
        "evidence_hash": ledger_result.get("evidence_hash"),
        "full_classifier_resolution_available": bool(available),
        "production_authorized": False,
    }


def classify_canonical_state(ledger_result: dict) -> dict:
    """Resolve an existing categorical evidence ledger into one canonical state.

    This classifier consumes categorical PIT evidence only. It does not derive
    categories from numeric market data and it never authorizes production use.
    """
    if not isinstance(ledger_result, dict) or ledger_result.get("valid") is not True:
        reasons = list((ledger_result or {}).get("reason_codes") or []) if isinstance(ledger_result, dict) else []
        if "REQUIRED_EVIDENCE_UNAVAILABLE" not in reasons:
            reasons.append("REQUIRED_EVIDENCE_UNAVAILABLE")
        return _result(
            state="UNAVAILABLE",
            reason_codes=reasons,
            ledger_result=ledger_result if isinstance(ledger_result, dict) else {},
            available=False,
        )

    evidence = ledger_result.get("normalized_evidence") or {}

    unavailable_fields = [
        field
        for field, unavailable_value in UNAVAILABLE_VALUES.items()
        if evidence.get(field, {}).get("value") == unavailable_value
    ]
    if unavailable_fields:
        result = _result(
            state="UNAVAILABLE",
            reason_codes=["REQUIRED_EVIDENCE_UNAVAILABLE"],
            ledger_result=ledger_result,
            available=False,
        )
        result["invalid_fields"] = sorted(set(result["invalid_fields"] + unavailable_fields))
        return result

    values = {field: item.get("value") for field, item in evidence.items()}

    external = values.get("external_shock")
    source = values.get("shock_source_persistence")
    transmission = values.get("local_transmission_state")
    breadth = values.get("breadth_state")
    leadership = values.get("leadership_state")
    small_mid = values.get("small_mid_state")
    turnover = values.get("turnover_state")
    repair = values.get("repair_state")

    contradictory = (
        (external == "ABSENT" and source in {"SOURCE_ONGOING", "SOURCE_ESCALATING"})
        or (transmission == "PENDING_TRANSMISSION" and repair == "BROAD")
    )
    if contradictory:
        return _result(
            state="UNAVAILABLE",
            reason_codes=["CONTRADICTORY_REQUIRED_EVIDENCE"],
            ledger_result=ledger_result,
            available=False,
        )

    severe_broad_channels = sum(
        [
            breadth == "DETERIORATING",
            leadership == "DETERIORATING",
            small_mid == "STRESSED",
        ]
    )

    if turnover == "DISTRIBUTION" and severe_broad_channels >= 2:
        return _result(
            state="ACTIVE_DE_RISKING",
            reason_codes=["ACTIVE_DISTRIBUTION_CONFIRMED"],
            ledger_result=ledger_result,
            available=True,
        )

    if (
        external == "VERIFIED"
        and source in {"SOURCE_ONGOING", "SOURCE_ESCALATING"}
        and transmission in {"PENDING_TRANSMISSION", "IN_TRANSMISSION", "REALIZED_SHOCK"}
    ):
        return _result(
            state="EXTERNAL_SHOCK",
            reason_codes=["VERIFIED_EXTERNAL_SHOCK_UNRESOLVED"],
            ledger_result=ledger_result,
            available=True,
        )

    severe_channels = sum(
        [
            breadth == "DETERIORATING",
            leadership == "DETERIORATING",
            small_mid == "STRESSED",
            turnover in {"LIQUIDITY_WITHDRAWAL", "DISTRIBUTION"},
        ]
    )
    if severe_channels >= 3:
        return _result(
            state="INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY",
            reason_codes=["MULTI_CHANNEL_FRAGILITY_HIGH"],
            ledger_result=ledger_result,
            available=True,
        )

    mild_channels = sum(
        [
            breadth in {"DIVERGENT", "DETERIORATING"},
            leadership in {"CONCENTRATED", "DETERIORATING"},
            small_mid in {"WEAK", "STRESSED"},
            turnover == "LIQUIDITY_WITHDRAWAL",
        ]
    )
    if mild_channels >= 2:
        return _result(
            state="INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY",
            reason_codes=["MULTI_CHANNEL_FRAGILITY_LOW"],
            ledger_result=ledger_result,
            available=True,
        )

    if repair == "BROAD" or (transmission == "REPAIRING" and repair in {"PARTIAL", "BROAD"}):
        return _result(
            state="REPAIR",
            reason_codes=["BROAD_REPAIR_CONFIRMED"],
            ledger_result=ledger_result,
            available=True,
        )

    if mild_channels == 1:
        return _result(
            state="INTERNAL_FRAGILITY_WATCH",
            reason_codes=["FRAGILITY_WATCH_ONLY"],
            ledger_result=ledger_result,
            available=True,
        )

    all_healthy = (
        external == "ABSENT"
        and source in {"SOURCE_RESOLVING", "SOURCE_TRANSIENT_REPRICING", "SOURCE_UNVERIFIED"}
        and breadth == "HEALTHY"
        and leadership == "HEALTHY"
        and small_mid == "HEALTHY"
        and turnover == "HEALTHY"
        and repair == "NONE"
    )
    if all_healthy:
        return _result(
            state="NORMAL_RISK_ON",
            reason_codes=["RISK_ON_EVIDENCE_SET"],
            ledger_result=ledger_result,
            available=True,
        )

    return _result(
        state="NORMAL",
        reason_codes=["NORMAL_EVIDENCE_SET"],
        ledger_result=ledger_result,
        available=True,
    )
