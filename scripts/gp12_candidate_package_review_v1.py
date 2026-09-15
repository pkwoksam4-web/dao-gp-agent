from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

import gp12_candidate_v1 as core


STRATEGY_ID = "GP12_REBUILD_CANDIDATE_V1"
SUPPORTED_PARAMETERS_SHA256 = "22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204"
SUPPORTED_FACTORS_SHA256 = "b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e"
EXPECTED_BINDING_SHA256 = "73e9f84bd5a7a01ae43a6d780c66279a48c63743636e4fb3611996bead544c1a"
FROZEN_CALENDAR_LEGACY_SHA256 = "0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0"
FROZEN_CALENDAR_SEMANTIC_SHA256 = "5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7"
CLOSE_SERIES_SHA256 = "e9541cf917893b214ebe31a8602914c793e162bc5280137bfac88d243b75a73e"
FORMAL_WINDOW = ["2020-06-01", "2026-04-17"]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: pathlib.Path | str) -> dict:
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid benchmark evidence JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("benchmark evidence must be an object")
    return value


def _sha_ok(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def validate_candidate_benchmark_evidence(evidence: object) -> dict:
    reasons: list[str] = []
    if not isinstance(evidence, dict):
        return {
            "valid": False,
            "reasons": ["evidence is not an object"],
            "benchmark": None,
            "validation_sha256": None,
        }

    def require(condition: bool, reason: str) -> None:
        if not condition and reason not in reasons:
            reasons.append(reason)

    benchmark = evidence.get("benchmark")
    calendar = evidence.get("calendar")
    pit = evidence.get("pit")
    source = evidence.get("source")

    require(evidence.get("artifact") == "GP12_CANDIDATE_BENCHMARK_VALIDATION_V1", "artifact identity mismatch")
    require(evidence.get("status") == "PASS_CANDIDATE_BENCHMARK_V1", "benchmark validation status is not PASS")
    require(evidence.get("strategy_id") == STRATEGY_ID, "strategy identity mismatch")
    require(evidence.get("binding_status") == "CANDIDATE_ONLY_UNAPPROVED", "binding is not candidate-only")
    require(evidence.get("definition_origin") == "NEW_RECONSTRUCTION_CANDIDATE", "definition origin mismatch")
    require(evidence.get("formal_window") == FORMAL_WINDOW, "formal window mismatch")
    require(evidence.get("binding_sha256") == EXPECTED_BINDING_SHA256, "benchmark binding hash mismatch")
    require(evidence.get("factors_sha256") == SUPPORTED_FACTORS_SHA256, "factor hash drift")
    require(evidence.get("parameters_sha256") == SUPPORTED_PARAMETERS_SHA256, "parameter hash drift")
    require(evidence.get("factors_parameters_hashes_unchanged") is True, "factor/parameter immutable-hash assertion missing")

    require(isinstance(benchmark, dict), "benchmark object missing")
    if isinstance(benchmark, dict):
        require(benchmark.get("name") == "CSI All Share", "benchmark name mismatch")
        require(benchmark.get("local_name") == "中证全指", "benchmark local name mismatch")
        require(benchmark.get("code") == "000985", "benchmark code mismatch")
        require(benchmark.get("eastmoney_secid") == "1.000985", "benchmark secid mismatch")
        require(benchmark.get("series") == "daily_close", "benchmark series mismatch")
        require(
            benchmark.get("series_construction") == "INDEX_OWN_DAILY_CLOSE_NO_CONSTITUENT_RECONSTRUCTION",
            "benchmark series construction mismatch",
        )

    require(isinstance(calendar, dict), "calendar evidence missing")
    if isinstance(calendar, dict):
        require(calendar.get("expected_n") == 1426, "frozen calendar expected count mismatch")
        require(calendar.get("observed_n") == 1426, "benchmark observed count mismatch")
        require(calendar.get("first") == "2020-06-01", "benchmark first date mismatch")
        require(calendar.get("last") == "2026-04-17", "benchmark last date mismatch")
        require(calendar.get("legacy_sha256") == FROZEN_CALENDAR_LEGACY_SHA256, "legacy calendar hash mismatch")
        require(calendar.get("semantic_sha256") == FROZEN_CALENDAR_SEMANTIC_SHA256, "semantic calendar hash mismatch")
        require(calendar.get("full_coverage") is True, "benchmark calendar coverage not full")

    require(isinstance(pit, dict), "PIT evidence missing")
    if isinstance(pit, dict):
        require(pit.get("policy_valid") is True, "PIT policy invalid")
        require(pit.get("scope") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "PIT scope mismatch")
        require(pit.get("known_at_first") == "2020-06-01T15:00:00+08:00", "PIT first availability mismatch")
        require(pit.get("known_at_last") == "2026-04-17T15:00:00+08:00", "PIT last availability mismatch")
        require(pit.get("same_session_close_usable_before_close") is False, "pre-close use was not forbidden")
        require(pit.get("historical_provider_publication_timestamp_proven") is False, "provider publication timestamp was overclaimed")

    require(isinstance(source, dict), "source evidence missing")
    if isinstance(source, dict):
        require(source.get("provider") == "Eastmoney", "benchmark provider mismatch")
        require(source.get("secid") == "1.000985", "source secid mismatch")
        require(source.get("payload_code") == "000985", "source payload code mismatch")
        require(source.get("payload_name") == "中证全指", "source payload name mismatch")
        require(source.get("klt") == 101, "source klt mismatch")
        require(source.get("fqt") == 0, "source fqt mismatch")
        require(source.get("identity_valid") is True, "source identity invalid")
        require(
            source.get("series_construction") == "INDEX_OWN_DAILY_CLOSE_NO_CONSTITUENT_RECONSTRUCTION",
            "source series construction mismatch",
        )

    require(evidence.get("close_series_sha256") == CLOSE_SERIES_SHA256, "benchmark close-series hash mismatch")
    require(_sha_ok(evidence.get("close_series_sha256")), "benchmark close-series hash malformed")
    require(evidence.get("candidate_benchmark_blocker_closed") is True, "candidate benchmark blocker remains open")
    require(evidence.get("gp_v11_benchmark_recovered") is False, "GP V1.1 benchmark recovery was falsely claimed")
    require(evidence.get("historical_recovery_claim_allowed") is False, "historical recovery claim was allowed")
    require(evidence.get("blockers") == [], "upstream benchmark validation contains blockers")

    return {
        "valid": not reasons,
        "reasons": reasons,
        "benchmark": {
            "name": benchmark.get("name"),
            "local_name": benchmark.get("local_name"),
            "code": benchmark.get("code"),
            "eastmoney_secid": benchmark.get("eastmoney_secid"),
            "series": benchmark.get("series"),
            "series_construction": benchmark.get("series_construction"),
            "formal_window": list(FORMAL_WINDOW),
            "calendar_n": calendar.get("observed_n") if isinstance(calendar, dict) else None,
            "pit_scope": pit.get("scope") if isinstance(pit, dict) else None,
            "source_identity_valid": source.get("identity_valid") if isinstance(source, dict) else False,
            "close_series_sha256": evidence.get("close_series_sha256"),
            "binding_sha256": evidence.get("binding_sha256"),
        } if isinstance(benchmark, dict) else None,
        "validation_sha256": canonical_json_sha256(evidence),
    }


def review_package(
    parameters_path: pathlib.Path | str,
    factors_path: pathlib.Path | str,
    benchmark_validation_path: pathlib.Path | str,
) -> dict:
    base = core.review_package(parameters_path, factors_path)
    evidence = None
    benchmark_check = {
        "valid": False,
        "reasons": ["benchmark evidence unavailable"],
        "benchmark": None,
        "validation_sha256": None,
    }
    try:
        evidence = _load_json(benchmark_validation_path)
        benchmark_check = validate_candidate_benchmark_evidence(evidence)
    except ValueError as exc:
        benchmark_check = {
            "valid": False,
            "reasons": [str(exc)],
            "benchmark": None,
            "validation_sha256": None,
        }

    blockers = list(base.get("blockers", []))
    if not benchmark_check["valid"]:
        if "CANDIDATE_BENCHMARK_EVIDENCE_INVALID" not in blockers:
            blockers.append("CANDIDATE_BENCHMARK_EVIDENCE_INVALID")

    combined_valid = bool(base.get("candidate_review_passed")) and benchmark_check["valid"]
    result = dict(base)
    result.update({
        "artifact": "GP12_CANDIDATE_PACKAGE_REVIEW_WITH_BENCHMARK_V1",
        "status": "CANDIDATE_READY_FOR_REVIEW" if combined_valid else "CANDIDATE_PACKAGE_INVALID",
        "candidate_review_passed": combined_valid,
        "candidate_benchmark_validated": benchmark_check["valid"],
        "candidate_benchmark_blocker_closed": benchmark_check["valid"],
        "candidate_benchmark": benchmark_check["benchmark"],
        "candidate_benchmark_validation_sha256": benchmark_check["validation_sha256"],
        "candidate_benchmark_validation_reasons": benchmark_check["reasons"],
        "benchmark_binding_scope": "BENCHMARK_REFERENCE_ONLY",
        "benchmark_feature_binding_allowed": False,
        "market_adjusted_close_substitution_allowed": False,
        "historical_benchmark_recovered": False,
        "historical_strategy_recovered": False,
        "real_feature_inputs_validated": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": blockers,
    })
    return result


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Review GP12 candidate package with candidate benchmark evidence")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--out", required=True)
    parser.add_argument("--parameters", default=str(root / "data/GP12_CANDIDATE_PARAMETERS_V1.json"))
    parser.add_argument("--factors", default=str(root / "data/GP12_CANDIDATE_FACTORS_V1.json"))
    parser.add_argument("--benchmark-validation", required=True)
    args = parser.parse_args()
    if not args.review:
        parser.error("--review is required")
    report = review_package(args.parameters, args.factors, args.benchmark_validation)
    output = pathlib.Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0 if report["candidate_review_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
