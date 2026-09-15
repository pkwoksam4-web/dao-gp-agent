from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib

import gp12_candidate_package_review_v1 as benchmark_gate
import gp12_pit_readiness_integration_v482 as pit


ARTIFACT = "GP12_CANDIDATE_INPUT_READINESS_V1"
VERSION = "1.0"
FACTOR_SHA256 = "b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e"
PARAMETER_SHA256 = "22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204"
MARKET_FEATURE_BLOCKER = "MARKET_ADJUSTED_CLOSE_FEATURE_BINDING_UNBOUND"
NEXT_PRIORITY_FAMILY = "amount_turnover"
NEXT_PRIORITY_BLOCKER = "TURNOVER_RATIO_UNBOUND"


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


def _collect_input_blockers(report: dict) -> list[str]:
    blockers: list[str] = []
    for state in report.get("feature_families", {}).values():
        blockers.extend(state.get("blockers") or [])
    for state in report.get("supporting_evidence", {}).values():
        blockers.extend(state.get("blockers") or [])
    return sorted(set(str(blocker) for blocker in blockers if str(blocker).strip()))


def build_checkpoint(
    parameters: dict,
    factors: dict,
    base_evidence: dict,
    intraday_binding: dict,
    pit_binding: dict,
    benchmark_validation: dict,
) -> dict:
    """Compose current verified GP12 candidate input readiness.

    The existing V4.82 PIT/intraday integration remains authoritative for
    family readiness. CSI All Share / 000985 is validated separately as a
    benchmark reference and is never promoted to the frozen
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
    report = copy.deepcopy(upstream)

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

    # The candidate benchmark reference closes only the old benchmark-reference
    # gap. It does not satisfy the scorer's separately frozen market feature.
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
            "amount_cny/turnover_ratio are structurally represented by the bound "
            "daily panel, but a dedicated full-window PIT/coverage binding is still required"
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
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = build_checkpoint(
        _load(args.parameters),
        _load(args.factors),
        _load(args.base_evidence),
        _load(args.intraday_binding),
        _load(args.pit_binding),
        _load(args.benchmark_validation),
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
