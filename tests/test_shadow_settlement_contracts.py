from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import scripts.shadow_contract_gates as gates
import scripts.ranking_shadow_settlement as settlement
from scripts.shadow_contract_gates import (
    ContractGateError, build_shadow_request, load_quarantine_registry,
    maturity_targets, source_is_live_pit, validate_event_order,
)


class ShadowSettlementContractTests(unittest.TestCase):
    def test_historical_recovery_is_never_eligible(self):
        self.assertFalse(source_is_live_pit({"mode":"HISTORICAL_RECOVERY_NON_LIVE","live_shadow_eligible":False}))
        self.assertTrue(source_is_live_pit({"mode":"LIVE_PIT","live_shadow_eligible":True}))

    def test_quarantine_registry_excludes_20260930(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"q.json"
            p.write_text(json.dumps({"schema":"agent-brain-prospective-quarantine-registry/v1",
                                     "quarantined_strategy_ids":["SSR-CORE10-STABLE4-20260930"]}))
            self.assertIn("SSR-CORE10-STABLE4-20260930",load_quarantine_registry(p))

    def test_5d_and_20d_boundaries_are_independent(self):
        d=[f"2026-10-{i:02d}" for i in range(1,21)]
        self.assertEqual(maturity_targets(d[:4]),{"eligible_future_sessions":4,"5d":None,"20d":None})
        self.assertEqual(maturity_targets(d[:5])["5d"],"2026-10-05")
        self.assertIsNone(maturity_targets(d[:19])["20d"])
        self.assertEqual(maturity_targets(d)["20d"],"2026-10-20")

    def test_exchange_calendar_target_does_not_shift_when_live_pit_is_missing(self):
        self.assertTrue(
            hasattr(gates, "maturity_targets_from_exchange_calendar"),
            "exchange-calendar maturity resolver is required",
        )
        exchange_calendar=[
            "2026-09-28","2026-09-29","2026-09-30","2026-10-08","2026-10-09",
            "2026-10-12","2026-10-13","2026-10-14","2026-10-15","2026-10-16",
        ]
        targets=gates.maturity_targets_from_exchange_calendar("2026-09-28",exchange_calendar)
        self.assertEqual(targets["5d"],"2026-10-12")
        available_live_pit={"2026-09-29","2026-09-30","2026-10-08","2026-10-09","2026-10-13"}
        self.assertNotIn(targets["5d"],available_live_pit)

    def test_frozen_2026_exchange_calendar_file_and_known_targets(self):
        dates=gates.load_exchange_trading_calendar("evidence/agent_brain/cn_exchange_calendar_2026.json")
        self.assertEqual(len(dates),242)
        self.assertEqual(gates.maturity_targets_from_exchange_calendar("2026-09-28",dates)["5d"],"2026-10-12")
        self.assertEqual(gates.maturity_targets_from_exchange_calendar("2026-10-08",dates)["5d"],"2026-10-15")
        self.assertEqual(gates.maturity_targets_from_exchange_calendar("2026-10-09",dates)["5d"],"2026-10-16")

    def test_future_target_is_not_due_before_exchange_date(self):
        self.assertTrue(hasattr(gates,"target_is_due"),"target due-date gate is required")
        self.assertFalse(gates.target_is_due("2026-10-15","2026-10-14"))
        self.assertTrue(gates.target_is_due("2026-10-15","2026-10-15"))
        self.assertTrue(gates.target_is_due("2026-10-15","2026-10-16"))

    def test_settlement_runtime_uses_exchange_calendar_not_available_rows(self):
        src=Path("scripts/ranking_shadow_settlement.py").read_text(encoding="utf-8")
        self.assertIn("maturity_targets_from_exchange_calendar",src)
        self.assertNotIn("maturity_targets(eligible_dates(cur",src)

    def test_missing_exact_target_is_reported_as_data_gap_not_shifted(self):
        src=Path("scripts/ranking_shadow_settlement.py").read_text(encoding="utf-8")
        self.assertIn("BLOCKED_DATA_GAP",src)
        self.assertIn("missing_target_symbols",src)

    def test_settlement_order_guard(self):
        with self.assertRaisesRegex(ContractGateError,"OUT_OF_ORDER"):
            validate_event_order(["LIVE_PIT_INGEST_PASS","SETTLEMENT_START",
                                  "SHADOW_RANKING_OBSERVATION_PASS","RANKING_ATTESTATION_PASS"])
        self.assertTrue(validate_event_order(["LIVE_PIT_INGEST_PASS",
                                             "SHADOW_RANKING_OBSERVATION_PASS",
                                             "RANKING_ATTESTATION_PASS","SETTLEMENT_START"]))

    def test_shadow_request_idempotency_key_and_time_gate(self):
        m={"trade_date_cn":"2026-10-12","universe_id":"WAT-core13-observation-v1"}
        good={"status":"PASS","manifest_sha256":"abc","ingest_report_sha256":"a"*64,
              "verified_rows":{"bars":13,"features":13}}
        with self.assertRaisesRegex(ContractGateError,"BEFORE_1730"):
            build_shadow_request(m,"abc",datetime(2026,10,12,9,0,tzinfo=timezone.utc),good)
        a=build_shadow_request(m,"abc",datetime(2026,10,12,9,31,tzinfo=timezone.utc),good)
        b=build_shadow_request(m,"abc",datetime(2026,10,12,10,0,tzinfo=timezone.utc),good)
        self.assertEqual(a["trigger"]["ingest_evidence_sha256"],"a"*64)
        with self.assertRaisesRegex(ContractGateError,"INGEST_EVIDENCE_NOT_PASS"):
            build_shadow_request(m,"abc",datetime(2026,10,12,9,31,tzinfo=timezone.utc),{"status":"BLOCKED"})
        bad={**good,"manifest_sha256":"wrong"}
        with self.assertRaisesRegex(ContractGateError,"MANIFEST_HASH_MISMATCH"):
            build_shadow_request(m,"abc",datetime(2026,10,12,9,31,tzinfo=timezone.utc),bad)
        self.assertEqual(a["trigger"]["idempotency_key"],b["trigger"]["idempotency_key"])
        self.assertFalse(a["probability_forecast_allowed"])


    def test_settlement_events_are_stable_for_retries_and_append_when_result_changes(self):
        builder = getattr(settlement, "build_settlement_event", None)
        self.assertTrue(callable(builder), "append-only settlement event builder is required")
        blocked = {"status": "BLOCKED_DATA_GAP", "missing_target_symbols": [
            {"symbol": "000636.SZ", "reason": "MISSING_TARGET_BAR"}
        ]}
        first = builder("SSR-CORE10-20261012", 5, "2026-10-19", blocked,
                        "2026-10-20T01:00:00+00:00")
        retry = builder("SSR-CORE10-20261012", 5, "2026-10-19", blocked,
                        "2026-10-20T02:00:00+00:00")
        settled = builder("SSR-CORE10-20261012", 5, "2026-10-19",
                          {"status": "SETTLED", "outcomes": [{"symbol": "000636.SZ", "actual_return_5d": 0.1}]},
                          "2026-10-20T03:00:00+00:00")
        self.assertEqual(first["event_id"], retry["event_id"])
        self.assertNotEqual(first["event_id"], settled["event_id"])
        self.assertEqual(first["evaluated_at"], "2026-10-20T01:00:00+00:00")

    def test_20d_can_settle_before_5d_retry_and_latest_event_is_current(self):
        latest = getattr(settlement, "latest_settlement_events", None)
        self.assertTrue(callable(latest), "latest event per horizon resolver is required")
        t1 = datetime(2026, 10, 20, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 2, 10, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 3, 10, tzinfo=timezone.utc)
        rows = [
            {"event_id":"5-gap", "horizon_sessions":5, "status":"BLOCKED_DATA_GAP",
             "created_at":t1, "event_json":{"result":{"status":"BLOCKED_DATA_GAP"}}},
            {"event_id":"20-settled", "horizon_sessions":20, "status":"SETTLED",
             "created_at":t2, "event_json":{"result":{"status":"SETTLED"}}},
            {"event_id":"5-retried", "horizon_sessions":5, "status":"SETTLED",
             "created_at":t3, "event_json":{"result":{"status":"SETTLED"}}},
        ]
        current = latest(rows)
        self.assertEqual(current[5]["event_id"], "5-retried")
        self.assertEqual(current[5]["status"], "SETTLED")
        self.assertEqual(current[20]["event_id"], "20-settled")
        self.assertEqual(set(current), {5, 20})

    def test_duplicate_evidence_insert_is_idempotent(self):
        class EventCursor:
            def __init__(self):
                self.ids = set()
                self.rowcount = 0
                self.sql = ""

            def execute(self, sql, params):
                self.sql = sql
                event_id = params[0]
                self.rowcount = int(event_id not in self.ids)
                self.ids.add(event_id)

        event = settlement.build_settlement_event(
            "SSR-CORE10-20261012", 20, "2026-11-09",
            {"status":"SETTLED", "outcomes":[{"symbol":"000636.SZ","actual_return_20d":0.1}]},
            "2026-11-09T10:00:00+00:00",
        )
        cur = EventCursor()
        self.assertTrue(settlement.persist_settlement_event(cur, event))
        self.assertFalse(settlement.persist_settlement_event(cur, event))
        self.assertEqual(cur.ids, {event["event_id"]})
        self.assertIn("ON CONFLICT (event_id) DO NOTHING", cur.sql)

    def test_migration_fails_before_table_creation_if_dedicated_role_is_missing(self):
        migration = Path("db/migrations/20261026_agent_brain_settlement_events.sql").read_text(encoding="utf-8")
        table_creation = migration.index("CREATE TABLE IF NOT EXISTS")
        for role in ("pit_writer", "pit_reader"):
            guard = (
                f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN\n"
                f"        RAISE EXCEPTION 'required role {role} must exist';"
            )
            self.assertIn(guard, migration)
            self.assertLess(migration.index(guard), table_creation)
        self.assertNotIn("IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pit_writer')", migration)
        self.assertNotIn("IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pit_reader')", migration)

    def test_migration_is_owner_run_and_not_applied_by_ci(self):
        migration = Path("db/migrations/20261026_agent_brain_settlement_events.sql").read_text(encoding="utf-8")
        workflow = Path(".github/workflows/shadow-settlement-contracts-ci.yml").read_text(encoding="utf-8")
        self.assertIn("Run manually by the database owner", migration)
        self.assertNotIn("NEON_DATABASE_URL", workflow)
        self.assertNotIn("psql", workflow.lower())


if __name__=="__main__":
    unittest.main()
