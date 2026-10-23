import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.agent_brain_preflight_observer import (
    build_observation,
    evaluate_authorization,
    inspect_calendar,
)


class AgentBrainPreflightObserverTests(unittest.TestCase):
    def test_authorization_requires_approval_and_future_expiry(self):
        now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
        self.assertEqual(evaluate_authorization("NOT_AUTHORIZED", "", now)["status"], "FAIL_NOT_AUTHORIZED")
        self.assertEqual(evaluate_authorization("APPROVED", "", now)["status"], "FAIL_EXPIRY_MISSING")
        self.assertEqual(
            evaluate_authorization("APPROVED", "2026-10-23T08:14:59Z", now)["status"],
            "FAIL_EXPIRED",
        )
        self.assertEqual(
            evaluate_authorization("APPROVED", "2026-10-24T08:15:00Z", now)["status"],
            "PASS",
        )

    def test_calendar_calculates_exact_31_expected_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calendar.json"
            dates = [f"2026-09-{day:02d}" for day in range(1, 31)] + ["2026-10-01"]
            path.write_text(json.dumps({
                "schema": "agent-brain-cn-exchange-calendar/v1",
                "year": 2026,
                "trading_days": dates,
            }), encoding="utf-8")
            result = inspect_calendar(path, "2026-10-01")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(len(result["expected_31_session_dates"]), 31)
            self.assertEqual(result["expected_31_session_dates"][-1], "2026-10-01")
            self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_observer_stays_non_live_when_authorization_is_pending(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calendar = root / "calendar.json"
            calendar.write_text(json.dumps({
                "schema": "agent-brain-cn-exchange-calendar/v1",
                "year": 2026,
                "trading_days": [(date(2026, 9, 23) + timedelta(days=offset)).isoformat()
                                 for offset in range(31)],
            }), encoding="utf-8")
            now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
            result = build_observation(
                trade_date="2026-10-23",
                now=now,
                main_sha="a" * 40,
                repo_root=root,
                calendar_path=calendar,
                write_authorization="NOT_AUTHORIZED",
                authorized_until="",
                repository="owner/repo",
                workflow_run_id="123",
                workflow_run_url="https://github.com/owner/repo/actions/runs/123",
            )
            self.assertEqual(result["status"], "NON_LIVE")
            self.assertIn("授权门禁", result["reason"])
            self.assertEqual(result["gates"]["database_31_session_presence"]["status"], "NOT_CHECKED")
            self.assertEqual(result["gates"]["same_day_ingest_chain"]["status"], "NOT_CHECKED")
            self.assertEqual(result["manifest"]["status"], "MISSING")
            self.assertNotIn("PIT_WRITER_DATABASE_URL", json.dumps(result))

    def test_non_session_is_not_reported_as_non_live(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calendar.json"
            path.write_text(json.dumps({
                "schema": "agent-brain-cn-exchange-calendar/v1",
                "year": 2026,
                "trading_days": ["2026-10-22", "2026-10-23"],
            }), encoding="utf-8")
            result = inspect_calendar(path, "2026-10-24")
            self.assertEqual(result["status"], "SKIPPED_NON_SESSION")

    def test_before_cutoff_does_not_emit_final_daily_non_live(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calendar = root / "calendar.json"
            calendar.write_text(json.dumps({
                "schema": "agent-brain-cn-exchange-calendar/v1",
                "year": 2026,
                "trading_days": ["2026-10-23"],
            }), encoding="utf-8")
            now = datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc)  # 15:00 Shanghai
            result = build_observation(
                trade_date="2026-10-23",
                now=now,
                main_sha="b" * 40,
                repo_root=root,
                calendar_path=calendar,
                write_authorization="NOT_AUTHORIZED",
                authorized_until="",
                repository="owner/repo",
                workflow_run_id="456",
                workflow_run_url="https://github.com/owner/repo/actions/runs/456",
            )
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertIn("cutoff", result["reason"].lower())

    def test_verified_manifest_still_cannot_make_phase1_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calendar = root / "calendar.json"
            sessions = [(date(2026, 9, 23) + timedelta(days=offset)).isoformat()
                        for offset in range(31)]
            calendar.write_text(json.dumps({
                "schema": "agent-brain-cn-exchange-calendar/v1",
                "year": 2026,
                "trading_days": sessions,
            }), encoding="utf-8")
            manifest_path = root / "runtime/pit_manifests/2026-10-23.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps({"trade_date_cn": "2026-10-23"}), encoding="utf-8")
            now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
            with patch("scripts.agent_brain_preflight_observer._last_change_commit", return_value="c" * 40):
                result = build_observation(
                    trade_date="2026-10-23",
                    now=now,
                    main_sha="b" * 40,
                    repo_root=root,
                    calendar_path=calendar,
                    write_authorization="APPROVED",
                    authorized_until="2026-10-24T08:15:00Z",
                    repository="owner/repo",
                    workflow_run_id="789",
                    workflow_run_url="https://github.com/owner/repo/actions/runs/789",
                )
            self.assertEqual(result["manifest"]["status"], "PASS")
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(result["gates"]["database_31_session_presence"]["status"], "NOT_CHECKED")


if __name__ == "__main__":
    unittest.main()
