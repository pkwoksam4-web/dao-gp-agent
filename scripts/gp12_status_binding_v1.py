from __future__ import annotations

import copy
import re

FORMAL_WINDOW = ["2020-06-01", "2026-04-17"]
REQUIRED_FIELDS = ["is_st", "tradable", "upper_limit"]
REQUIRED_SEMANTIC_STATE = {
    "is_st": "BOUND_PIT_VERIFIED",
    "tradable": "BOUND_PIT_VERIFIED",
    "upper_limit": "BOUND_PIT_VERIFIED",
}
EXPECTED_COUNTS = {
    "panel_rows": 1021953,
    "panel_symbols": 847,
    "tradable_rows": 1011607,
    "nontradable_rows": 10346,
    "special_no_limit_rows": 9,
    "partial_truth_rows": 896827,
    "partial_truth_symbols": 698,
    "special_evidence_entries": 9,
}
PINNED_SOURCE_IDS = {
    "sohu_raw_run_id": 34192233633,
    "pit_st_final_run_id": 33977325822,
    "pit_st_merged_run_id": 33971534669,
}
PINNED_HASHES = {
    "sohu_raw_parquet_sha256": "bc72238d046378cf3b6fa61723e86fb43f1c491ac3da86d76932e3185f60e1eb",
    "partial_truth_sha256": "d11b415b74d44d63d1aa927e8652f395dd039c28f6e1b4c24964e53759405308",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_hash(value: object, field: str) -> str:
    text = str(value or "").strip().lower()
    _require(bool(HEX64.fullmatch(text)), f"invalid {field}")
    return text


def validate_status_binding(binding: dict) -> dict:
    _require(isinstance(binding, dict), "status binding must be an object")
    doc = copy.deepcopy(binding)

    _require(doc.get("artifact") == "GP12_CANDIDATE_STATUS_BINDING_V1", "status binding artifact mismatch")
    _require(doc.get("version") == "1.0", "status binding version mismatch")
    _require(doc.get("origin") == "NEW_RECONSTRUCTION_CANDIDATE", "status binding origin mismatch")
    _require(doc.get("formal_window") == FORMAL_WINDOW, "status binding Formal window mismatch")
    _require(doc.get("family") == "status", "status binding family mismatch")
    _require(doc.get("required_fields") == REQUIRED_FIELDS, "status binding required fields mismatch")
    _require(doc.get("semantic_state") == REQUIRED_SEMANTIC_STATE, "status binding semantic state mismatch")
    _require(doc.get("family_ready") is True, "status binding family is not ready")
    _require(doc.get("blockers") == [], "status binding blockers must be empty")

    for key, expected in EXPECTED_COUNTS.items():
        _require(doc.get(key) == expected, f"status binding {key} mismatch")
    _require(
        doc["tradable_rows"] + doc["nontradable_rows"] == doc["panel_rows"],
        "status binding tradable/nontradable rows do not sum to panel rows",
    )

    for key, expected in PINNED_SOURCE_IDS.items():
        _require(doc.get(key) == expected, f"status binding {key} mismatch")
    reference_run_id = doc.get("sohu_reference_run_id")
    _require(isinstance(reference_run_id, int) and reference_run_id > 0, "invalid sohu_reference_run_id")

    for key in (
        "panel_sha256",
        "panel_audit_payload_sha256",
        "panel_audit_file_sha256",
        "sohu_reference_panel_sha256",
        "sohu_raw_parquet_sha256",
        "partial_truth_sha256",
    ):
        normalized = _require_hash(doc.get(key), key)
        if key in PINNED_HASHES:
            _require(normalized == PINNED_HASHES[key], f"status binding {key} identity mismatch")

    _require(
        doc.get("partial_truth_mismatches") == {"no_limit": 0, "price": 0, "boolean": 0},
        "status binding partial truth mismatch counts are not zero",
    )
    _require(
        doc.get("special_evidence_artifact") == "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1",
        "status binding special evidence artifact mismatch",
    )
    _require(doc.get("pit_policy") == "SESSION_CLOSE_NO_LOOKAHEAD_POLICY", "status binding PIT policy mismatch")
    _require(
        doc.get("historical_provider_publication_timestamp_proven") is False,
        "status binding publication-timestamp provenance overclaim",
    )
    _require(doc.get("historical_gp_v11_source_recovered") is False, "status binding historical GP recovery overclaim")
    _require(doc.get("model_freeze_allowed") is False, "status binding model-freeze overclaim")
    _require(doc.get("oos_metrics_allowed") is False, "status binding OOS overclaim")

    return doc
