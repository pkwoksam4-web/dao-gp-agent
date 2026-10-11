from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

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
            validate_prev_close_continuity(rows(),latest)

    def test_prev_close_mismatch_fails_closed(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        bad=rows(); bad[4]["quote"]["normalized"]["prev_close"]=9.0
        with self.assertRaisesRegex(ContractGateError,"PREV_CLOSE_MISMATCH"):
            validate_prev_close_continuity(bad,latest)

    def test_prev_close_13_of_13_passes(self):
        latest={s:{"close":10.0,"trade_date":"2026-10-09"} for s in CORE13}
        self.assertEqual(validate_prev_close_continuity(rows(),latest)["matched"],13)

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
