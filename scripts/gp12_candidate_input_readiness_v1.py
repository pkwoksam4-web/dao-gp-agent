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
MAIN_NET_FLOW_REQUIREMENT_ARTIFACT = "GP12_MAIN_NET_FLOW_SOURCE_REQUIREMENT_V1"
MAIN_NET_FLOW_REQUIREMENT_SHA256 = "13577a123a506750d1070c91c96bb603aa727fb9f7826a5cb449efe39963fed3"
STATUS_PARTIAL_BINDING_ARTIFACT = "GP12_CANDIDATE_STATUS_PARTIAL_BINDING_V1"
STATUS_PARTIAL_BINDING_SHA256 = "e565742e9baaa37de5563aa9c51ff2a4a6b9166c1f1579945b865f69d909cb10"
STATUS_UPPER_LIMIT_BLOCKER = "STATUS_UPPER_LIMIT_UNBOUND"
MARKET_BREADTH_BINDING_ARTIFACT = "GP12_CANDIDATE_MARKET_BREADTH_BINDING_V1"
MARKET_BREADTH_BINDING_SHA256 = "337f6dafa3894c55fb8f24b87779d600c9258b1c09f10b8b140d65a120eed1c1"
MAIN_NET_FLOW_BLOCKERS = [
    "MAIN_NET_FLOW_UNBOUND",
    "TUSHARE_CREDENTIAL_REQUIRED",
    "MAIN_NET_FLOW_PANEL_NOT_MATERIALIZED",
]
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


def validate_main_net_flow_requirement(requirement: dict) -> str:
    """Validate the exact unresolved main-net-flow source requirement.

    This is blocker evidence, not a data binding. It must remain impossible for
    this artifact to promote ``main_net_flow`` while the credential and panel
    are absent.
    """
    _require(isinstance(requirement, dict), "main-net-flow requirement must be an object")
    requirement_sha = _canonical_json_sha256(requirement)
    _require(
        requirement_sha == MAIN_NET_FLOW_REQUIREMENT_SHA256,
        "MAIN_NET_FLOW_REQUIREMENT_IDENTITY_MISMATCH",
    )
    _require(requirement.get("artifact") == MAIN_NET_FLOW_REQUIREMENT_ARTIFACT, "main-net-flow requirement artifact mismatch")
    _require(requirement.get("version") == "1.0", "main-net-flow requirement version mismatch")
    _require(requirement.get("strategy_id") == "GP12_REBUILD_CANDIDATE_V1", "main-net-flow strategy mismatch")
    _require(requirement.get("status") == "CANDIDATE_ONLY_UNAPPROVED", "main-net-flow status mismatch")
    _require(requirement.get("origin") == "NEW_RECONSTRUCTION_CANDIDATE", "main-net-flow origin mismatch")
    _require(requirement.get("formal_window") == [FORMAL_START, FORMAL_END], "main-net-flow formal window mismatch")
    _require(requirement.get("universe_n") == 847, "main-net-flow universe mismatch")
    _require(requirement.get("formal_symbol_n") == 844, "main-net-flow formal-symbol mismatch")
    _require(requirement.get("na_symbols") == NA_SYMBOLS, "main-net-flow N/A partition mismatch")
    _require(requirement.get("expected_trade_rows") == EXPECTED_TRADE_ROWS, "main-net-flow expected rows mismatch")
    _require(requirement.get("semantic_definition") == "large_plus_extra_large_active_buy_minus_sell", "main-net-flow semantic definition mismatch")
    _require(requirement.get("candidate_field") == "main_net_flow_cny", "main-net-flow field mismatch")
    _require(requirement.get("source_amount_unit") == "wan_cny", "main-net-flow source unit mismatch")
    _require(requirement.get("candidate_unit") == "cny", "main-net-flow candidate unit mismatch")

    pit_state = requirement.get("pit") or {}
    _require(pit_state.get("scope") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "main-net-flow PIT scope mismatch")
    _require(pit_state.get("same_session_main_net_flow_usable_before_close") is False, "same-session main-net-flow lookahead allowed")
    _require(pit_state.get("historical_provider_publication_timestamp_proven") is False, "main-net-flow provider publication timestamp must remain unproven")

    axis = requirement.get("expected_date_axis") or {}
    _require(axis.get("source_provider") == "Sohu", "main-net-flow expected-date provider mismatch")
    _require(axis.get("source_artifact_name") == "gp-sohu-full-raw-v482-reaudit", "main-net-flow expected-date artifact mismatch")
    _require(axis.get("workflow_run") == 34192233633, "main-net-flow expected-date run mismatch")
    _require(axis.get("artifact_id") == 10042614517, "main-net-flow expected-date artifact id mismatch")
    _require(axis.get("artifact_zip_sha256") == "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550", "main-net-flow expected-date artifact digest mismatch")
    _require(axis.get("raw_panel_sha256") == "bc72238d046378cf3b6fa61723e86fb43f1c491ac3da86d76932e3185f60e1eb", "main-net-flow raw panel digest mismatch")
    _require(axis.get("scope_sha256") == "9e64e111c5eeff1f43fcce6e920d7e5590aa5bb14268c482bbdfe1a936affef8", "main-net-flow scope digest mismatch")
    _require(axis.get("preflight_run") == 35044495123, "main-net-flow preflight run mismatch")
    _require(axis.get("preflight_artifact_name") == "gp12-main-net-flow-preflight-v1", "main-net-flow preflight artifact mismatch")
    _require(axis.get("preflight_artifact_id") == 10426418457, "main-net-flow preflight artifact id mismatch")
    _require(axis.get("preflight_artifact_zip_sha256") == "2ad7b5f9aa682140e745dd2fd1b5f01f3489c0f26dd1910890b4dee9ce472772", "main-net-flow preflight digest mismatch")
    _require(axis.get("source_axis_verified") is True, "main-net-flow source axis not verified")

    source = requirement.get("selected_source") or {}
    _require(source.get("provider") == "Tushare Pro", "main-net-flow source provider mismatch")
    _require(source.get("interface") == "moneyflow", "main-net-flow source interface mismatch")
    _require(source.get("official_documentation") == "https://tushare.pro/document/2?doc_id=170", "main-net-flow source documentation mismatch")
    _require(source.get("documented_history_start") == "2010", "main-net-flow source history mismatch")
    _require(source.get("documented_single_request_max_rows") == 6000, "main-net-flow source request limit mismatch")
    _require(source.get("documented_total_limit") == "unlimited", "main-net-flow source total-limit mismatch")
    _require(source.get("documented_minimum_points") == 2000, "main-net-flow source permission mismatch")
    _require(
        source.get("required_fields")
        == ["ts_code", "trade_date", "buy_lg_amount", "sell_lg_amount", "buy_elg_amount", "sell_elg_amount"],
        "main-net-flow source fields mismatch",
    )
    _require(source.get("credential_secret_name") == "TUSHARE_TOKEN", "main-net-flow secret name mismatch")

    credential = requirement.get("credential_probe") or {}
    _require(credential.get("workflow_run") == 35043809061, "main-net-flow credential probe mismatch")
    _require(credential.get("status") == "MISSING", "main-net-flow credential must remain missing in requirement artifact")
    _require(credential.get("real_source_fetch_validated") is False, "main-net-flow real source fetch cannot be claimed")

    source_workflow = requirement.get("source_workflow") or {}
    _require(source_workflow.get("path") == ".github/workflows/gp12-main-net-flow-source-v1.yml", "main-net-flow workflow path mismatch")
    _require(source_workflow.get("head_sha") == "8a4db43e174849cafb1e80b3b69da18b24340225", "main-net-flow workflow head mismatch")
    _require(source_workflow.get("verification_run") == 35044589492, "main-net-flow workflow run mismatch")
    _require(source_workflow.get("overall_status") == "SUCCESS", "main-net-flow workflow verification mismatch")
    _require(source_workflow.get("preflight_status") == "SUCCESS", "main-net-flow preflight status mismatch")
    _require(source_workflow.get("credential_status") == "MISSING", "main-net-flow workflow credential status mismatch")
    _require(source_workflow.get("source_shards_status") == "SKIPPED", "main-net-flow source shards must remain skipped")
    _require(source_workflow.get("aggregate_status") == "SKIPPED", "main-net-flow aggregate must remain skipped")
    _require(source_workflow.get("source_shard_count") == 4, "main-net-flow shard count mismatch")
    _require(source_workflow.get("max_parallel") == 1, "main-net-flow concurrency mismatch")

    resolution = requirement.get("resolution_state") or {}
    _require(resolution.get("engineering_ready") is True, "main-net-flow engineering readiness mismatch")
    _require(resolution.get("source_axis_verified") is True, "main-net-flow source-axis readiness mismatch")
    _require(resolution.get("credential_available") is False, "main-net-flow credential cannot be claimed available")
    _require(resolution.get("panel_materialized") is False, "main-net-flow panel cannot be claimed materialized")
    _require(resolution.get("main_net_flow_candidate_pit_verified") is False, "main-net-flow PIT cannot be claimed verified")
    _require(requirement.get("historical_gp_v11_source_recovered") is False, "historical GP V1.1 source recovery cannot be claimed")
    _require(requirement.get("model_freeze_allowed") is False, "main-net-flow requirement cannot open model freeze")
    _require(requirement.get("oos_metrics_allowed") is False, "main-net-flow requirement cannot open OOS metrics")
    _require(requirement.get("blockers") == ["TUSHARE_CREDENTIAL_REQUIRED", "MAIN_NET_FLOW_PANEL_NOT_MATERIALIZED"], "main-net-flow requirement blockers mismatch")
    return requirement_sha


def validate_market_breadth_binding(binding: dict) -> str:
    """Validate the exact candidate-only market-breadth reconstruction binding."""
    _require(isinstance(binding, dict), "market-breadth binding must be an object")
    binding_sha = _canonical_json_sha256(binding)
    _require(binding_sha == MARKET_BREADTH_BINDING_SHA256, "MARKET_BREADTH_BINDING_IDENTITY_MISMATCH")
    _require(binding.get("artifact") == MARKET_BREADTH_BINDING_ARTIFACT, "market-breadth artifact mismatch")
    _require(binding.get("version") == "1.0", "market-breadth version mismatch")
    _require(binding.get("strategy_id") == "GP12_REBUILD_CANDIDATE_V1", "market-breadth strategy mismatch")
    _require(binding.get("status") == "CANDIDATE_ONLY_UNAPPROVED", "market-breadth status mismatch")
    _require(binding.get("origin") == "NEW_RECONSTRUCTION_CANDIDATE", "market-breadth origin mismatch")
    _require(binding.get("formal_window") == [FORMAL_START, FORMAL_END], "market-breadth formal window mismatch")
    _require(binding.get("universe_n") == 847, "market-breadth universe mismatch")
    _require(binding.get("formal_symbol_n") == 844, "market-breadth formal-symbol mismatch")
    _require(binding.get("na_symbols") == NA_SYMBOLS, "market-breadth N/A partition mismatch")
    _require(binding.get("date_n") == 1426, "market-breadth date coverage mismatch")

    definition = binding.get("definition") or {}
    _require(definition.get("candidate_field") == "market_breadth_ratio", "market-breadth field mismatch")
    _require(definition.get("formula") == "advancers/(advancers+decliners)", "market-breadth formula mismatch")
    _require(definition.get("advancer") == "current PIT-adjusted close > previous comparable traded PIT-adjusted close", "market-breadth advancer semantics mismatch")
    _require(definition.get("decliner") == "current PIT-adjusted close < previous comparable traded PIT-adjusted close", "market-breadth decliner semantics mismatch")
    _require(definition.get("flat") == "excluded from denominator", "market-breadth flat semantics mismatch")
    _require(definition.get("first_trade_without_prior_comparable_trade") == "excluded from denominator", "market-breadth first-trade semantics mismatch")

    feasibility = binding.get("feasibility_source") or {}
    _require(feasibility.get("workflow_run") == 35053614838, "market-breadth feasibility run mismatch")
    _require(feasibility.get("artifact_name") == "gp12-market-breadth-feasibility-v1", "market-breadth feasibility artifact mismatch")
    _require(feasibility.get("artifact_id") == 10429504424, "market-breadth feasibility artifact id mismatch")
    _require(feasibility.get("artifact_zip_sha256") == "96e37573e48c37b9b3f021d59f4bce93a476c87cc53308fc0c1f83e93abb5c99", "market-breadth feasibility digest mismatch")
    _require(feasibility.get("raw_trade_rows") == EXPECTED_TRADE_ROWS, "market-breadth feasibility raw rows mismatch")
    _require(feasibility.get("directly_comparable_rows") == 1_010_763, "market-breadth comparable rows mismatch")
    _require(feasibility.get("bridge_rows") == 844, "market-breadth bridge rows mismatch")

    bridge = binding.get("bridge_source") or {}
    _require(bridge.get("workflow_run") == 35054180237, "market-breadth bridge run mismatch")
    _require(bridge.get("workflow_head") == "6a0eb77dd54c7cabda128f1d84f9954eba2d0037", "market-breadth bridge head mismatch")
    _require(bridge.get("artifact_name") == "gp12-market-breadth-bridge-v1", "market-breadth bridge artifact mismatch")
    _require(bridge.get("artifact_id") == 10429659699, "market-breadth bridge artifact id mismatch")
    _require(bridge.get("artifact_zip_sha256") == "9615dba0c2eb9c3db2cd04cf8d5ecf2509752f419fb65ef38815b851185b8031", "market-breadth bridge digest mismatch")
    _require(bridge.get("candidate_series_sha256") == "7aaa527806d373133fbedd202b92d3e5da8b903099cfc3335b267951ead3c788", "market-breadth series digest mismatch")
    _require(bridge.get("status") == "PASS_COMPLETE_CANDIDATE_SERIES", "market-breadth bridge status mismatch")
    _require(bridge.get("old_lifecycle_bridge_n") == 737, "market-breadth old-lifecycle bridge count mismatch")
    _require(bridge.get("bridge_resolved_n") == 737, "market-breadth resolved bridge count mismatch")
    _require(bridge.get("old_lifecycle_no_previous_trade_excluded_n") == 0, "market-breadth unresolved old-lifecycle bridge remains")
    _require(bridge.get("new_lifecycle_first_trade_excluded_n") == 107, "market-breadth new-lifecycle exclusion mismatch")
    expected_shards = [
        (0, 10430435903, "8dfa53d6639873e8fcc9a7a1be6c1a800b4ecfc9a57dc980a301c63fdd4eb744"),
        (1, 10429857095, "b0cb15e0a3cadfe9004bef4fd4dd652a80c7e5f1620a333256b7f64fe960e563"),
        (2, 10429329110, "1aa46d19519a71718d1c730ebddd5cd7ba26ee213eaf921912ab92d909d10cc9"),
        (3, 10430096336, "0a760ca1fe2bc0cda9e886cc907f829ad9008528c45d5a656f763b0d289c103b"),
        (4, 10430475749, "a01378872d3142f16ab3c3efb2f081908916b92a9a6d3ead420eacc7a6f4a7fd"),
        (5, 10429808408, "0ba93455fd59e87ee9f6f35227fc0070c31a3b17efb0f152d0f76afe0e6d6509"),
        (6, 10429817130, "1ae133119fa0aae58e91d2233873140d2b087642cdaa0ea70460c1be2a6e2991"),
        (7, 10430600407, "53410e8a9147c493230cc4aa1c91913383f93d2bbae93146855bc9b2130ef58a"),
    ]
    actual_shards = [(row.get("shard"), row.get("artifact_id"), row.get("artifact_zip_sha256")) for row in (bridge.get("bridge_shards") or [])]
    _require(actual_shards == expected_shards, "market-breadth bridge shard identities mismatch")

    adjusted = binding.get("pit_adjusted_close_source") or {}
    _require(adjusted.get("workflow_run") == 34928104668, "market-breadth adjusted-close run mismatch")
    _require(adjusted.get("workflow_head") == "30a826f2e4e1dc4350b3e89453e66848a8d5141f", "market-breadth adjusted-close head mismatch")
    _require(adjusted.get("artifact_name") == "gp12-pit-adjusted-close-full-audit-v482", "market-breadth adjusted-close artifact mismatch")
    _require(adjusted.get("artifact_id") == 10380675799, "market-breadth adjusted-close artifact id mismatch")
    _require(adjusted.get("artifact_zip_sha256") == "fb57bce61a9156fa3d2bb327dc1d8dba70c6fa9739eb7d87bfb5a3e88c6e9b3f", "market-breadth adjusted-close digest mismatch")
    _require(adjusted.get("audit_json_sha256") == "2d75ace7461d4e7879e49a1678bb0d51f0acc3ca3abdc380c068876c1c569c6e", "market-breadth adjusted-close audit digest mismatch")
    _require(adjusted.get("formal_symbol_n") == 844, "market-breadth adjusted-close symbol coverage mismatch")
    _require(adjusted.get("raw_trade_rows") == EXPECTED_TRADE_ROWS, "market-breadth adjusted-close row coverage mismatch")
    _require(adjusted.get("constant_scale_pass_n") == 844 and adjusted.get("constant_scale_fail_n") == 0, "market-breadth adjusted-close audit not fully green")
    _require(adjusted.get("adjusted_close_pit_verified") is True, "market-breadth adjusted-close PIT not verified")

    raw = binding.get("raw_trade_source") or {}
    _require(raw.get("provider") == "Sohu", "market-breadth raw provider mismatch")
    _require(raw.get("workflow_run") == 34192233633, "market-breadth raw run mismatch")
    _require(raw.get("artifact_name") == "gp-sohu-full-raw-v482-reaudit", "market-breadth raw artifact mismatch")
    _require(raw.get("artifact_id") == 10042614517, "market-breadth raw artifact id mismatch")
    _require(raw.get("artifact_zip_sha256") == "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550", "market-breadth raw artifact digest mismatch")
    _require(raw.get("formal_trade_rows") == EXPECTED_TRADE_ROWS, "market-breadth raw row coverage mismatch")

    pit_state = binding.get("pit") or {}
    _require(pit_state.get("scope") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "market-breadth PIT scope mismatch")
    _require(pit_state.get("same_session_market_breadth_usable_before_close") is False, "same-session market breadth lookahead allowed")
    _require(pit_state.get("historical_provider_publication_timestamp_proven") is False, "market-breadth provider publication timestamp must remain unproven")
    _require(pit_state.get("market_breadth_candidate_pit_verified") is True, "market-breadth candidate PIT not verified")
    _require(binding.get("historical_gp_v11_source_recovered") is False, "historical GP V1.1 market breadth recovery cannot be claimed")
    _require(binding.get("family_ready") is True, "market-breadth family readiness mismatch")
    _require(binding.get("model_freeze_allowed") is False, "market-breadth binding cannot open model freeze")
    _require(binding.get("oos_metrics_allowed") is False, "market-breadth binding cannot open OOS metrics")
    _require(binding.get("blockers") == [], "market-breadth binding blockers remain")
    return binding_sha


def validate_status_partial_binding(binding: dict) -> str:
    """Validate candidate-only partial status evidence without promoting status."""
    _require(isinstance(binding, dict), "status partial binding must be an object")
    binding_sha = _canonical_json_sha256(binding)
    _require(binding_sha == STATUS_PARTIAL_BINDING_SHA256, "STATUS_PARTIAL_BINDING_IDENTITY_MISMATCH")
    _require(binding.get("artifact") == STATUS_PARTIAL_BINDING_ARTIFACT, "status partial artifact mismatch")
    _require(binding.get("version") == "1.0", "status partial version mismatch")
    _require(binding.get("strategy_id") == "GP12_REBUILD_CANDIDATE_V1", "status partial strategy mismatch")
    _require(binding.get("status") == "CANDIDATE_ONLY_UNAPPROVED", "status partial status mismatch")
    _require(binding.get("origin") == "NEW_RECONSTRUCTION_CANDIDATE", "status partial origin mismatch")
    _require(binding.get("formal_window") == [FORMAL_START, FORMAL_END], "status partial formal window mismatch")
    _require(binding.get("universe_n") == 847, "status partial universe mismatch")
    _require(binding.get("required_status_fields") == ["is_st", "tradable", "upper_limit"], "status field contract mismatch")

    st = binding.get("is_st_source") or {}
    _require(st.get("field") == "isST", "is_st field mismatch")
    _require(st.get("workflow_run") == 33977325822, "is_st run mismatch")
    _require(st.get("workflow_head") == "a552c5855a96c526178da15837f2d9d488e2d2e6", "is_st head mismatch")
    _require(st.get("artifact_name") == "gp-pit-st-v480-final-audit", "is_st artifact mismatch")
    _require(st.get("artifact_id") == 9972698555, "is_st artifact id mismatch")
    _require(st.get("artifact_zip_sha256") == "a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58", "is_st artifact digest mismatch")
    _require(st.get("overlay_csv_sha256") == "6ed8ffd09215bccb90f716af26d44f7f590ffd5d455c20841307484a63aaa490", "is_st overlay digest mismatch")
    _require(st.get("lifecycle_rows") == 1_021_953, "is_st lifecycle rows mismatch")
    _require(st.get("lifecycle_pass_n") == 847, "is_st lifecycle coverage mismatch")
    _require(st.get("transition_crosscheck_pass_n") == 6, "is_st transition pass mismatch")
    _require(st.get("transition_crosscheck_evidence_n") == 6, "is_st transition evidence mismatch")

    tradable = binding.get("tradable_source") or {}
    _require(tradable.get("workflow_run") == 35052354861, "tradable run mismatch")
    _require(tradable.get("workflow_head") == "627e5504afa71774437b9ba1c3cc5d95f188d74d", "tradable head mismatch")
    _require(tradable.get("artifact_name") == "gp12-status-tradable-probe-v1", "tradable artifact mismatch")
    _require(tradable.get("artifact_id") == 10428808437, "tradable artifact id mismatch")
    _require(tradable.get("artifact_zip_sha256") == "f9808c65cc953953a9920d730640aa2c1c22225a9de75ceddc1ac55433916ec7", "tradable artifact digest mismatch")
    _require(tradable.get("probe_json_sha256") == "09559b86e0bf7424789c2c6f196b5ca1d2c941fdedb4d8c757ca335084617574", "tradable probe digest mismatch")
    _require(tradable.get("positive_trade_rows") == EXPECTED_TRADE_ROWS, "tradable positive rows mismatch")
    _require(tradable.get("nontrade_lifecycle_rows") == 10_346, "tradable nontrade rows mismatch")
    _require(tradable.get("provider_status_misflag_n") == 5, "tradable provider-status trace mismatch")
    _require(tradable.get("status1_but_no_positive_trade_n") == 0, "tradable false-positive status mismatch")

    semantic = binding.get("semantic_state") or {}
    _require(semantic == {"is_st": "BOUND_PIT_VERIFIED", "tradable": "BOUND_PIT_VERIFIED", "upper_limit": "UNBOUND"}, "status semantic state mismatch")
    pit_state = binding.get("pit") or {}
    _require(pit_state.get("scope") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "status PIT scope mismatch")
    _require(pit_state.get("same_session_status_usable_before_close") is False, "same-session status lookahead allowed")
    _require(pit_state.get("historical_provider_publication_timestamp_proven") is False, "status provider publication timestamp must remain unproven")
    _require(binding.get("family_ready") is False, "partial status binding cannot claim family ready")
    _require(binding.get("historical_gp_v11_source_recovered") is False, "historical GP V1.1 status source recovery cannot be claimed")
    _require(binding.get("model_freeze_allowed") is False, "partial status binding cannot open model freeze")
    _require(binding.get("oos_metrics_allowed") is False, "partial status binding cannot open OOS metrics")
    _require(binding.get("blockers") == [STATUS_UPPER_LIMIT_BLOCKER], "status partial blockers mismatch")
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
    main_net_flow_requirement: dict | None = None,
    status_partial_binding: dict | None = None,
    market_breadth_binding: dict | None = None,
) -> dict:
    """Compose current verified GP12 candidate input readiness.

    Existing PIT/intraday integrations remain authoritative. The verified
    candidate-only amount/turnover binding adds one scorer family without
    making any historical GP V1.1 recovery claim. The main-net-flow source
    requirement can add precise blocker detail but can never promote that
    family. CSI All Share / 000985 is still benchmark-reference only and cannot
    substitute for the frozen ``market_adjusted_close`` feature family.
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
    main_net_flow_requirement_sha = None
    if main_net_flow_requirement is not None:
        main_net_flow_requirement_sha = validate_main_net_flow_requirement(
            main_net_flow_requirement
        )
    status_partial_binding_sha = None
    if status_partial_binding is not None:
        status_partial_binding_sha = validate_status_partial_binding(status_partial_binding)
    market_breadth_binding_sha = None
    if market_breadth_binding is not None:
        market_breadth_binding_sha = validate_market_breadth_binding(market_breadth_binding)

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
    if status_partial_binding_sha is not None:
        derived_evidence["feature_families"]["status"] = {
            "binding_state": "BOUND_STRUCTURAL_ONLY",
            "pit_state": "PIT_PARTIAL",
            "source_artifact": STATUS_PARTIAL_BINDING_ARTIFACT,
            "source_sha256": status_partial_binding_sha,
            "coverage_start": FORMAL_START,
            "coverage_end": FORMAL_END,
            "blockers": [STATUS_UPPER_LIMIT_BLOCKER],
        }
    if market_breadth_binding_sha is not None:
        derived_evidence["feature_families"]["market_breadth"] = {
            "binding_state": "BOUND_VERIFIED_ARTIFACT",
            "pit_state": "PIT_VERIFIED",
            "source_artifact": MARKET_BREADTH_BINDING_ARTIFACT,
            "source_sha256": market_breadth_binding_sha,
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

    main_net_flow = report["feature_families"]["main_net_flow"]
    if main_net_flow.get("formal_feature_ready") is not False:
        raise ValueError("main_net_flow unexpectedly ready before source binding")
    if main_net_flow.get("binding_state") != "UNBOUND":
        raise ValueError("main_net_flow unexpectedly bound before source binding")
    if main_net_flow.get("pit_state") != "PIT_UNVERIFIED":
        raise ValueError("main_net_flow PIT state unexpectedly changed")
    if main_net_flow.get("source_artifact") is not None or main_net_flow.get("source_sha256") is not None:
        raise ValueError("main_net_flow unexpectedly carries source identity")
    if main_net_flow_requirement_sha is not None:
        main_net_flow["blockers"] = list(MAIN_NET_FLOW_BLOCKERS)

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
        "main_net_flow_requirement_artifact": (
            MAIN_NET_FLOW_REQUIREMENT_ARTIFACT
            if main_net_flow_requirement_sha is not None
            else None
        ),
        "main_net_flow_requirement_sha256": main_net_flow_requirement_sha,
        "status_partial_binding_artifact": (
            STATUS_PARTIAL_BINDING_ARTIFACT if status_partial_binding_sha is not None else None
        ),
        "status_partial_binding_sha256": status_partial_binding_sha,
        "market_breadth_binding_artifact": (
            MARKET_BREADTH_BINDING_ARTIFACT if market_breadth_binding_sha is not None else None
        ),
        "market_breadth_binding_sha256": market_breadth_binding_sha,
        "market_breadth_definition_origin": (
            "NEW_RECONSTRUCTION_CANDIDATE" if market_breadth_binding_sha is not None else None
        ),
        "status_semantic_state": (
            copy.deepcopy(status_partial_binding["semantic_state"])
            if status_partial_binding_sha is not None
            else None
        ),
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
            "main_net_flow engineering and Formal844 source axis are verified, but the selected "
            "Tushare route still lacks a credential and no 1,011,607-row panel is materialized"
            if main_net_flow_requirement_sha is not None
            else
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
    parser.add_argument("--main-net-flow-requirement", required=True)
    parser.add_argument("--status-partial-binding", required=True)
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
                "main_net_flow_requirement_sha256": report[
                    "main_net_flow_requirement_sha256"
                ],
                "status_partial_binding_sha256": report[
                    "status_partial_binding_sha256"
                ],
                "market_breadth_binding_sha256": report[
                    "market_breadth_binding_sha256"
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
