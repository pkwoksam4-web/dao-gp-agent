from __future__ import annotations

import ast
import inspect
import unittest
from datetime import datetime, timezone
from pathlib import Path

import scripts.pit_calendar_gate as gates
from scripts.pit_calendar_gate import (
    CORE13, ContractGateError, historical_bar_available_by_cutoff,
    validate_prev_close_continuity,
)


def rows(prev=10.0):
    return [{"symbol":s,"quote":{"normalized":{"prev_close":prev}}} for s in CORE13]


class CalendarGateTests(unittest.TestCase):
    def test_missing_previous_session_fails_closed(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-08"} for s in CORE13[1:]}
        with self.assertRaisesRegex(ContractGateError,"MISSING_PREVIOUS_SESSION"):
            validate_prev_close_continuity(rows(),latest,expected_previous_trade_date="2026-10-08")

    def test_prev_close_mismatch_fails_closed(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-08"} for s in CORE13}
        bad=rows(); bad[4]["quote"]["normalized"]["prev_close"]=9.0
        with self.assertRaisesRegex(ContractGateError,"PREV_CLOSE_MISMATCH"):
            validate_prev_close_continuity(bad,latest,expected_previous_trade_date="2026-10-08")

    def test_prev_close_requires_expected_exchange_predecessor(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        with self.assertRaisesRegex(ContractGateError,"UNEXPECTED_PREVIOUS_SESSION"):
            validate_prev_close_continuity(rows(),latest,expected_previous_trade_date="2026-10-08")

    def test_2026_10_10_weekend_makeup_is_not_an_exchange_session(self):
        dates=gates.load_exchange_trading_calendar("evidence/agent_brain/cn_exchange_calendar_2026.json")
        self.assertNotIn("2026-10-10",dates)
        self.assertIn("2026-10-12",dates)

    def test_31_session_window_counts_across_national_day_closure(self):
        dates=gates.load_exchange_trading_calendar("evidence/agent_brain/cn_exchange_calendar_2026.json")
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        self.assertEqual(len(expected),31)
        self.assertEqual(expected[0],"2026-08-20")
        self.assertEqual(expected[-5:],["2026-09-28","2026-09-29","2026-09-30","2026-10-08","2026-10-09"])
        self.assertTrue({"2026-10-01","2026-10-02","2026-10-03","2026-10-04","2026-10-05","2026-10-06","2026-10-07"}.isdisjoint(expected))

    def test_missing_2026_09_29_bar_fails_closed(self):
        dates=gates.load_exchange_trading_calendar("evidence/agent_brain/cn_exchange_calendar_2026.json")
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        observed=[d for d in expected if d!="2026-09-29"]
        with self.assertRaisesRegex(ContractGateError,"MISSING_EXCHANGE_SESSIONS"):
            gates.validate_feature_window_continuity("000636.SZ",expected,observed)

    def test_missing_interior_session_fails_closed(self):
        dates=gates.load_exchange_trading_calendar("evidence/agent_brain/cn_exchange_calendar_2026.json")
        expected=gates.feature_window_dates("2026-10-09",dates,required_sessions=31)
        observed=[d for d in expected if d!=expected[-6]]
        with self.assertRaisesRegex(ContractGateError,"MISSING_EXCHANGE_SESSIONS"):
            gates.validate_feature_window_continuity("000636.SZ",expected,observed)

    def test_live_ingest_checks_window_before_any_write(self):
        src=Path("scripts/live_pit_ingest.py").read_text(encoding="utf-8")
        tree=ast.parse(src)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        checks=[n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="validate_feature_window_continuity"]
        writes=[n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="insert_source"]
        self.assertTrue(checks); self.assertTrue(writes); self.assertLess(min(checks),min(writes))

    def test_lookback_bar_at_cutoff_is_available(self):
        cutoff=datetime(2026,10,22,8,10,tzinfo=timezone.utc)
        self.assertTrue(historical_bar_available_by_cutoff(cutoff,cutoff))

    def test_lookback_bar_before_cutoff_is_available(self):
        self.assertTrue(historical_bar_available_by_cutoff("2026-10-22T08:09:59Z","2026-10-22T08:10:00Z"))

    def test_lookback_bar_after_cutoff_is_not_available(self):
        self.assertFalse(historical_bar_available_by_cutoff("2026-10-22T08:10:01Z","2026-10-22T08:10:00Z"))

    def test_lookback_cutoff_requires_timezone_aware_timestamps(self):
        with self.assertRaisesRegex(ContractGateError,"TIMEZONE_AWARE"):
            historical_bar_available_by_cutoff("2026-10-22T08:10:00","2026-10-22T08:10:00Z")


if __name__=="__main__":
    unittest.main()
