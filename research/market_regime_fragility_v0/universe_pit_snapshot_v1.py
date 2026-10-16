from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

VERSION = "UNIVERSE_PIT_SNAPSHOT_V1"

_VALID_DELISTING = {"NORMAL", "DELISTING", "DELISTED", "UNAVAILABLE"}
_VALID_ST = {"NORMAL", "ST", "STAR_ST", "UNAVAILABLE"}
_VALID_SUSPENSION = {"TRADING", "SUSPENDED", "UNAVAILABLE"}


def _parse_aware(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _canonical_time(value: str) -> str:
    parsed = _parse_aware(value)
    if parsed is None:
        return value
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _snapshot_hash(records: list[dict], asof: str, policy: dict) -> str:
    normalized_records = []
    for item in sorted(records, key=lambda row: str(row.get("symbol", ""))):
        copy = dict(item)
        if isinstance(copy.get("observed_at"), str):
            copy["observed_at"] = _canonical_time(copy["observed_at"])
        if isinstance(copy.get("provenance"), dict):
            copy["provenance"] = dict(sorted(copy["provenance"].items()))
        normalized_records.append(copy)
    payload = {
        "version": VERSION,
        "asof": _canonical_time(asof),
        "policy": dict(sorted(policy.items())),
        "records": normalized_records,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_universe_snapshot(records: list[dict], asof: str, policy_manifest: dict) -> dict:
    reasons: list[str] = []
    cutoff = _parse_aware(asof)
    if cutoff is None:
        reasons.append("INVALID_ASOF")

    liquidity_policy = policy_manifest.get("liquidity_policy_version")
    new_listing_policy = policy_manifest.get("new_listing_policy_version")
    if not isinstance(liquidity_policy, str) or not liquidity_policy.strip():
        reasons.append("LIQUIDITY_POLICY_VERSION_MISSING")
    if not isinstance(new_listing_policy, str) or not new_listing_policy.strip():
        reasons.append("NEW_LISTING_POLICY_VERSION_MISSING")

    if reasons:
        return {
            "version": VERSION,
            "universe_pit_valid": False,
            "universe_snapshot_hash": None,
            "eligible_symbols": [],
            "ineligible_symbols_with_reasons": {},
            "unresolved_symbols": sorted(str(row.get("symbol", "")) for row in records if row.get("symbol")),
            "record_reasons": {},
            "policy_versions": {
                "liquidity_policy_version": liquidity_policy,
                "new_listing_policy_version": new_listing_policy,
            },
            "reasons": reasons,
            "production_authorized": False,
        }

    eligible: list[str] = []
    ineligible: dict[str, list[str]] = {}
    unresolved: list[str] = []
    record_reasons: dict[str, list[str]] = {}

    for item in records:
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        symbol = symbol.strip()
        unresolved_reasons: list[str] = []
        ineligible_reasons: list[str] = []

        observed_at = _parse_aware(item.get("observed_at"))
        if observed_at is None:
            unresolved_reasons.append("INVALID_RECORD_TIMESTAMP")
        elif observed_at > cutoff:
            unresolved_reasons.append("POST_CUTOFF_RECORD")

        if item.get("pit_valid") is not True:
            unresolved_reasons.append("PIT_INVALID")

        provenance = item.get("provenance")
        if not isinstance(provenance, dict) or not provenance or any(not str(v).strip() for v in provenance.values()):
            unresolved_reasons.append("PROVENANCE_MISSING")

        if item.get("delisting_status_at_asof") not in _VALID_DELISTING:
            unresolved_reasons.append("DELISTING_STATUS_INVALID")
        if item.get("st_status_at_asof") not in _VALID_ST:
            unresolved_reasons.append("ST_STATUS_INVALID")
        if item.get("suspension_status_at_asof") not in _VALID_SUSPENSION:
            unresolved_reasons.append("SUSPENSION_STATUS_INVALID")
        if not item.get("board_at_asof") or item.get("board_at_asof") == "UNAVAILABLE":
            unresolved_reasons.append("BOARD_UNAVAILABLE")
        if not item.get("price_limit_rule_id") or item.get("price_limit_rule_id") == "UNAVAILABLE":
            unresolved_reasons.append("PRICE_LIMIT_RULE_MISSING")

        if item.get("liquidity_policy_version") != liquidity_policy or item.get("new_listing_policy_version") != new_listing_policy:
            unresolved_reasons.append("POLICY_VERSION_MISMATCH")

        liquidity_result = item.get("liquidity_eligible_at_asof")
        new_listing_result = item.get("new_listing_eligible_at_asof")
        if liquidity_result not in {True, False} or new_listing_result not in {True, False}:
            unresolved_reasons.append("POLICY_RESULT_UNAVAILABLE")

        if unresolved_reasons:
            unresolved.append(symbol)
            record_reasons[symbol] = sorted(set(unresolved_reasons))
            continue

        if item.get("listed_at_asof") is not True:
            ineligible_reasons.append("NOT_LISTED_AT_ASOF")
        if item.get("delisting_status_at_asof") == "DELISTED":
            ineligible_reasons.append("DELISTED_AT_ASOF")
        if liquidity_result is False:
            ineligible_reasons.append("LIQUIDITY_POLICY_INELIGIBLE")
        if new_listing_result is False:
            ineligible_reasons.append("NEW_LISTING_POLICY_INELIGIBLE")

        if ineligible_reasons:
            ineligible[symbol] = sorted(set(ineligible_reasons))
            record_reasons[symbol] = ineligible[symbol]
        else:
            eligible.append(symbol)
            record_reasons[symbol] = []

    return {
        "version": VERSION,
        "universe_pit_valid": True,
        "universe_snapshot_hash": _snapshot_hash(records, asof, policy_manifest),
        "eligible_symbols": sorted(eligible),
        "ineligible_symbols_with_reasons": dict(sorted(ineligible.items())),
        "unresolved_symbols": sorted(unresolved),
        "record_reasons": dict(sorted(record_reasons.items())),
        "policy_versions": {
            "liquidity_policy_version": liquidity_policy,
            "new_listing_policy_version": new_listing_policy,
        },
        "reasons": [],
        "production_authorized": False,
    }
