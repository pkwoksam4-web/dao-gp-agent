from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json


LEDGER_VERSION = "ATOMIC_EVIDENCE_LEDGER_V1"

DOMAINS = {
    "external_shock": {"VERIFIED", "ABSENT", "UNAVAILABLE"},
    "shock_source_persistence": {
        "SOURCE_RESOLVING",
        "SOURCE_ONGOING",
        "SOURCE_ESCALATING",
        "SOURCE_TRANSIENT_REPRICING",
        "SOURCE_UNVERIFIED",
    },
    "local_transmission_state": {
        "PENDING_TRANSMISSION",
        "IN_TRANSMISSION",
        "REALIZED_SHOCK",
        "REPAIRING",
        "UNRESOLVED",
    },
    "breadth_state": {"HEALTHY", "DIVERGENT", "DETERIORATING", "UNAVAILABLE"},
    "leadership_state": {"HEALTHY", "CONCENTRATED", "DETERIORATING", "UNAVAILABLE"},
    "small_mid_state": {"HEALTHY", "WEAK", "STRESSED", "UNAVAILABLE"},
    "turnover_state": {"HEALTHY", "DISTRIBUTION", "LIQUIDITY_WITHDRAWAL", "UNAVAILABLE"},
    "repair_state": {"NONE", "PARTIAL", "BROAD", "UNAVAILABLE"},
}

REQUIRED_FIELDS = tuple(sorted(DOMAINS))


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _parse_aware_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical_ts(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def validate_and_hash_ledger(
    *,
    decision_cutoff: str,
    evidence: dict[str, dict],
    classifier_version: str,
) -> dict:
    """Validate categorical PIT evidence and emit a deterministic provenance hash.

    This function validates already-categorical evidence only. It deliberately
    does not derive categories from numeric market observations.
    """
    missing_fields: list[str] = []
    invalid_fields: list[str] = []
    reason_codes: list[str] = []
    normalized: dict[str, dict] = {}

    cutoff = _parse_aware_iso(decision_cutoff)
    if cutoff is None:
        _append_once(reason_codes, "INVALID_DECISION_CUTOFF")

    if not isinstance(classifier_version, str) or not classifier_version:
        _append_once(reason_codes, "CLASSIFIER_VERSION_MISSING")

    if not isinstance(evidence, dict):
        evidence = {}

    for field in REQUIRED_FIELDS:
        if field not in evidence:
            missing_fields.append(field)
            _append_once(reason_codes, "REQUIRED_EVIDENCE_UNAVAILABLE")
            continue

        item = evidence[field]
        if not isinstance(item, dict):
            invalid_fields.append(field)
            _append_once(reason_codes, "INVALID_EVIDENCE_ITEM")
            continue

        value = item.get("value")
        provenance = item.get("provenance")
        pit_valid = item.get("pit_valid")
        observed = _parse_aware_iso(item.get("observed_at"))
        field_invalid = False

        if value not in DOMAINS[field]:
            _append_once(reason_codes, "INVALID_ENUM_VALUE")
            field_invalid = True

        if not isinstance(provenance, str) or not provenance.strip():
            _append_once(reason_codes, "PROVENANCE_MISSING")
            field_invalid = True

        if pit_valid is not True:
            _append_once(reason_codes, "PIT_INVALID_EVIDENCE")
            field_invalid = True

        if observed is None:
            _append_once(reason_codes, "INVALID_TIMESTAMP")
            field_invalid = True
        elif cutoff is not None and observed > cutoff:
            _append_once(reason_codes, "STALE_OR_POST_CUTOFF_EVIDENCE")
            field_invalid = True

        if field_invalid:
            invalid_fields.append(field)
            continue

        normalized[field] = {
            "value": value,
            "observed_at": _canonical_ts(observed),
            "provenance": provenance.strip(),
            "pit_valid": True,
        }

    valid = (
        not missing_fields
        and not invalid_fields
        and cutoff is not None
        and isinstance(classifier_version, str)
        and bool(classifier_version)
        and len(normalized) == len(REQUIRED_FIELDS)
    )

    evidence_hash = None
    if valid:
        payload = {
            "ledger_version": LEDGER_VERSION,
            "classifier_version": classifier_version,
            "decision_cutoff": _canonical_ts(cutoff),
            "evidence": {field: normalized[field] for field in REQUIRED_FIELDS},
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        evidence_hash = hashlib.sha256(encoded).hexdigest()

    return {
        "ledger_version": LEDGER_VERSION,
        "valid": valid,
        "normalized_evidence": normalized,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "reason_codes": reason_codes,
        "evidence_hash": evidence_hash,
    }
