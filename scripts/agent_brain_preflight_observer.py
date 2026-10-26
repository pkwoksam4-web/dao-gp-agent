#!/usr/bin/env python3
"""Read-only, observe-only Agent Brain preflight reporter.

This phase deliberately cannot return PASS: database lookback presence and the
authoritative same-day ingest attestation are not yet checked. It has no database
client and never authorizes or dispatches a writer.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
CUTOFF = time(16, 10)
CALENDAR_SCHEMA = "agent-brain-cn-exchange-calendar/v1"
EXPECTED_LOOKBACK_SESSIONS = 31
FROZEN_CALENDAR_SHA256 = {
    2026: "4211957f7916adf07da0b9005e90dbdeb5aba25facb9d5637e47483f2048bd87",
}
MANIFEST_DIR = Path("runtime/pit_manifests")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def evidence_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def _gate(name: str, status: str, checked_at: str, evidence: Any, **details: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "evidence_sha256": evidence_hash(evidence),
        "checked_at": checked_at,
        **details,
    }


def _parse_expiry(value: str) -> datetime | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_authorization(state: str, authorized_until: str, now: datetime) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    expiry = _parse_expiry(authorized_until)
    normalized = (state or "").strip()
    if normalized != "APPROVED":
        status = "FAIL_NOT_AUTHORIZED"
    elif not authorized_until:
        status = "FAIL_EXPIRY_MISSING"
    elif expiry is None:
        status = "FAIL_INVALID_EXPIRY"
    elif expiry <= now.astimezone(timezone.utc):
        status = "FAIL_EXPIRED"
    else:
        status = "PASS"
    # These are non-secret repository variables. Do not add a database URL here.
    evidence = {"authorization": normalized, "authorized_until": authorized_until.strip()}
    return {
        "status": status,
        "authorized_until": authorized_until.strip() or None,
        "evidence": evidence,
    }


def inspect_calendar(calendar_path: Path, trade_date: str) -> dict[str, Any]:
    raw = calendar_path.read_bytes()
    digest = sha256_bytes(raw)
    try:
        calendar = json.loads(raw)
        date.fromisoformat(trade_date)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "PRECHECK_FAIL",
            "error": f"CALENDAR_OR_TRADE_DATE_INVALID: {type(exc).__name__}",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": [],
        }
    if not isinstance(calendar, dict) or calendar.get("schema") != CALENDAR_SCHEMA:
        return {
            "status": "PRECHECK_FAIL",
            "error": "CALENDAR_SCHEMA_MISMATCH",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": [],
        }
    try:
        year = int(calendar["year"])
        sessions = calendar["trading_days"]
        if not isinstance(sessions, list) or any(not isinstance(d, str) for d in sessions):
            raise ValueError("trading_days must be a string array")
        for d in sessions:
            date.fromisoformat(d)
        if sessions != sorted(set(sessions)):
            raise ValueError("trading_days must be sorted and unique")
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "status": "PRECHECK_FAIL",
            "error": f"CALENDAR_CONTENT_INVALID: {type(exc).__name__}",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": [],
        }
    expected_digest = FROZEN_CALENDAR_SHA256.get(year)
    if expected_digest is None:
        return {
            "status": "BLOCKED_CALENDAR_COVERAGE",
            "error": "CALENDAR_SHA256_NOT_FROZEN",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": [],
        }
    if digest != expected_digest:
        return {
            "status": "PRECHECK_FAIL",
            "error": "FROZEN_CALENDAR_SHA256_MISMATCH",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_calendar_sha256": expected_digest,
            "expected_31_session_dates": [],
        }
    trade_year = date.fromisoformat(trade_date).year
    if trade_year != year:
        return {
            "status": "BLOCKED_CALENDAR_COVERAGE",
            "error": f"NO_FROZEN_CALENDAR_FOR_TRADE_DATE_YEAR_{trade_year}",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": [],
        }
    if trade_date not in sessions:
        return {
            "status": "SKIPPED_NON_SESSION",
            "error": None,
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": [],
        }
    end = sessions.index(trade_date) + 1
    window = sessions[max(0, end - EXPECTED_LOOKBACK_SESSIONS):end]
    if len(window) != EXPECTED_LOOKBACK_SESSIONS:
        return {
            "status": "PRECHECK_FAIL",
            "error": "CALENDAR_HISTORY_INSUFFICIENT_FOR_31_SESSIONS",
            "evidence_sha256": digest,
            "calendar_sha256": digest,
            "expected_31_session_dates": window,
        }
    evidence = {"calendar_sha256": digest, "trade_date_cn": trade_date, "expected_sessions": window}
    return {
        "status": "PASS",
        "error": None,
        "evidence_sha256": evidence_hash(evidence),
        "calendar_sha256": digest,
        "expected_31_session_dates": window,
    }


def _last_change_commit(repo_root: Path, relative_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(relative_path)],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and len(value) == 40 else None


def inspect_manifest(repo_root: Path, trade_date: str, main_sha: str, checked_at: str) -> dict[str, Any]:
    relative = MANIFEST_DIR / f"{trade_date}.json"
    path = repo_root / relative
    if not path.is_file():
        return {
            "status": "MISSING",
            "path": str(relative),
            "manifest_sha256": None,
            "manifest_commit_sha": None,
            "error": "EXACT_DATE_MANIFEST_NOT_FOUND",
            "gate": _gate(
                "immutable_manifest_path", "MISSING", checked_at,
                {"path": str(relative), "main_sha": main_sha, "exists": False},
                path=str(relative), manifest_commit_sha=None,
            ),
        }
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError:
        manifest = None
    commit_sha = _last_change_commit(repo_root, relative)
    if not isinstance(manifest, dict):
        status, error = "PRECHECK_FAIL", "MANIFEST_JSON_INVALID"
    elif manifest.get("trade_date_cn") != trade_date:
        status, error = "PRECHECK_FAIL", "MANIFEST_TRADE_DATE_MISMATCH"
    elif commit_sha is None:
        status, error = "UNKNOWN", "MANIFEST_COMMIT_IDENTITY_UNAVAILABLE"
    else:
        status, error = "PASS", None
    gate = _gate(
        "immutable_manifest_path", status, checked_at,
        {"path": str(relative), "manifest_sha256": digest, "manifest_commit_sha": commit_sha},
        path=str(relative), manifest_commit_sha=commit_sha,
    )
    return {
        "status": status,
        "path": str(relative),
        "manifest_sha256": digest,
        "manifest_commit_sha": commit_sha,
        "error": error,
        "gate": gate,
    }


def build_observation(
    *,
    trade_date: str,
    now: datetime,
    main_sha: str,
    repo_root: Path,
    calendar_path: Path,
    write_authorization: str,
    authorized_until: str,
    repository: str,
    workflow_run_id: str,
    workflow_run_url: str,
) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if len(main_sha) != 40:
        raise ValueError("main_sha must be a full 40-character commit SHA")
    local_now = now.astimezone(SHANGHAI)
    recorded_at = local_now.isoformat(timespec="seconds")
    auth = evaluate_authorization(write_authorization, authorized_until, now)
    authorization_gate = _gate(
        "authorization_and_expiry", auth["status"], recorded_at, auth["evidence"],
        authorized_until=auth["authorized_until"],
    )
    manifest = inspect_manifest(repo_root, trade_date, main_sha, recorded_at)
    calendar = inspect_calendar(calendar_path, trade_date)
    calendar_gate = _gate(
        "calendar_31_session_calculation", calendar["status"], recorded_at,
        {"calendar_sha256": calendar["calendar_sha256"],
         "trade_date_cn": trade_date,
         "expected_31_session_dates": calendar["expected_31_session_dates"]},
        calendar_sha256=calendar["calendar_sha256"],
        expected_31_session_dates=calendar["expected_31_session_dates"],
        error=calendar["error"],
    )
    unverified_database_gate = _gate(
        "database_31_session_presence", "NOT_CHECKED", recorded_at,
        {"reason": "PHASE1_NO_READER_ROLE"},
        reason="Phase 1 does not connect to Neon; wait for separately verified PIT_READER_DATABASE_URL.",
    )
    ingest_gate = _gate(
        "same_day_ingest_chain", "NOT_CHECKED", recorded_at,
        {"reason": "AUTHORITATIVE_INGEST_ATTESTATION_NOT_BOUND"},
        reason="Phase 1 does not read workflow artifacts or database state; an authoritative PASS attestation is not yet bound.",
    )

    if calendar["status"] == "SKIPPED_NON_SESSION":
        status = "SKIPPED_NON_SESSION"
        reason = "The frozen exchange calendar marks this date as a non-session."
    elif local_now.time().replace(tzinfo=None) < CUTOFF:
        status = "UNKNOWN"
        reason = "Before the daily 16:10 Asia/Shanghai cutoff; do not record a final daily NON_LIVE status early."
    elif calendar["status"] == "PRECHECK_FAIL":
        status = "PRECHECK_FAIL"
        reason = calendar["error"] or "Frozen exchange calendar validation failed."
    elif calendar["status"] == "BLOCKED_CALENDAR_COVERAGE":
        status = "BLOCKED_CALENDAR_COVERAGE"
        reason = calendar["error"] or "No frozen, SHA-pinned exchange calendar covers this trade date."
    elif auth["status"] != "PASS":
        status = "NON_LIVE"
        reason = "授权门禁待负责人决定"
    elif manifest["status"] != "PASS":
        status = "NON_LIVE"
        reason = "No verified exact-date immutable manifest is available."
    else:
        # This observer cannot report PASS until the database and ingest gates exist.
        status = "UNKNOWN"
        reason = "Phase 1 is observe-only; database lookback presence and authoritative ingest attestation are not checked."

    payload = {
        "schema": "agent-brain-preflight-observation/v1",
        "record_type": "DAILY_PREFLIGHT_STATUS",
        "trade_date_cn": trade_date,
        "recorded_at": recorded_at,
        "timezone": "Asia/Shanghai",
        "status": status,
        "reason": reason,
        "main_sha": main_sha,
        "repository": repository,
        "workflow_run_id": workflow_run_id,
        "workflow_run_url": workflow_run_url,
        "manifest": {k: manifest[k] for k in ("status", "path", "manifest_sha256", "manifest_commit_sha", "error")},
        "gates": {
            "authorization": authorization_gate,
            "immutable_manifest_path": manifest["gate"],
            "calendar_31_session_calculation": calendar_gate,
            "database_31_session_presence": unverified_database_gate,
            "same_day_ingest_chain": ingest_gate,
        },
        "execution_scope": "OBSERVE_ONLY_NO_DATABASE_NO_COLLECTOR_NO_WRITER_DISPATCH",
    }
    return payload


def render_issue_body(payload: dict[str, Any]) -> str:
    return (
        "Automated Phase 1 Agent Brain preflight observation. This is a status record only; it does not authorize or dispatch any writer.\n\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n"
    )


def _api_json(url: str, token: str, method: str = "GET", data: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
    raw = json.dumps(data).encode("utf-8") if data is not None else None
    request = Request(
        url,
        data=raw,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "agent-brain-preflight-observer",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body else None), dict(response.headers.items())
    except HTTPError as exc:
        # Do not include request headers or token in error output.
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"GitHub API {method} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API {method} connection failed: {exc.reason}") from exc


def publish_status_issue(payload: dict[str, Any], *, token: str, repository: str, api_url: str) -> dict[str, Any]:
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to publish the status issue")
    base = api_url.rstrip("/") + f"/repos/{repository}"
    title = f"Agent Brain preflight status - {payload['trade_date_cn']}"
    body = render_issue_body(payload)
    marker = f"workflow_run_id={payload['workflow_run_id']}"
    page = 1
    existing = None
    while page <= 10:
        query = urlencode({"state": "all", "per_page": 100, "page": page})
        issues, _ = _api_json(f"{base}/issues?{query}", token)
        if not isinstance(issues, list):
            raise RuntimeError("GitHub issue list response was not an array")
        existing = next((item for item in issues if item.get("title") == title and "pull_request" not in item), None)
        if existing or len(issues) < 100:
            break
        page += 1
    if existing:
        comments, _ = _api_json(f"{base}/issues/{existing['number']}/comments?per_page=100", token)
        if any(marker in str(item.get("body", "")) for item in comments if isinstance(item, dict)):
            return {"action": "NOOP_DUPLICATE_RUN", "issue_number": existing["number"], "title": title}
        comment = body + f"\n<!-- {marker} -->\n"
        result, _ = _api_json(f"{base}/issues/{existing['number']}/comments", token, "POST", {"body": comment})
        return {
            "action": "APPENDED_RUN_COMMENT",
            "issue_number": existing["number"],
            "comment_id": result["id"],
            "title": title,
        }
    body += f"\n<!-- {marker} -->\n"
    result, _ = _api_json(f"{base}/issues", token, "POST", {"title": title, "body": body})
    return {"action": "CREATED_DAILY_ISSUE", "issue_number": result["number"], "title": title}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-date", help="Override trade date for local tests; defaults to today in Asia/Shanghai")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    trade_date = args.trade_date or now.astimezone(SHANGHAI).date().isoformat()
    root = Path.cwd()
    calendar_path = root / "evidence/agent_brain/cn_exchange_calendar_2026.json"
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repository}/actions/runs/{run_id}"
    payload = build_observation(
        trade_date=trade_date,
        now=now,
        main_sha=os.environ.get("GITHUB_SHA", ""),
        repo_root=root,
        calendar_path=calendar_path,
        write_authorization=os.environ.get("PIT_WRITE_AUTHORIZATION", ""),
        authorized_until=os.environ.get("PIT_WRITE_AUTHORIZED_UNTIL", ""),
        repository=repository,
        workflow_run_id=run_id,
        workflow_run_url=run_url,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as stream:
            stream.write("## Agent Brain preflight observation\n\n```json\n" + rendered + "\n```\n")
    result = publish_status_issue(
        payload,
        token=os.environ.get("GITHUB_TOKEN", ""),
        repository=repository,
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    print(json.dumps({"issue_publication": result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
