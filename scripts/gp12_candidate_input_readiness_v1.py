from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib

import gp12_candidate_package_review_v1 as benchmark_gate
import gp12_formal_input_readiness_v1 as readiness_base
import gp12_pit_readiness_integration_v482 as pit


ARTIFACT = "GP12_CANDIDATE_INPUT_READINESS_V1"
VERSION = "1.0"
FACTOR_SHA256 = "b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e"
PARAMETER_SHA256 = "22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204"
MARKET_FEATURE_BLOCKER = "MARKET_ADJUSTED_CLOSE_FEATURE_BINDING_UNBOUND"
AMOUNT_TURNOVER_BINDING_ARTIFACT = "GP12_CANDIDATE_AMOUNT_TURNOVER_BINDING_V1"
AMOUNT_TURNOVER_BINDING_SHA256 = "47b83c11b7190f4bb8f3bc69900f75fd682362ed5e20d6cbb3b9c4d7bdbe4998"
NEXT_PRIORITY_FAMILY = "main_net_flow"
NEXT_PRIORITY_BLOCKER = "MAIN_NET_FLOW_UNBOUND"
FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
EXPECTED_TRADE_ROWS = 1_011_607
NA_SYMBOLS = ["600074.SH", "600485.SH", "600677.SH"]


def _load(path: pathlib.Path | str) -> dict:
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return value


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_amount_turnover_binding(binding: dict) -> str:
    """Validate the exact candidate-only amount/turnover evidence binding."""
    _require(isinstance(binding, dict), "amount-turnover binding must be an object")
    binding_sha = _canonical_json_sha256(binding)
    _require(
        binding_sha == AMOUNT_TURNOVER_BINDING_SHA256,
        "AMOUNT_TURNOVER_BINDING_IDENTITY_MISMATCH",
    )
    _require(binding.get("artifact") == AMOUNT_TURNOVER_BINDING_ARTIFACT, "amount-turnover artifact mismatch")
    _require(binding.get("version") == "1.0", "amount-turnover version mismatch")
    _require(binding.get("strategy_id") == "GP12_REBUILD_CANDIDATE_V1", "amount-turnover strategy mismatch")
    _require(binding.get("status") == "CANDIDATE_ONLY_UNAPPROVED", "amount-turnover status mismatch")
    _require(binding.get("origin") == "NEW_RECONSTRUCTION_CANDIDATE", "amount-turnover origin mismatch")
    _require(binding.get("formal_window") == [FORMAL_START, FORMAL_END], "amount-turnover formal window mismatch")
    _require(binding.get("universe_n") == 847, "amount-turnover universe mismatch")
    _require(binding.get("formal_symbol_n") == 844, "amount-turnover formal-symbol mismatch")
    _require(binding.get("na_symbols") == NA_SYMBOLS, "amount-turnover N/A partition mismatch")
    _require(binding.get("expected_trade_rows") == EXPECTED_TRADE_ROWS, "amount-turnover expected rows mismatch")

    amount = binding.get("amount_source") or {}
    _require(amount.get("field") == "amount", "amount field mismatch")
    _require(amount.get("unit") == "CNY", "amount unit mismatch")
    _require(amount.get("artifact_name") == "gp-sohu-full-raw-v482-reaudit", "amount artifact mismatch")
    _require(amount.get("workflow_run") == 34192233633, "amount workflow run mismatch")
    _require(amount.get("artifact_id") == 10042614517, "amount artifact id mismatch")
    _require(
        amount.get("artifact_zip_sha256")
        == "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550",
        "amount artifact digest mismatch",
    )
    _require(amount.get("positive_amount_rows") == EXPECTED_TRADE_ROWS, "amount row coverage mismatch")

    turnover = binding.get("turnover_source") or {}
    _require(turnover.get("provider") == "BaoStock", "turnover provider mismatch")
    _require(turnover.get("field") == "turn", "turnover field mismatch")
    _require(turnover.get("source_unit") == "percent", "turnover source unit mismatch")
    _require(turnover.get("candidate_unit") == "decimal_ratio", "turnover candidate unit mismatch")
    _require(turnover.get("workflow_run") == 34981310300, "turnover workflow run mismatch")
    _require(
        turnover.get("workflow_head") == "66571bc360f77ba989c47dbe6e8dc0708aac46f9",
        "turnover workflow head mismatch",
    )
    _require(turnover.get("artifact_name") == "gp12-baostock-turnover-full-v1", "turnover artifact mismatch")
    _require(turnover.get("artifact_id") == 10403125922, "turnover artifact id mismatch")
    _require(
        turnover.get("artifact_zip_sha256")
        == "9fcda20e7d7ab01ce22ea377c15726126dfd62d28b5ad7df6d694fda545be6ad",
        "turnover artifact digest mismatch",
    )
    _require(
        turnover.get("audit_json_sha256")
        == "7c3c85315f53956df96a59f2703210077bdc67d758d454c77de7edce03e24e0c",
        "turnover audit digest mismatch",
    )
    _require(
        turnover.get("panel_csv_sha256")
        == "90b483f5f55668c0243523c5cf997c5251611e59dc5007fa6429ddf441b515a4",
        "turnover panel digest mismatch",
    )
    _require(turnover.get("observed_turnover_rows") == EXPECTED_TRADE_ROWS, "turnover observed rows mismatch")
    _require(turnover.get("materialized_rows") == EXPECTED_TRADE_ROWS, "turnover materialized rows mismatch")
    _require(turnover.get("provider_status_override_n") == 5, "turnover provider-status trace mismatch")
    _require(turnover.get("turnover_precision_reconstruction_n") == 9, "turnover precision trace mismatch")
    _require(
        turnover.get("residual_denominator_binding_artifact")
        == "GP12_CANDIDATE_TURNOVER_RESIDUAL_DENOMINATORS_V1",
        "turnover residual denominator artifact mismatch",
    )
    _require(
        turnover.get("residual_denominator_binding_sha256")
        == "74e00c11098c4fe46b1b60048306b5b64c6836ca929c54fdb58064e4a14fce4f",
        "turnover residual denominator digest mismatch",
    )

    coverage = binding.get("coverage") or {}
    _require(coverage.get("amount_turnover_full_window_aligned") is True, "amount-turnover alignment not verified")
    _require(coverage.get("turnover_ratio_candidate_pit_verified") is True, "turnover PIT not verified")
    _require(coverage.get("pit_scope") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "turnover PIT scope mismatch")
    _require(coverage.get("same_session_turnover_usable_before_close") is False, "same-session turnover lookahead allowed")
    _require(
        coverage.get("historical_provider_publication_timestamp_proven") is False,
        "provider publication timestamp must remain unproven",
    )
    _require(binding.get("historical_gp_v11_source_recovered") is False, "historical GP V1.1 recovery cannot be claimed")
    _require(binding.get("model_freeze_allowed") is False, "turnover binding cannot open model freeze")
    _require(binding.get("oos_metrics_allowed") is False, "turnover binding cannot open OOS metrics")
    _require(binding.get("blockers") == [], "amount-turnover binding blockers remain")
    return binding_sha


def _collect_input_blockers(report: dict) -> list[str]:
    blockers: list[str] = []
    for state in report.get("feature_families", {}).values():
        blockers.extend(state.get("blockers") or [])
    for state in report.get("supporting_evidence", {}).values():
        blockers.extend(state.get("blockers") or [])
    return sorted(set(str(blocker) for blocker in blockers if str(blocker).strip()))


def _copy_verified_family_overlay(derived_evidence: dict, upstream: dict, family: str) -> None:
    state = upstream["feature_families"][family]
    derived_evidence["feature_families"][family] = {
        key: state[key] for key in readiness_base.FAMILY_KEYS
    }


def build_checkpoint(
    parameters: dict,
    factors: dict,
    base_evidence: dict,
    intraday_binding: dict,
    pit_binding: dict,
    benchmark_validation: dict,
    amount_turnover_binding: dict,
) -> dict:
    """Compose current verified GP12 candidate input readiness.

    Existing PIT/intraday integrations remain authoritative. The verified
    candidate-only amount/turnover binding adds one scorer family without
    making any historical GP V1.1 recovery claim. CSI All Share / 000985 is
    still benchmark-reference only and cannot substitute for the frozen
    ``market_adjusted_close`` feature family.
    """
    factor_sha = _canonical_json_sha256(factors)
    parameter_sha = _canonical_json_sha256(parameters)
    if factor_sha != FACTOR_SHA256:
        raise ValueError(f"factor definition hash drift: {factor_sha}")
    if parameter_sha != PARAMETER_SHA256:
        raise ValueError(f"parameter hash drift: {parameter_sha}")

    upstream = pit.build_pit_checkpoint(
        parameters,
        factors,
        base_evidence,
        intraday_binding,
        pit_binding,
    )
    amount_turnover_sha = validate_amount_turnover_binding(amount_turnover_binding)

    derived_evidence = copy.deepcopy(base_evidence)
    for family in ("intraday_15m", "intraday_60m", "stock_adjusted_close"):
        _copy_verified_family_overlay(derived_evidence, upstream, family)
    derived_evidence["feature_families"]["amount_turnover"] = {
        "binding_state": "BOUND_VERIFIED_ARTIFACT",
        "pit_state": "PIT_VERIFIED",
        "source_artifact": AMOUNT_TURNOVER_BINDING_ARTIFACT,
        "source_sha256": amount_turnover_sha,
        "coverage_start": FORMAL_START,
        "coverage_end": FORMAL_END,
        "blockers": [],
    }
    report = readiness_base.build_readiness_report(parameters, factors, derived_evidence)

    benchmark_check = benchmark_gate.validate_candidate_benchmark_evidence(
        benchmark_validation
    )

    market = report["feature_families"]["market_adjusted_close"]
    if market.get("formal_feature_ready") is not False:
        raise ValueError("market_adjusted_close unexpectedly ready before feature binding")
    if market.get("binding_state") != "UNBOUND":
        raise ValueError("market_adjusted_close unexpectedly bound before feature binding")
    if market.get("pit_state") != "PIT_UNVERIFIED":
        raise ValueError("market_adjusted_close PIT state unexpectedly changed")
    if market.get("source_artifact") is not None or market.get("source_sha256") is not None:
        raise ValueError("market_adjusted_close unexpectedly carries source identity")

    market["blockers"] = [MARKET_FEATURE_BLOCKER]

    input_blockers = _collect_input_blockers(report)
    if not benchmark_check["valid"]:
        input_blockers = sorted(
            set(input_blockers + ["CANDIDATE_BENCHMARK_EVIDENCE_INVALID"])
        )

    benchmark_reference = None
    if benchmark_check["valid"]:
        benchmark_reference = {
            **benchmark_check["benchmark"],
            "scope": "BENCHMARK_REFERENCE_ONLY",
            "validation_sha256": benchmark_check["validation_sha256"],
        }

    candidate_scoring_ready = bool(report.get("candidate_scoring_ready"))
    if not benchmark_check["valid"]:
        candidate_scoring_ready = False

    result = {
        **report,
        "artifact": ARTIFACT,
        "version": VERSION,
        "lineage_artifact": upstream.get("artifact"),
        "lineage_version": upstream.get("version"),
        "asset_hashes": {
            "factor_definition_sha256": factor_sha,
            "parameter_sha256": parameter_sha,
        },
        "amount_turnover_binding_artifact": AMOUNT_TURNOVER_BINDING_ARTIFACT,
        "amount_turnover_binding_sha256": amount_turnover_sha,
        "candidate_benchmark_reference_validated": benchmark_check["valid"],
        "candidate_benchmark_reference": benchmark_reference,
        "candidate_benchmark_validation_reasons": benchmark_check["reasons"],
        "benchmark_feature_binding_allowed": False,
        "market_adjusted_close_substitution_allowed": False,
        "historical_benchmark_recovered": False,
        "historical_strategy_recovered": False,
        "candidate_scoring_ready": candidate_scoring_ready,
        "real_feature_inputs_validated": candidate_scoring_ready,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": input_blockers,
        "adoption_blockers": ["NEW_STRATEGY_ADOPTION_REQUIRED"],
        "next_priority_family": NEXT_PRIORITY_FAMILY,
        "next_priority_blocker": NEXT_PRIORITY_BLOCKER,
        "next_priority_reason": (
            "amount_cny and turnover_ratio now have exact full-window candidate-only binding; "
            "F11 remains blocked by the still-unbound main_net_flow input family"
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build GP12 candidate feature-input readiness checkpoint"
    )
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--factors", required=True)
    parser.add_argument("--base-evidence", required=True)
    parser.add_argument("--intraday-binding", required=True)
    parser.add_argument("--pit-binding", required=True)
    parser.add_argument("--benchmark-validation", required=True)
    parser.add_argument("--amount-turnover-binding", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = build_checkpoint(
        _load(args.parameters),
        _load(args.factors),
        _load(args.base_evidence),
        _load(args.intraday_binding),
        _load(args.pit_binding),
        _load(args.benchmark_validation),
        _load(args.amount_turnover_binding),
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact": report["artifact"],
                "asset_hashes": report["asset_hashes"],
                "amount_turnover_binding_sha256": report[
                    "amount_turnover_binding_sha256"
                ],
                "validated_families": report["validated_families"],
                "missing_or_unvalidated_families": report[
                    "missing_or_unvalidated_families"
                ],
                "ready_factor_ids": report["ready_factor_ids"],
                "blocked_factor_ids": report["blocked_factor_ids"],
                "candidate_benchmark_reference_validated": report[
                    "candidate_benchmark_reference_validated"
                ],
                "benchmark_feature_binding_allowed": report[
                    "benchmark_feature_binding_allowed"
                ],
                "market_adjusted_close_substitution_allowed": report[
                    "market_adjusted_close_substitution_allowed"
                ],
                "blockers": report["blockers"],
                "next_priority_family": report["next_priority_family"],
                "candidate_scoring_ready": report["candidate_scoring_ready"],
                "model_freeze_allowed": report["model_freeze_allowed"],
                "oos_metrics_allowed": report["oos_metrics_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["candidate_benchmark_reference_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
