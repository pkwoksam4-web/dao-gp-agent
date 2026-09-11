from __future__ import annotations

import math
from typing import Iterable


FORMAL_BEG = "2020-06-01"
FORMAL_END = "2026-04-17"
FORMAL_WINDOW = [FORMAL_BEG, FORMAL_END]
EXPECTED_ROWS = {1: 1010002, 2: 1008825, 3: 1007667}
SOURCE_SEMANTICS = "V4.82_proven_horizon_local_action_neutral"
EXPECTED_QFQ_CHECKPOINT = {
    "PASS": 844,
    "EXACT_TERM_REVIEW": 0,
    "MISSING_EVENT_REVIEW": 0,
    "NOT_APPLICABLE": 3,
}
METHOD = (
    "Apply only V4.82-proven event ratios with T < ex_date <= target_date; "
    "exclude events after target_date."
)


def _num(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _label(target: float, reference: float) -> str:
    if target > reference:
        return "UP"
    if target < reference:
        return "DOWN"
    return "FLAT"


def audit_action_neutral_label_rows(
    rows: Iterable[dict], horizon: int, *, file_sha256: str
) -> dict:
    data = [dict(r) for r in rows]
    seen = set()
    duplicate_n = 0
    invalid_numeric_n = 0
    horizon_mismatch_n = 0
    target_nonforward_n = 0
    target_oos_n = 0
    source_semantics_mismatch_n = 0
    invalid_label_n = 0
    formula_mismatch_n = 0
    label_mismatch_n = 0

    for row in data:
        symbol = str(row.get("symbol") or "").strip().upper()
        date = str(row.get("date") or "").strip()[:10]
        target_date = str(row.get("target_date") or "").strip()[:10]
        key = (symbol, date)
        if not symbol or len(date) != 10 or key in seen:
            duplicate_n += 1
        seen.add(key)

        try:
            row_h = int(row.get("horizon_market_sessions"))
        except (TypeError, ValueError):
            row_h = None
        if row_h != int(horizon):
            horizon_mismatch_n += 1

        if len(target_date) != 10 or target_date <= date:
            target_nonforward_n += 1
        if len(target_date) != 10 or target_date > FORMAL_END:
            target_oos_n += 1

        if str(row.get("source_semantics") or "") != SOURCE_SEMANTICS:
            source_semantics_mismatch_n += 1

        stored_label = str(row.get("label") or "")
        if stored_label not in {"UP", "DOWN", "FLAT"}:
            invalid_label_n += 1

        close = _num(row.get("close"))
        target_close = _num(row.get("target_close"))
        product = _num(row.get("event_ratio_product"))
        stored_ref = _num(row.get("action_neutral_reference_close"))
        if (
            close is None
            or target_close is None
            or product is None
            or stored_ref is None
            or close <= 0
            or target_close <= 0
            or product <= 0
            or stored_ref <= 0
        ):
            invalid_numeric_n += 1
            continue

        expected_ref = close * product
        if not math.isclose(stored_ref, expected_ref, rel_tol=1e-12, abs_tol=1e-12):
            formula_mismatch_n += 1
        if stored_label != _label(target_close, expected_ref):
            label_mismatch_n += 1

    fail_n = sum(
        (
            duplicate_n,
            invalid_numeric_n,
            horizon_mismatch_n,
            target_nonforward_n,
            target_oos_n,
            source_semantics_mismatch_n,
            invalid_label_n,
            formula_mismatch_n,
            label_mismatch_n,
        )
    )
    return {
        "status": (
            "PASS_ACTION_NEUTRAL_LABEL_ROWS"
            if fail_n == 0
            else "REVIEW_ACTION_NEUTRAL_LABEL_ROWS"
        ),
        "horizon": int(horizon),
        "rows": len(data),
        "unique_symbol_date_n": len(seen),
        "duplicate_symbol_date_n": duplicate_n,
        "invalid_numeric_n": invalid_numeric_n,
        "horizon_mismatch_n": horizon_mismatch_n,
        "target_nonforward_n": target_nonforward_n,
        "target_oos_n": target_oos_n,
        "source_semantics_mismatch_n": source_semantics_mismatch_n,
        "invalid_label_n": invalid_label_n,
        "formula_mismatch_n": formula_mismatch_n,
        "label_mismatch_n": label_mismatch_n,
        "file_sha256": str(file_sha256),
    }


def _validate_raw_probe(raw: dict) -> None:
    inv = raw.get("invariants") or {}
    promo = raw.get("promotion") or {}
    horizons = {int(x.get("horizon_market_sessions", -1)): x for x in raw.get("horizons") or []}
    ok = (
        raw.get("status") == "PASS_LITERAL_RAW_CLOSE_LABEL_PROVENANCE_PROBE"
        and raw.get("formal_window") == FORMAL_WINDOW
        and set(horizons) == {1, 2, 3}
        and all(horizons[h].get("label_rows") == EXPECTED_ROWS[h] for h in EXPECTED_ROWS)
        and inv.get("oos_rows_consumed") == 0
        and inv.get("max_target_date") == FORMAL_END
        and inv.get("target_dates_never_shifted_for_missing_symbol_rows") is True
        and inv.get("source_symbol_date_duplicates") == 0
        and inv.get("zero_trade_symbols_emit_no_labels") is True
        and promo.get("historical_label_provenance_candidate_materialized") is True
        and promo.get("label_provenance_blocker_closed") is False
        and promo.get("candidate_adoption_status") == "UNAPPROVED"
        and promo.get("model_freeze_allowed") is False
        and promo.get("oos_metrics_allowed") is False
    )
    if not ok:
        raise ValueError("raw label provenance probe is not fail-closed and exact")


def _validate_candidate(candidate: dict) -> dict[int, dict]:
    inv = candidate.get("invariants") or {}
    promo = candidate.get("promotion") or {}
    horizons = {int(x.get("horizon", -1)): x for x in candidate.get("horizons") or []}
    ok = (
        candidate.get("status") == "PASS_V482_PROVENANCE_LABEL_CANDIDATE_MATERIALIZED"
        and candidate.get("formal_window") == FORMAL_WINDOW
        and candidate.get("formal_qfq_checkpoint") == EXPECTED_QFQ_CHECKPOINT
        and candidate.get("formal_full_path_pass_n") == 844
        and candidate.get("standard_override_n") == 270
        and candidate.get("special_override_n") == 11
        and candidate.get("total_override_n") == 281
        and candidate.get("method") == METHOD
        and set(horizons) == {1, 2, 3}
        and all(horizons[h].get("rows") == EXPECTED_ROWS[h] for h in EXPECTED_ROWS)
        and all(int(horizons[h].get("crossing_action_rows") or 0) > 0 for h in EXPECTED_ROWS)
        and all(int(horizons[h].get("raw_vs_neutral_diff_rows") or 0) > 0 for h in EXPECTED_ROWS)
        and inv.get("events_after_target_date_used") is False
        and inv.get("oos_rows_consumed") == 0
        and inv.get("max_target_date") == FORMAL_END
        and inv.get("all_281_overrides_bound_to_ledger") is True
        and promo.get("label_contract_approved") is False
        and promo.get("label_provenance_blocker_closed") is False
        and promo.get("candidate_adoption_status") == "UNAPPROVED"
        and promo.get("model_freeze_allowed") is False
        and promo.get("oos_metrics_allowed") is False
    )
    if not ok:
        raise ValueError("action-neutral label candidate is not exact or fail-closed")
    return horizons


def _validate_event_timing(event: dict) -> None:
    promo = event.get("promotion") or {}
    ok = (
        event.get("status") == "PASS_EVENT_TIMING_ADMISSION"
        and event.get("expected_n") == 2732
        and event.get("covered_n") == 2732
        and event.get("missing_n") == 0
        and event.get("extra_n") == 0
        and event.get("late_n") == 0
        and event.get("source_partition_exact") is True
        and promo.get("event_availability_time_verified") is True
    )
    if not ok:
        raise ValueError("event timing admission is not closed")


def _validate_override_timing(override: dict) -> None:
    promo = override.get("promotion") or {}
    ok = (
        override.get("status") == "PASS_OVERRIDE_TIMING_ADMISSION"
        and override.get("standard_expected_n") == 270
        and override.get("standard_pass_n") == 270
        and override.get("special_expected_n") == 11
        and override.get("special_pass_n") == 11
        and override.get("total_expected_n") == 281
        and override.get("total_pass_n") == 281
        and override.get("missing_n") == 0
        and override.get("binding_mismatch_n") == 0
        and override.get("late_n") == 0
        and override.get("missing_preopen_n") == 0
        and override.get("same_day_preopen_pass_n") == 2
        and promo.get("corrected_term_availability_time_verified") is True
    )
    if not ok:
        raise ValueError("override timing admission is not closed")


def _validate_adjusted_close(adjusted: dict) -> None:
    promo = adjusted.get("promotion") or {}
    ok = (
        adjusted.get("status") == "VALIDATED_GLOBAL_PROVENANCE"
        and promo.get("adjusted_close_blocker_closed") is True
        and promo.get("adjustment_provenance_blocker_closed") is True
        and promo.get("model_freeze_allowed") is False
        and promo.get("oos_metrics_allowed") is False
    )
    if not ok:
        raise ValueError("adjusted-close provenance gate is not closed")


def _validate_turnover(turnover: dict) -> None:
    scope = turnover.get("scope") or {}
    promo = turnover.get("promotion") or {}
    ok = (
        turnover.get("status") == "PASS_TURNOVER_RATIO_PIT_ADMISSION"
        and scope.get("universe_symbol_n") == 847
        and scope.get("row_bearing_symbol_n") == 844
        and scope.get("not_applicable_symbol_n") == 3
        and scope.get("trade_row_n") == 1011607
        and promo.get("turnover_ratio_pit_verified") is True
        and promo.get("turnover_ratio_blocker_closed") is True
        and promo.get("model_freeze_allowed") is False
        and promo.get("oos_metrics_allowed") is False
    )
    if not ok:
        raise ValueError("turnover provenance gate is not closed")


def _validate_row_audits(row_audits: Iterable[dict], candidate_h: dict[int, dict]) -> list[dict]:
    audits = [dict(x) for x in row_audits]
    by_h = {int(x.get("horizon", -1)): x for x in audits}
    if len(audits) != 3 or set(by_h) != {1, 2, 3}:
        raise ValueError("label row audit horizon partition is not exact")

    zero_fields = (
        "invalid_numeric_n",
        "horizon_mismatch_n",
        "target_nonforward_n",
        "target_oos_n",
        "source_semantics_mismatch_n",
        "invalid_label_n",
        "event_product_mismatch_n",
        "cross_flag_mismatch_n",
        "formula_mismatch_n",
        "label_mismatch_n",
    )
    for h in (1, 2, 3):
        a = by_h[h]
        expected_sha = str(candidate_h[h].get("output_sha256") or "")
        ok = (
            a.get("status") == "PASS_ACTION_NEUTRAL_LABEL_ROWS"
            and a.get("rows") == EXPECTED_ROWS[h]
            and a.get("unique_symbol_date_n") == EXPECTED_ROWS[h]
            and all(a.get(field, 0) == 0 for field in zero_fields)
            and str(a.get("file_sha256") or "") == expected_sha
            and len(expected_sha) == 64
        )
        if not ok:
            raise ValueError(f"label row audit H{h} is not exact")
    return [by_h[h] for h in (1, 2, 3)]


def build_label_provenance_admission(
    raw_probe: dict,
    candidate: dict,
    row_audits: Iterable[dict],
    event_timing: dict,
    override_timing: dict,
    adjusted_close: dict,
    turnover: dict,
) -> dict:
    _validate_raw_probe(raw_probe)
    candidate_h = _validate_candidate(candidate)
    _validate_event_timing(event_timing)
    _validate_override_timing(override_timing)
    _validate_adjusted_close(adjusted_close)
    _validate_turnover(turnover)
    audited = _validate_row_audits(row_audits, candidate_h)

    return {
        "artifact": "GP12_LABEL_PROVENANCE_ADMISSION_V482",
        "version": "V4.82",
        "status": "PASS_LABEL_PROVENANCE_ADMISSION",
        "formal_window": FORMAL_WINDOW,
        "scope": {
            "universe_symbol_n": 847,
            "row_bearing_symbol_n": 844,
            "not_applicable_symbol_n": 3,
            "horizon_label_rows": {str(h): EXPECTED_ROWS[h] for h in (1, 2, 3)},
        },
        "label_contract": {
            "contract_id": "GP12_V482_HORIZON_LOCAL_ACTION_NEUTRAL",
            "horizon_basis": "official A-share market-calendar T+h sessions",
            "horizons": [1, 2, 3],
            "missing_or_suspended_target_policy": "exclude row; never shift target to a later symbol bar",
            "corporate_action_window": "T < ex_date <= target_date",
            "action_neutral_reference_close": "close_T * product(V4.82-proven event_ratio)",
            "signed_return": "target_close / action_neutral_reference_close - 1",
            "label_rule": {"UP": "> 0", "DOWN": "< 0", "FLAT": "= 0"},
            "source_semantics": SOURCE_SEMANTICS,
            "events_after_target_date_rejected": True,
            "oos_rows_rejected": True,
            "all_281_corrected_overrides_bound": True,
            "event_availability_timing_required": True,
            "override_availability_timing_required": True,
        },
        "row_audits": audited,
        "promotion": {
            "adjusted_close_blocker_closed": True,
            "adjustment_provenance_blocker_closed": True,
            "turnover_ratio_blocker_closed": True,
            "label_contract_approved": True,
            "label_provenance_blocker_closed": True,
            "candidate_adoption_status": "APPROVED_FORMAL_LABEL_CONTRACT_V482",
            "formal_feature_ready": True,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        },
        "remaining_gp12_feature_blockers": [],
        "next_gate": "MODEL_FREEZE_PROVENANCE_ADMISSION",
    }
