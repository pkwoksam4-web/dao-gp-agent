from __future__ import annotations

import argparse
import copy
import json
import pathlib

import gp12_candidate_input_readiness_v1 as base


STATUS_BINDING_ARTIFACT = "GP12_CANDIDATE_STATUS_BINDING_V1"
STATUS_BINDING_SHA256 = "aaf1c352d74ce2a0408ea454f8d9deaaea7d9428629ed33ecccdd09f1a2ce96a"
STATUS_COMPOSITION_ARTIFACT = "gp12-status-full-composition-v1"
STATUS_COMPOSITION_PANEL_SHA256 = "dadf57d1d845491caf7f6fdf785f32c7e9f56e23f2476f5f66d7d26d1c65d0a9"
STATUS_COMPOSITION_AUDIT_SHA256 = "8dd50470a6d7b4d149a9a9af30665f220351de00d13149c9aa42b9fccff3a83b"
UPPER_LIMIT_PANEL_SHA256 = "a08a0705621c41bfdc704ff281f6f3a6c01ba17485e3981d55707f18303ad08e"
UPPER_LIMIT_AUDIT_SHA256 = "44ada4ca0429963ae19f9c4ed4a5ba60e915e31b3677172cfefe63384ba1d6b8"
EXPECTED_LIFECYCLE_ROWS = 1_021_953
EXPECTED_NONTRADE_ROWS = 10_346
EXPECTED_UPPER_LIMIT_ROWS = 25_742


def _load(path: pathlib.Path | str) -> dict:
    return base._load(path)


def _require(condition: bool, message: str) -> None:
    base._require(condition, message)


def validate_status_binding(binding: dict) -> str:
    """Validate the exact full candidate-only status binding.

    This validates a reconstruction candidate, not recovered historical GP V1.1
    source semantics.  All three status fields are only usable under the
    session-close no-lookahead policy.
    """
    _require(isinstance(binding, dict), "status binding must be an object")
    binding_sha = base._canonical_json_sha256(binding)
    _require(binding_sha == STATUS_BINDING_SHA256, "STATUS_BINDING_IDENTITY_MISMATCH")
    _require(binding.get("artifact") == STATUS_BINDING_ARTIFACT, "status artifact mismatch")
    _require(binding.get("version") == "1.0", "status version mismatch")
    _require(binding.get("strategy_id") == "GP12_REBUILD_CANDIDATE_V1", "status strategy mismatch")
    _require(binding.get("status") == "CANDIDATE_ONLY_UNAPPROVED", "status state mismatch")
    _require(binding.get("origin") == "NEW_RECONSTRUCTION_CANDIDATE", "status origin mismatch")
    _require(binding.get("formal_window") == [base.FORMAL_START, base.FORMAL_END], "status formal window mismatch")
    _require(binding.get("universe_n") == 847, "status universe mismatch")
    _require(binding.get("formal_symbol_n") == 844, "status formal symbol mismatch")
    _require(binding.get("na_symbols") == base.NA_SYMBOLS, "status N/A partition mismatch")
    _require(binding.get("lifecycle_rows") == EXPECTED_LIFECYCLE_ROWS, "status lifecycle rows mismatch")
    _require(binding.get("expected_trade_rows") == base.EXPECTED_TRADE_ROWS, "status trade rows mismatch")
    _require(binding.get("required_status_fields") == ["is_st", "tradable", "upper_limit"], "status fields mismatch")

    st = binding.get("is_st_source") or {}
    _require(st.get("workflow_run") == 33977325822, "is_st run mismatch")
    _require(st.get("workflow_head") == "a552c5855a96c526178da15837f2d9d488e2d2e6", "is_st head mismatch")
    _require(st.get("artifact_id") == 9972698555, "is_st artifact id mismatch")
    _require(st.get("overlay_csv_sha256") == "6ed8ffd09215bccb90f716af26d44f7f590ffd5d455c20841307484a63aaa490", "is_st overlay mismatch")
    _require(st.get("lifecycle_rows") == EXPECTED_LIFECYCLE_ROWS, "is_st lifecycle mismatch")
    _require(st.get("lifecycle_pass_n") == 847, "is_st coverage mismatch")

    tradable = binding.get("tradable_source") or {}
    _require(tradable.get("workflow_run") == 35052354861, "tradable run mismatch")
    _require(tradable.get("artifact_id") == 10428808437, "tradable artifact id mismatch")
    _require(tradable.get("positive_trade_rows") == base.EXPECTED_TRADE_ROWS, "tradable positive rows mismatch")
    _require(tradable.get("nontrade_lifecycle_rows") == EXPECTED_NONTRADE_ROWS, "tradable nontrade rows mismatch")
    _require(tradable.get("provider_status_misflag_n") == 5, "tradable provider-status mismatch")
    _require(tradable.get("status1_but_no_positive_trade_n") == 0, "tradable false-positive mismatch")

    upper = binding.get("upper_limit_source") or {}
    _require(upper.get("field") == "upper_limit", "upper-limit field mismatch")
    _require(upper.get("workflow_run") == 35069676486, "upper-limit run mismatch")
    _require(upper.get("workflow_head") == "1e07ada2b3480221c0dbc3417bf911965a1dc8ed", "upper-limit head mismatch")
    _require(upper.get("artifact_name") == "gp12-upper-limit-full-source-v1", "upper-limit artifact mismatch")
    _require(upper.get("artifact_id") == 10435886487, "upper-limit artifact id mismatch")
    _require(upper.get("artifact_zip_sha256") == "ef9692c9feef8bda9d55b7d96f124925d6beb02b33123424725c8caf7f9ef8bf", "upper-limit artifact digest mismatch")
    _require(upper.get("panel_sha256") == UPPER_LIMIT_PANEL_SHA256, "upper-limit panel digest mismatch")
    _require(upper.get("audit_json_sha256") == UPPER_LIMIT_AUDIT_SHA256, "upper-limit audit digest mismatch")
    _require(upper.get("positive_trade_rows") == base.EXPECTED_TRADE_ROWS, "upper-limit row coverage mismatch")
    _require(upper.get("formal_symbol_n") == 844, "upper-limit symbol coverage mismatch")
    _require(upper.get("no_limit_rows") == 199, "upper-limit no-limit count mismatch")
    _require(upper.get("special_no_limit_rows") == 9, "upper-limit special count mismatch")
    _require(upper.get("upper_limit_true_rows") == EXPECTED_UPPER_LIMIT_ROWS, "upper-limit true count mismatch")
    _require(upper.get("reference_panel_run") == 35064830592, "reference-panel run mismatch")
    _require(upper.get("reference_panel_artifact_id") == 10435322179, "reference-panel artifact mismatch")
    _require(upper.get("reference_panel_sha256") == "39f4df606abd4629ab28fac1d7444e73dfdeb3bb36c6764673f378463bd08c7e", "reference-panel digest mismatch")
    _require(upper.get("special_evidence_artifact") == "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1", "special evidence artifact mismatch")
    _require(upper.get("special_evidence_sha256") == "ab97091336089aedb984eca782468e0cfd331e1db96f397fb1a172fbea6db039", "special evidence digest mismatch")
    _require(upper.get("canonical_truth_sha256") == "d11b415b74d44d63d1aa927e8652f395dd039c28f6e1b4c24964e53759405308", "canonical truth digest mismatch")
    _require(upper.get("canonical_truth_overlap_rows") == 896_827, "canonical truth row coverage mismatch")
    _require(upper.get("canonical_truth_overlap_symbols") == 698, "canonical truth symbol coverage mismatch")
    for field in ("truth_close_mismatch_n", "truth_no_limit_mismatch_n", "truth_price_mismatch_n", "truth_boolean_mismatch_n"):
        _require(upper.get(field) == 0, f"upper-limit truth mismatch remains: {field}")

    composition = binding.get("composition_source") or {}
    _require(composition.get("workflow_run") == 35070179201, "status composition run mismatch")
    _require(composition.get("workflow_head") == "e4ae255deddfbe7f98e56a1eb5e3ae2c77b6330d", "status composition head mismatch")
    _require(composition.get("artifact_name") == STATUS_COMPOSITION_ARTIFACT, "status composition artifact mismatch")
    _require(composition.get("artifact_id") == 10435349883, "status composition artifact id mismatch")
    _require(composition.get("artifact_zip_sha256") == "fd3d3ca4fe573e9ad0a212e96e4acda8eeb740276f77148a262211834e8cd94c", "status composition zip mismatch")
    _require(composition.get("panel_sha256") == STATUS_COMPOSITION_PANEL_SHA256, "status composition panel mismatch")
    _require(composition.get("audit_json_sha256") == STATUS_COMPOSITION_AUDIT_SHA256, "status composition audit mismatch")
    _require(composition.get("pit_st_lifecycle_csv_sha256") == "6ed8ffd09215bccb90f716af26d44f7f590ffd5d455c20841307484a63aaa490", "status lifecycle digest mismatch")
    _require(composition.get("lifecycle_rows") == EXPECTED_LIFECYCLE_ROWS, "status composition lifecycle mismatch")
    _require(composition.get("tradable_true_rows") == base.EXPECTED_TRADE_ROWS, "status composition tradable rows mismatch")
    _require(composition.get("tradable_false_rows") == EXPECTED_NONTRADE_ROWS, "status composition nontrade rows mismatch")
    _require(composition.get("upper_limit_true_rows") == EXPECTED_UPPER_LIMIT_ROWS, "status composition upper-limit rows mismatch")
    _require(composition.get("nontradable_upper_limit_true_rows") == 0, "nontradable upper-limit rows remain")
    _require(composition.get("duplicate_symbol_dates") == 0, "status composition duplicate keys remain")
    _require(composition.get("missing_status_values") == 0, "status composition missing values remain")

    _require(binding.get("semantic_state") == {
        "is_st": "BOUND_PIT_VERIFIED",
        "tradable": "BOUND_PIT_VERIFIED",
        "upper_limit": "BOUND_PIT_VERIFIED",
    }, "status semantic state mismatch")
    pit_state = binding.get("pit") or {}
    _require(pit_state.get("scope") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "status PIT scope mismatch")
    _require(pit_state.get("same_session_status_usable_before_close") is False, "same-session status lookahead allowed")
    _require(pit_state.get("historical_provider_publication_timestamp_proven") is False, "status provider publication timestamp must remain unproven")
    _require(binding.get("family_ready") is True, "status family readiness mismatch")
    _require(binding.get("historical_gp_v11_source_recovered") is False, "historical GP V1.1 status source recovery cannot be claimed")
    _require(binding.get("model_freeze_allowed") is False, "status binding cannot open model freeze")
    _require(binding.get("oos_metrics_allowed") is False, "status binding cannot open OOS metrics")
    _require(binding.get("blockers") == [], "status binding blockers remain")
    return binding_sha


def build_checkpoint(
    parameters: dict,
    factors: dict,
    base_evidence: dict,
    intraday_binding: dict,
    pit_binding: dict,
    benchmark_validation: dict,
    amount_turnover_binding: dict,
    main_net_flow_requirement: dict | None = None,
    status_partial_binding: dict | None = None,
    market_breadth_binding: dict | None = None,
    *,
    status_binding: dict | None = None,
) -> dict:
    result = base.build_checkpoint(
        parameters,
        factors,
        base_evidence,
        intraday_binding,
        pit_binding,
        benchmark_validation,
        amount_turnover_binding,
        main_net_flow_requirement,
        status_partial_binding,
        market_breadth_binding,
    )
    if status_binding is None:
        return result

    status_sha = validate_status_binding(status_binding)
    state = result["feature_families"]["status"]
    state.update({
        "formal_feature_ready": True,
        "binding_state": "BOUND_VERIFIED_ARTIFACT",
        "pit_state": "PIT_VERIFIED",
        "source_artifact": STATUS_BINDING_ARTIFACT,
        "source_sha256": status_sha,
        "coverage_start": base.FORMAL_START,
        "coverage_end": base.FORMAL_END,
        "blockers": [],
    })
    result["validated_families"] = sorted(
        family for family, family_state in result["feature_families"].items()
        if family_state.get("formal_feature_ready") is True
    )
    result["missing_or_unvalidated_families"] = sorted(
        family for family, family_state in result["feature_families"].items()
        if family_state.get("formal_feature_ready") is not True
    )
    result["blockers"] = [
        blocker for blocker in result.get("blockers", [])
        if blocker != base.STATUS_UPPER_LIMIT_BLOCKER
    ]
    result["status_binding_artifact"] = STATUS_BINDING_ARTIFACT
    result["status_binding_sha256"] = status_sha
    result["status_definition_origin"] = "NEW_RECONSTRUCTION_CANDIDATE"
    result["status_semantic_state"] = copy.deepcopy(status_binding["semantic_state"])

    # Closing status does not open any global adoption/model/OOS gates. Other
    # unresolved feature and supporting-evidence blockers remain authoritative.
    if result["blockers"]:
        result["candidate_scoring_ready"] = False
        result["real_feature_inputs_validated"] = False
    result["model_freeze_allowed"] = False
    result["oos_metrics_allowed"] = False
    result["historical_strategy_recovered"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build GP12 candidate readiness with verified full status binding"
    )
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--factors", required=True)
    parser.add_argument("--base-evidence", required=True)
    parser.add_argument("--intraday-binding", required=True)
    parser.add_argument("--pit-binding", required=True)
    parser.add_argument("--benchmark-validation", required=True)
    parser.add_argument("--amount-turnover-binding", required=True)
    parser.add_argument("--main-net-flow-requirement", required=True)
    parser.add_argument("--status-partial-binding", required=True)
    parser.add_argument("--status-binding", required=True)
    parser.add_argument("--market-breadth-binding")
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
        _load(args.main_net_flow_requirement),
        _load(args.status_partial_binding),
        _load(args.market_breadth_binding) if args.market_breadth_binding else None,
        status_binding=_load(args.status_binding),
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "artifact": report["artifact"],
        "asset_hashes": report["asset_hashes"],
        "status_binding_sha256": report["status_binding_sha256"],
        "status_semantic_state": report["status_semantic_state"],
        "validated_families": report["validated_families"],
        "missing_or_unvalidated_families": report["missing_or_unvalidated_families"],
        "ready_factor_ids": report["ready_factor_ids"],
        "blocked_factor_ids": report["blocked_factor_ids"],
        "blockers": report["blockers"],
        "candidate_scoring_ready": report["candidate_scoring_ready"],
        "model_freeze_allowed": report["model_freeze_allowed"],
        "oos_metrics_allowed": report["oos_metrics_allowed"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["candidate_benchmark_reference_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
