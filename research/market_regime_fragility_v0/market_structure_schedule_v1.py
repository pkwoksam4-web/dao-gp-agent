from __future__ import annotations

import copy
import hashlib
import json
from datetime import date


VERSION = "A_SHARE_MARKET_STRUCTURE_REGIME_SCHEDULE_V1"
FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"

ALLOWED_AXES = {
    "BOARD_PRICE_LIMIT_REGIME",
    "IPO_NEW_LISTING_REGIME",
    "BOARD_TAXONOMY_REGIME",
    "TRANSACTION_COST_REGIME",
    "FINANCING_REGIME",
    "SHORT_HEDGE_REGIME",
    "PROGRAM_TRADING_REGULATORY_REGIME",
}

ALLOWED_CAUSAL_USES = {
    "DIRECT_EXECUTION",
    "TAXONOMY_ONLY",
    "FINANCING_ONLY",
    "HEDGE_ONLY",
    "CONTEXT_ONLY",
    "CROSS_BORDER_FLOW_CONTEXT",
}


def _iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _valid_urls(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.startswith("https://") for item in value)
    )


def _normalize_for_hash(schedule: dict) -> dict:
    normalized = copy.deepcopy(schedule)
    normalized.pop("schedule_hash", None)

    if isinstance(normalized.get("axes"), list):
        normalized["axes"] = sorted(normalized["axes"])
    if isinstance(normalized.get("unresolved_requirements"), list):
        normalized["unresolved_requirements"] = sorted(normalized["unresolved_requirements"])
    if isinstance(normalized.get("baseline_states"), list):
        normalized["baseline_states"] = sorted(
            normalized["baseline_states"], key=lambda item: item.get("baseline_id", "")
        )
    if isinstance(normalized.get("events"), list):
        normalized["events"] = sorted(normalized["events"], key=lambda item: item.get("event_id", ""))
        for event in normalized["events"]:
            if isinstance(event.get("axes"), list):
                event["axes"] = sorted(event["axes"])
            if isinstance(event.get("source_urls"), list):
                event["source_urls"] = sorted(event["source_urls"])
    if isinstance(normalized.get("post_cutoff_exclusions"), list):
        normalized["post_cutoff_exclusions"] = sorted(
            normalized["post_cutoff_exclusions"], key=lambda item: item.get("event_id", "")
        )

    return normalized


def _schedule_hash(schedule: dict) -> str:
    payload = json.dumps(
        _normalize_for_hash(schedule),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_schedule(schedule: dict) -> dict:
    reasons: list[str] = []

    if not isinstance(schedule, dict):
        return {
            "valid": False,
            "reasons": ["SCHEDULE_NOT_OBJECT"],
            "schedule_hash": None,
            "formal_evaluation_scope_complete": False,
            "production_authorized": False,
        }

    if schedule.get("schedule_version") != VERSION:
        reasons.append("SCHEDULE_VERSION_MISMATCH")

    formal_window = schedule.get("formal_window")
    if not isinstance(formal_window, dict) or formal_window.get("start") != FORMAL_START or formal_window.get("end") != FORMAL_END:
        reasons.append("FORMAL_WINDOW_MISMATCH")

    status = schedule.get("status")
    if status not in {"PARTIAL_SOURCE_BOUND", "SOURCE_BOUND_COMPLETE"}:
        reasons.append("SCHEDULE_STATUS_INVALID")

    complete = schedule.get("formal_evaluation_scope_complete") is True
    if status == "PARTIAL_SOURCE_BOUND" and complete:
        reasons.append("PARTIAL_SCHEDULE_CANNOT_BE_FORMAL_COMPLETE")

    if schedule.get("production_authorized") is not False:
        reasons.append("PRODUCTION_AUTHORIZATION_INVALID")

    axes = schedule.get("axes")
    if not isinstance(axes, list) or set(axes) != ALLOWED_AXES:
        reasons.append("AXIS_REGISTRY_MISMATCH")

    baselines = schedule.get("baseline_states")
    if not isinstance(baselines, list) or not baselines:
        reasons.append("BASELINE_STATES_MISSING")
        baselines = []

    baseline_ids: set[str] = set()
    for baseline in baselines:
        if not isinstance(baseline, dict):
            reasons.append("BASELINE_RECORD_INVALID")
            continue
        baseline_id = baseline.get("baseline_id")
        if not baseline_id:
            reasons.append("BASELINE_ID_MISSING")
        elif baseline_id in baseline_ids:
            reasons.append("DUPLICATE_BASELINE_ID")
        else:
            baseline_ids.add(baseline_id)
        if baseline.get("source_bound") is not True:
            reasons.append("BASELINE_SOURCE_NOT_BOUND")
        source_url = baseline.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            reasons.append("BASELINE_SOURCE_URL_INVALID")
        if baseline.get("axis") not in ALLOWED_AXES:
            reasons.append("BASELINE_AXIS_INVALID")
        if baseline.get("causal_use") not in ALLOWED_CAUSAL_USES:
            reasons.append("BASELINE_CAUSAL_USE_INVALID")
        if _iso_date(baseline.get("as_of")) is None:
            reasons.append("BASELINE_ASOF_INVALID")

    events = schedule.get("events")
    if not isinstance(events, list) or not events:
        reasons.append("EVENTS_MISSING")
        events = []

    formal_end = date.fromisoformat(FORMAL_END)
    event_ids: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            reasons.append("EVENT_RECORD_INVALID")
            continue
        event_id = event.get("event_id")
        if not event_id:
            reasons.append("EVENT_ID_MISSING")
        elif event_id in event_ids:
            reasons.append("DUPLICATE_EVENT_ID")
        else:
            event_ids.add(event_id)

        effective_date = _iso_date(event.get("effective_date"))
        if effective_date is None:
            reasons.append("EVENT_EFFECTIVE_DATE_INVALID")
        elif effective_date > formal_end:
            reasons.append("EVENT_AFTER_FORMAL_WINDOW")

        first_session = _iso_date(event.get("first_affected_session"))
        if first_session is None:
            reasons.append("FIRST_AFFECTED_SESSION_INVALID")
        elif first_session > formal_end:
            reasons.append("EVENT_AFTER_FORMAL_WINDOW")

        event_axes = event.get("axes")
        if not isinstance(event_axes, list) or not event_axes or not set(event_axes).issubset(ALLOWED_AXES):
            reasons.append("EVENT_AXIS_INVALID")
        if event.get("source_bound") is not True:
            reasons.append("EVENT_SOURCE_NOT_BOUND")
        if not _valid_urls(event.get("source_urls")):
            reasons.append("EVENT_SOURCE_URL_INVALID")
        if not event.get("authority"):
            reasons.append("EVENT_AUTHORITY_MISSING")
        if event.get("causal_use") not in ALLOWED_CAUSAL_USES:
            reasons.append("EVENT_CAUSAL_USE_INVALID")
        if not isinstance(event.get("change"), dict) or not event.get("change"):
            reasons.append("EVENT_CHANGE_MISSING")

    exclusions = schedule.get("post_cutoff_exclusions")
    if not isinstance(exclusions, list):
        reasons.append("POST_CUTOFF_EXCLUSIONS_INVALID")

    unresolved = schedule.get("unresolved_requirements")
    if status == "PARTIAL_SOURCE_BOUND" and (not isinstance(unresolved, list) or not unresolved):
        reasons.append("PARTIAL_SCHEDULE_REQUIRES_UNRESOLVED_LIST")

    return {
        "valid": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "schedule_hash": _schedule_hash(schedule),
        "formal_evaluation_scope_complete": complete,
        "production_authorized": False,
        "schedule_version": schedule.get("schedule_version"),
        "status": status,
    }
