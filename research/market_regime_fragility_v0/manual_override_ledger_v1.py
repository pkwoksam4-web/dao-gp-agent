from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime


VERSION = "MANUAL_OVERRIDE_LEDGER_V1"

ALLOWED_SCOPE_TYPES = {
    "SYMBOL",
    "THEME",
    "PORTFOLIO",
    "MODULE",
    "ORDER",
}

ALLOWED_ACTOR_ROLES = {
    "USER",
    "PORTFOLIO_MANAGER",
    "RISK_OWNER",
    "AUTHORIZED_OPERATOR",
}

FORBIDDEN_OUTCOME_KEYS = {
    "pnl",
    "future_return",
    "forward_return",
    "outcome",
    "realized_pnl",
    "hit_rate",
    "win_rate",
}

FORBIDDEN_OUTCOME_PREFIXES = (
    "future_",
    "forward_",
    "outcome_",
    "post_action_",
    "realized_pnl",
)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _canonical_record(record: dict) -> dict:
    normalized = copy.deepcopy(record)
    normalized.pop("record_hash", None)
    normalized["production_authorized"] = False
    refs = normalized.get("evidence_refs")
    if isinstance(refs, list):
        normalized["evidence_refs"] = sorted(refs)
    return normalized


def _hash_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_override_record(record: dict) -> dict:
    reasons: list[str] = []

    if not isinstance(record, dict):
        return {
            "valid": False,
            "reasons": ["OVERRIDE_RECORD_NOT_OBJECT"],
            "record_hash": None,
            "original_action": None,
            "override_action": None,
            "production_authorized": False,
            "version": VERSION,
        }

    if not record.get("override_id"):
        reasons.append("OVERRIDE_ID_MISSING")

    recorded_at = _parse_timestamp(record.get("recorded_at"))
    action_cutoff = _parse_timestamp(record.get("action_cutoff"))
    if recorded_at is None:
        reasons.append("RECORDED_AT_INVALID")
    if action_cutoff is None:
        reasons.append("ACTION_CUTOFF_INVALID")
    if recorded_at is not None and action_cutoff is not None and recorded_at > action_cutoff:
        reasons.append("OVERRIDE_RECORDED_AFTER_ACTION_CUTOFF")

    if record.get("scope_type") not in ALLOWED_SCOPE_TYPES:
        reasons.append("SCOPE_TYPE_INVALID")
    if not record.get("scope_id"):
        reasons.append("SCOPE_ID_MISSING")
    if not record.get("module_version"):
        reasons.append("MODULE_VERSION_MISSING")
    if not record.get("model_output_hash"):
        reasons.append("MODEL_OUTPUT_HASH_MISSING")

    original_action = record.get("original_action")
    override_action = record.get("override_action")
    if not isinstance(original_action, str) or not original_action:
        reasons.append("ORIGINAL_ACTION_MISSING")
    if not isinstance(override_action, str) or not override_action:
        reasons.append("OVERRIDE_ACTION_MISSING")
    if original_action and override_action and original_action == override_action:
        reasons.append("OVERRIDE_ACTION_EQUALS_ORIGINAL")

    if not record.get("reason_code"):
        reasons.append("REASON_CODE_MISSING")
    reason_text = record.get("reason_text")
    if not isinstance(reason_text, str) or not reason_text.strip():
        reasons.append("REASON_TEXT_MISSING")
    if record.get("actor_role") not in ALLOWED_ACTOR_ROLES:
        reasons.append("ACTOR_ROLE_INVALID")

    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not all(isinstance(ref, str) and ref for ref in refs):
        reasons.append("EVIDENCE_REFS_INVALID")

    if record.get("production_authorized") not in {None, False}:
        reasons.append("PRODUCTION_AUTHORIZATION_FORBIDDEN")

    for key in record:
        lowered = key.lower()
        if lowered in FORBIDDEN_OUTCOME_KEYS or any(lowered.startswith(prefix) for prefix in FORBIDDEN_OUTCOME_PREFIXES):
            reasons.append("FUTURE_OUTCOME_FIELD_FORBIDDEN")
            break

    normalized = _canonical_record(record)
    return {
        "valid": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "record_hash": _hash_payload({"version": VERSION, "record": normalized}),
        "original_action": original_action,
        "override_action": override_action,
        "production_authorized": False,
        "version": VERSION,
    }


def build_ledger(records: list[dict]) -> dict:
    reasons: list[str] = []

    if not isinstance(records, list):
        return {
            "valid": False,
            "reasons": ["LEDGER_RECORDS_NOT_LIST"],
            "override_count": 0,
            "ledger_hash": None,
            "production_authorized": False,
            "version": VERSION,
        }

    ids: set[str] = set()
    normalized_records: list[dict] = []

    for record in records:
        result = validate_override_record(record)
        if not result["valid"]:
            reasons.extend(f"RECORD_INVALID:{reason}" for reason in result["reasons"])

        override_id = record.get("override_id") if isinstance(record, dict) else None
        if override_id:
            if override_id in ids:
                reasons.append("DUPLICATE_OVERRIDE_ID")
            ids.add(override_id)

        if isinstance(record, dict):
            normalized_records.append(_canonical_record(record))

    normalized_records.sort(key=lambda item: (item.get("override_id", ""), item.get("recorded_at", "")))
    ledger_payload = {
        "version": VERSION,
        "records": normalized_records,
    }

    return {
        "valid": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "override_count": len(normalized_records),
        "ledger_hash": _hash_payload(ledger_payload),
        "production_authorized": False,
        "version": VERSION,
    }
