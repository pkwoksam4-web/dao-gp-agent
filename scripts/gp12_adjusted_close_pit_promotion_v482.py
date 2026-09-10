from __future__ import annotations

import argparse
import json
from pathlib import Path


FROZEN_INPUTS = {
    "event_timing": {
        "workflow_run_id": 34470443439,
        "artifact_id": 10149283589,
        "artifact_name": "gp12-event-timing-admission-v482",
        "artifact_zip_sha256": "d63c2e7c4aa094b47a3a311de6eda690a3c4082f58185963d4f57cb87af7401d",
    },
    "override_timing": {
        "workflow_run_id": 34471061403,
        "artifact_id": 10149533619,
        "artifact_name": "gp12-override-timing-admission-v482",
        "artifact_zip_sha256": "16824e45ea35c286bdf503e1d10dce8886fb6c08375e507859b4c86830e4c0de",
    },
    "row_provenance": {
        "workflow_run_id": 34465663322,
        "artifact_id": 10147403778,
        "artifact_name": "gp12-qfq-row-provenance-candidate-v482",
        "artifact_zip_sha256": "dd734b9d47a08d971a0e3d431c2229c0502d273fd952bb3225927760cc4347fd",
    },
    "formal_final": {
        "workflow_run_id": 34192462041,
        "artifact_id": 10042687724,
        "artifact_name": "gp-formal-readiness-final-v482",
        "artifact_zip_sha256": "fdd2f45f4c6998ce2e130363aaf49bab16c9f964c28ba3202b552fbe07c5f5c6",
    },
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_event_timing(event: dict) -> None:
    ok = (
        event.get("status") == "PASS_EVENT_TIMING_ADMISSION"
        and event.get("expected_n") == 2732
        and event.get("covered_n") == 2732
        and event.get("missing_n") == 0
        and event.get("extra_n") == 0
        and event.get("late_n") == 0
        and event.get("source_partition_exact") is True
        and (event.get("promotion") or {}).get("event_availability_time_verified") is True
    )
    _require(ok, "event timing admission is not exact 2732/2732 PIT-safe coverage")


def _validate_override_timing(override: dict) -> None:
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
        and (override.get("promotion") or {}).get("corrected_term_availability_time_verified") is True
    )
    _require(ok, "override timing admission is not exact 281/281 PIT-safe binding")


def _validate_row_provenance(row: dict) -> None:
    cross = row.get("global_row_crosscheck") or {}
    sample = row.get("sample50_v479") or {}
    ok = (
        row.get("status") == "PASS_ROW_LEVEL_MATERIALIZATION"
        and row.get("formal_symbol_n") == 844
        and row.get("not_applicable_symbol_n") == 3
        and row.get("row_n") == 1011607
        and row.get("unique_symbol_date_n") == 1011607
        and row.get("factor_positive_rows") == 1011607
        and row.get("row_provenance_nonempty_n") == 1011607
        and row.get("row_provenance_unique_n") == 1011607
        and row.get("event_ledger_n") == 2732
        and row.get("override_event_n") == 281
        and sample.get("sample_n") == 50
        and sample.get("pass_n") == 50
        and sample.get("fail_n") == 0
        and float(sample.get("max_diff_bp", 1e9)) <= 5.0
        and float(cross.get("threshold_bp", -1)) == 5.0
        and cross.get("mismatch_rows") == 0
        and float(cross.get("max_diff_bp", 1e9)) <= 5.0
    )
    _require(ok, "row-level provenance is not exact 1,011,607-row validated coverage")


def _validate_formal_final(formal: dict) -> None:
    ok = (
        formal.get("formal_ready") is True
        and formal.get("validated_global_provenance_emitted") is True
        and formal.get("full_path_pass_n") == 844
        and formal.get("full_path_fail_n") == 0
        and formal.get("checkpoint")
        == {"PASS": 844, "EXACT_TERM_REVIEW": 0, "MISSING_EVENT_REVIEW": 0, "NOT_APPLICABLE": 3}
        and formal.get("oos_metrics_allowed") is False
    )
    _require(ok, "formal final is not the closed V4.82 844/844 checkpoint")


def build_promotion(event: dict, override: dict, row: dict, formal: dict) -> dict:
    _validate_event_timing(event)
    _validate_override_timing(override)
    _validate_row_provenance(row)
    _validate_formal_final(formal)

    return {
        "artifact": "GP12_ADJUSTED_CLOSE_PIT_PROMOTION_V482",
        "version": "V4.82",
        "status": "VALIDATED_GLOBAL_PROVENANCE",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "scope": {
            "formal_symbol_n": 844,
            "not_applicable_symbol_n": 3,
            "row_n": 1011607,
            "event_n": 2732,
            "corrected_override_n": 281,
            "same_day_preopen_n": 2,
        },
        "evidence": {
            "event_timing_status": event["status"],
            "event_timing_covered_n": event["covered_n"],
            "override_timing_status": override["status"],
            "override_timing_pass_n": override["total_pass_n"],
            "row_provenance_status": row["status"],
            "row_provenance_unique_n": row["row_provenance_unique_n"],
            "global_row_crosscheck_mismatch_rows": row["global_row_crosscheck"]["mismatch_rows"],
            "global_row_crosscheck_max_diff_bp": row["global_row_crosscheck"]["max_diff_bp"],
            "formal_full_path_pass_n": formal["full_path_pass_n"],
            "formal_full_path_fail_n": formal["full_path_fail_n"],
        },
        "frozen_inputs": FROZEN_INPUTS,
        "promotion": {
            "validation_status_promoted_to_VALIDATED_GLOBAL_PROVENANCE": True,
            "event_availability_time_verified": True,
            "corrected_term_availability_time_verified": True,
            "row_level_factor_provenance_verified": True,
            "adjusted_close_blocker_closed": True,
            "adjustment_provenance_blocker_closed": True,
            "adjusted_close_feature_ready": True,
            "turnover_ratio_blocker_closed": False,
            "label_provenance_blocker_closed": False,
            "formal_feature_ready": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        },
        "remaining_gp12_blockers": [
            "TURNOVER_RATIO_UNBOUND",
            "LABEL_PROVENANCE_UNBOUND",
        ],
        "note": (
            "This promotion closes only the GP12 adjusted-close PIT/provenance blocker. "
            "Turnover-ratio PIT immutability and label provenance remain fail-closed; "
            "model freeze and OOS metrics remain disallowed."
        ),
    }


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-timing", required=True)
    parser.add_argument("--override-timing", required=True)
    parser.add_argument("--row-provenance", required=True)
    parser.add_argument("--formal-final", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    result = build_promotion(
        _load(args.event_timing),
        _load(args.override_timing),
        _load(args.row_provenance),
        _load(args.formal_final),
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "GP12_ADJUSTED_CLOSE_PIT_PROMOTION_V482.json"
    target.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
