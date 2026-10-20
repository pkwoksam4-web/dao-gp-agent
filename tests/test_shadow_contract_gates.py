from __future__ import annotations

import json
import ast
import inspect
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import scripts.shadow_contract_gates as gates
from scripts.shadow_contract_gates import (
    CORE13, ContractGateError, build_shadow_request, load_quarantine_registry,
    maturity_targets, source_is_live_pit, validate_event_order,
    validate_prev_close_continuity,
)


def rows(prev=10.0):
    return [{"symbol":s,"quote":{"normalized":{"prev_close":prev}}} for s in CORE13]


class ContractGateTests(unittest.TestCase):
    def test_missing_previous_session_fails_closed(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13[1:]}
        with self.assertRaisesRegex(ContractGateError,"MISSING_PREVIOUS_SESSION"):
            validate_prev_close_continuity(
                rows(),latest,expected_previous_trade_date="2026-10-09"
            )

    def test_prev_close_mismatch_fails_closed(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        bad=rows(); bad[4]["quote"]["normalized"]["prev_close"]=9.0
        with self.assertRaisesRegex(ContractGateError,"PREV_CLOSE_MISMATCH"):
            validate_prev_close_continuity(
                bad,latest,expected_previous_trade_date="2026-10-09"
            )

    def test_prev_close_sub_nanounit_mismatch_fails_closed(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        bad=rows(); bad[4]["quote"]["normalized"]["prev_close"]=10.0000000005
        with self.assertRaisesRegex(ContractGateError,"PREV_CLOSE_MISMATCH"):
            validate_prev_close_continuity(
                bad,latest,expected_previous_trade_date="2026-10-09"
            )

    def test_prev_close_13_of_13_passes(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        self.assertEqual(
            validate_prev_close_continuity(
                rows(),latest,expected_previous_trade_date="2026-10-09"
            )["matched"],
            13,
        )

    def test_prev_close_must_come_from_expected_exchange_predecessor(self):
        self.assertIn(
            "expected_previous_trade_date",
            inspect.signature(validate_prev_close_continuity).parameters,
            "previous-session validation must bind the exchange-calendar key",
        )
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        with self.assertRaisesRegex(ContractGateError,"UNEXPECTED_PREVIOUS_SESSION"):
            validate_prev_close_continuity(
                rows(),latest,expected_previous_trade_date="2026-10-08"
            )

    def test_feature_window_fails_closed_on_missing_interior_exchange_session(self):
        self.assertTrue(
            hasattr(gates,"feature_window_dates"),
            "calendar-keyed feature window resolver is required",
        )
        self.assertTrue(
            hasattr(gates,"validate_feature_window_continuity"),
            "calendar-keyed feature window validator is required",
        )
        dates=gates.load_exchange_trading_calendar(
            "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        self.assertEqual(len(expected),31)
        self.assertEqual(expected[-1],"2026-10-09")
        self.assertEqual(expected[-2],"2026-10-08")
        observed=[d for d in expected if d!=expected[-6]]
        self.assertEqual(observed[-1],expected[-1])
        self.assertEqual(observed[-2],expected[-2])
        with self.assertRaisesRegex(ContractGateError,"MISSING_EXCHANGE_SESSIONS"):
            gates.validate_feature_window_continuity("000636.SZ",expected,observed)

    def test_2026_10_10_weekend_makeup_is_not_an_exchange_session(self):
        dates=gates.load_exchange_trading_calendar(
            "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        self.assertNotIn("2026-10-10",dates)
        self.assertNotIn("2026-10-11",dates)
        self.assertIn("2026-10-12",dates)

    def test_31_session_window_counts_across_national_day_closure(self):
        dates=gates.load_exchange_trading_calendar(
            "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        self.assertEqual(len(expected),31)
        self.assertEqual(expected[0],"2026-08-20")
        self.assertEqual(
            expected[-5:],
            ["2026-09-28","2026-09-29","2026-09-30","2026-10-08","2026-10-09"],
        )
        self.assertTrue(
            {"2026-10-01","2026-10-02","2026-10-03","2026-10-04",
             "2026-10-05","2026-10-06","2026-10-07"}.isdisjoint(expected)
        )

    def test_missing_2026_09_29_feature_bar_fails_closed(self):
        dates=gates.load_exchange_trading_calendar(
            "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        self.assertIn("2026-09-29",expected)
        observed=[d for d in expected if d!="2026-09-29"]
        with self.assertRaisesRegex(ContractGateError,"MISSING_EXCHANGE_SESSIONS"):
            gates.validate_feature_window_continuity("000636.SZ",expected,observed)

    def test_feature_window_fails_closed_on_missing_immediate_predecessor(self):
        dates=gates.load_exchange_trading_calendar(
            "evidence/agent_brain/cn_exchange_calendar_2026.json"
        )
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        observed=expected[:-2]+[expected[-1]]
        with self.assertRaisesRegex(ContractGateError,"MISSING_EXCHANGE_SESSIONS"):
            gates.validate_feature_window_continuity("000636.SZ",expected,observed)

    def test_live_ingest_checks_full_calendar_window_before_any_write(self):
        src=Path("scripts/live_pit_ingest.py").read_text(encoding="utf-8")
        tree=ast.parse(src)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        validation_lines=[
            n.lineno for n in ast.walk(main)
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
            and n.func.id=="validate_feature_window_continuity"
        ]
        write_lines=[
            n.lineno for n in ast.walk(main)
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
            and n.func.id=="insert_source"
        ]
        self.assertTrue(validation_lines,"pre-write calendar feature-window gate is required")
        self.assertTrue(write_lines,"expected source write path was not found")
        self.assertLess(min(validation_lines),min(write_lines))

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
        with self.assertRaisesRegex(ContractGateError,"BEFORE_1730"):
            build_shadow_request(m,"abc",datetime(2026,10,12,9,0,tzinfo=timezone.utc))
        a=build_shadow_request(m,"abc",datetime(2026,10,12,9,31,tzinfo=timezone.utc))
        b=build_shadow_request(m,"abc",datetime(2026,10,12,10,0,tzinfo=timezone.utc))
        self.assertEqual(a["trigger"]["idempotency_key"],b["trigger"]["idempotency_key"])
        self.assertFalse(a["probability_forecast_allowed"])


if __name__=="__main__":
    unittest.main()
