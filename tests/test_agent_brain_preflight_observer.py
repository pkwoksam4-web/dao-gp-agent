import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import scripts.agent_brain_preflight_observer as observer
from scripts.agent_brain_preflight_observer import (
    build_observation,
    evaluate_authorization,
    inspect_calendar,
    publish_status_issue,
)


class AgentBrainPreflightObserverTests(unittest.TestCase):
    def _write_calendar(self, path: Path, sessions: list[str]) -> tuple[Path, str]:
        path.write_text(json.dumps({
            "schema": "agent-brain-cn-exchange-calendar/v1",
            "year": 2026,
            "trading_days": sessions,
        }), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path, digest

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
            path, digest = self._write_calendar(path, dates)
            with patch.dict(observer.FROZEN_CALENDAR_SHA256, {2026: digest}):
                result = inspect_calendar(path, "2026-10-01")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(len(result["expected_31_session_dates"]), 31)
            self.assertEqual(result["expected_31_session_dates"][-1], "2026-10-01")
            self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_authorization_off_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sessions = [(date(2026, 9, 23) + timedelta(days=offset)).isoformat()
                        for offset in range(31)]
            calendar, digest = self._write_calendar(root / "calendar.json", sessions)
            now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
            with patch.dict(observer.FROZEN_CALENDAR_SHA256, {2026: digest}):
                result = build_observation(
                    trade_date="2026-10-23",
                    now=now,
                    main_sha="a" * 40,
                    repo_root=root,
                    calendar_path=calendar,
                    write_authorization="NOT_AUTHORIZED",
                    authorized_until="",
                    repository="owner/repo",
                    workflow_run_id="auth-off",
                    workflow_run_url="https://github.com/owner/repo/actions/runs/auth-off",
                )
            self.assertEqual(result["status"], "NON_LIVE")
            self.assertEqual(result["gates"]["authorization"]["status"], "FAIL_NOT_AUTHORIZED")
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(result["gates"]["database_31_session_presence"]["status"], "NOT_CHECKED")
            self.assertEqual(result["gates"]["same_day_ingest_chain"]["status"], "NOT_CHECKED")

    def test_missing_manifest_fails_closed_with_authorization_approved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sessions = [(date(2026, 9, 23) + timedelta(days=offset)).isoformat()
                        for offset in range(31)]
            calendar, digest = self._write_calendar(root / "calendar.json", sessions)
            now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
            with patch.dict(observer.FROZEN_CALENDAR_SHA256, {2026: digest}):
                result = build_observation(
                    trade_date="2026-10-23",
                    now=now,
                    main_sha="b" * 40,
                    repo_root=root,
                    calendar_path=calendar,
                    write_authorization="APPROVED",
                    authorized_until="2026-10-24T08:15:00Z",
                    repository="owner/repo",
                    workflow_run_id="manifest-missing",
                    workflow_run_url="https://github.com/owner/repo/actions/runs/manifest-missing",
                )
            self.assertEqual(result["status"], "NON_LIVE")
            self.assertEqual(result["manifest"]["status"], "MISSING")
            self.assertEqual(result["gates"]["immutable_manifest_path"]["status"], "MISSING")
            self.assertNotEqual(result["status"], "PASS")

    def test_weekend_is_not_reported_as_non_live(self):
        with tempfile.TemporaryDirectory() as td:
            path, digest = self._write_calendar(
                Path(td) / "calendar.json", ["2026-10-22", "2026-10-23"]
            )
            with patch.dict(observer.FROZEN_CALENDAR_SHA256, {2026: digest}):
                result = inspect_calendar(path, "2026-10-24")
            self.assertEqual(result["status"], "SKIPPED_NON_SESSION")

    def test_frozen_calendar_holidays_weekends_and_makeup_saturday_are_skipped(self):
        calendar = (
            Path(__file__).resolve().parents[1]
            / "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        calendar_data = json.loads(calendar.read_text(encoding="utf-8"))
        self.assertTrue(
            all(date.fromisoformat(session).weekday() < 5
                for session in calendar_data["trading_days"])
        )
        closed_dates = [
            "2026-09-25",
            *[f"2026-10-{day:02d}" for day in range(1, 8)],
            "2026-10-10",
            "2026-10-24",
        ]
        for trade_date in closed_dates:
            with self.subTest(trade_date=trade_date):
                result = inspect_calendar(calendar, trade_date)
                self.assertEqual(result["status"], "SKIPPED_NON_SESSION")
                self.assertNotEqual(result["status"], "NON_LIVE")

    def test_calendar_coverage_gap_is_blocked_before_other_failed_gates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calendar = (
                Path(__file__).resolve().parents[1]
                / "evidence/agent_brain/cn_exchange_calendar_2026.json"
            )
            now = datetime(2027, 1, 4, 8, 15, tzinfo=timezone.utc)
            result = build_observation(
                trade_date="2027-01-04",
                now=now,
                main_sha="f" * 40,
                repo_root=root,
                calendar_path=calendar,
                write_authorization="NOT_AUTHORIZED",
                authorized_until="",
                repository="owner/repo",
                workflow_run_id="calendar-coverage",
                workflow_run_url="https://github.com/owner/repo/actions/runs/calendar-coverage",
            )
        self.assertEqual(
            result["gates"]["calendar_31_session_calculation"]["status"],
            "BLOCKED_CALENDAR_COVERAGE",
        )
        self.assertEqual(result["status"], "BLOCKED_CALENDAR_COVERAGE")
        self.assertNotEqual(result["status"], "PASS")

    def test_trading_day_failure_is_not_hidden_as_non_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calendar = (
                Path(__file__).resolve().parents[1]
                / "evidence/agent_brain/cn_exchange_calendar_2026.json"
            )
            now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
            result = build_observation(
                trade_date="2026-10-23",
                now=now,
                main_sha="a" * 40,
                repo_root=root,
                calendar_path=calendar,
                write_authorization="APPROVED",
                authorized_until="2026-10-24T08:15:00Z",
                repository="owner/repo",
                workflow_run_id="trading-day-missing-manifest",
                workflow_run_url="https://github.com/owner/repo/actions/runs/trading-day-missing-manifest",
            )
        self.assertEqual(
            result["gates"]["calendar_31_session_calculation"]["status"],
            "PASS",
        )
        self.assertEqual(result["manifest"]["status"], "MISSING")
        self.assertEqual(result["status"], "NON_LIVE")
        self.assertNotEqual(result["status"], "SKIPPED_NON_SESSION")

    def test_missing_session_in_frozen_window_fails_calendar_hash_check(self):
        frozen_calendar = (
            Path(__file__).resolve().parents[1]
            / "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        calendar_data = json.loads(frozen_calendar.read_text(encoding="utf-8"))
        self.assertIn("2026-10-08", calendar_data["trading_days"])
        calendar_data["trading_days"].remove("2026-10-08")
        with tempfile.TemporaryDirectory() as td:
            changed_calendar = Path(td) / "calendar.json"
            changed_calendar.write_text(
                json.dumps(calendar_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = inspect_calendar(changed_calendar, "2026-10-23")
        self.assertEqual(result["status"], "PRECHECK_FAIL")
        self.assertEqual(result["error"], "FROZEN_CALENDAR_SHA256_MISMATCH")
        self.assertNotEqual(result["status"], "PASS")

    def test_before_cutoff_does_not_emit_final_daily_non_live(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calendar, digest = self._write_calendar(
                root / "calendar.json", ["2026-10-23"]
            )
            now = datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc)  # 15:00 Shanghai
            with patch.dict(observer.FROZEN_CALENDAR_SHA256, {2026: digest}):
                result = build_observation(
                    trade_date="2026-10-23",
                    now=now,
                    main_sha="c" * 40,
                    repo_root=root,
                    calendar_path=calendar,
                    write_authorization="NOT_AUTHORIZED",
                    authorized_until="",
                    repository="owner/repo",
                    workflow_run_id="before-cutoff",
                    workflow_run_url="https://github.com/owner/repo/actions/runs/before-cutoff",
                )
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertIn("cutoff", result["reason"].lower())

    def test_verified_manifest_still_cannot_make_phase1_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sessions = [(date(2026, 9, 23) + timedelta(days=offset)).isoformat()
                        for offset in range(31)]
            calendar, digest = self._write_calendar(root / "calendar.json", sessions)
            manifest_path = root / "runtime/pit_manifests/2026-10-23.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps({"trade_date_cn": "2026-10-23"}), encoding="utf-8")
            now = datetime(2026, 10, 23, 8, 15, tzinfo=timezone.utc)
            with patch.dict(observer.FROZEN_CALENDAR_SHA256, {2026: digest}):
                with patch("scripts.agent_brain_preflight_observer._last_change_commit", return_value="d" * 40):
                    result = build_observation(
                        trade_date="2026-10-23",
                        now=now,
                        main_sha="e" * 40,
                        repo_root=root,
                        calendar_path=calendar,
                        write_authorization="APPROVED",
                        authorized_until="2026-10-24T08:15:00Z",
                        repository="owner/repo",
                        workflow_run_id="phase1-no-pass",
                        workflow_run_url="https://github.com/owner/repo/actions/runs/phase1-no-pass",
                    )
            self.assertEqual(result["manifest"]["status"], "PASS")
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(result["gates"]["database_31_session_presence"]["status"], "NOT_CHECKED")
            self.assertEqual(result["gates"]["same_day_ingest_chain"]["status"], "NOT_CHECKED")

    def test_same_run_rerun_is_idempotent_for_trade_date(self):
        payload = {"trade_date_cn": "2026-10-23", "workflow_run_id": "run-123"}
        existing = [{"number": 77, "title": "Agent Brain preflight status - 2026-10-23"}]
        comments = [{"body": "<!-- workflow_run_id=run-123 -->"}]
        with patch("scripts.agent_brain_preflight_observer._api_json",
                   side_effect=[(existing, {}), (comments, {})]) as api:
            result = publish_status_issue(
                payload,
                token="test-token",
                repository="owner/repo",
                api_url="https://api.github.com",
            )
        self.assertEqual(result["action"], "NOOP_DUPLICATE_RUN")
        self.assertEqual(result["issue_number"], 77)
        self.assertEqual(api.call_count, 2)
        self.assertFalse(any(
            len(call.args) >= 3 and call.args[2] == "POST"
            for call in api.call_args_list
        ))

    def test_new_run_appends_to_same_daily_issue_without_creating_another(self):
        payload = {"trade_date_cn": "2026-10-23", "workflow_run_id": "run-456"}
        existing = [{"number": 77, "title": "Agent Brain preflight status - 2026-10-23"}]
        comments = [{"body": "<!-- workflow_run_id=run-123 -->"}]
        with patch("scripts.agent_brain_preflight_observer._api_json",
                   side_effect=[(existing, {}), (comments, {}), ({"id": 900}, {})]) as api:
            result = publish_status_issue(
                payload,
                token="test-token",
                repository="owner/repo",
                api_url="https://api.github.com",
            )
        self.assertEqual(result["action"], "APPENDED_RUN_COMMENT")
        self.assertEqual(result["issue_number"], 77)
        self.assertEqual(result["comment_id"], 900)
        self.assertTrue(api.call_args_list[-1].args[0].endswith("/issues/77/comments"))
        self.assertNotEqual(api.call_args_list[-1].args[0], "https://api.github.com/repos/owner/repo/issues")


if __name__ == "__main__":
    unittest.main()
