import copy
import unittest

from gp12_turnover_pit_admission_v482 import (
    audit_adjustflag_invariance,
    audit_prefix_invariance,
    audit_replay,
    build_turnover_pit_admission,
)


class GP12TurnoverPitAdmissionV482Test(unittest.TestCase):
    def _rows(self):
        return [
            {"symbol":"000001.SZ","date":"2024-01-02","turn":1.2345,"volume":1000,"amount":1234.5,"tradestatus":1,"isST":0},
            {"symbol":"000001.SZ","date":"2024-01-03","turn":1.1000,"volume":900,"amount":1100.0,"tradestatus":1,"isST":0},
            {"symbol":"000002.SZ","date":"2024-01-02","turn":0.0,"volume":100,"amount":200.0,"tradestatus":1,"isST":0},
        ]

    def _structural(self):
        return {"status":"PASS_STRUCTURAL_PITST_ALIGNED_TURNOVER","aligned_trade_rows":1011607,"sohu_trade_rows":1011607,"exact_symbol_date_coverage":True,"turn_missing_n":0,"turn_negative_n":0}

    def _replay(self):
        return {"status":"PASS_REPLAY_EXACT","expected_n":1011607,"matched_n":1011607,"missing_n":0,"extra_n":0,"mismatch_n":0}

    def _prefix(self):
        return {"status":"PASS_PREFIX_MATRIX_INVARIANCE","symbol_n":844,"probe_n":844,"missing_n":0,"extra_n":0,"mismatch_n":0}

    def _flag(self):
        return {"status":"PASS_ADJUSTFLAG_INVARIANCE","symbol_n":50,"mismatch_n":0,"missing_n":0,"extra_n":0}

    def test_exact_replay_passes(self):
        x=audit_replay(self._rows(), copy.deepcopy(self._rows()))
        self.assertEqual(x["status"],"PASS_REPLAY_EXACT")
        self.assertEqual(x["mismatch_n"],0)
        self.assertEqual(x["missing_n"],0)
        self.assertEqual(x["extra_n"],0)

    def test_replay_turn_mismatch_fails(self):
        live=copy.deepcopy(self._rows())
        live[0]["turn"]=1.2346
        x=audit_replay(self._rows(),live)
        self.assertEqual(x["status"],"REVIEW_REPLAY_EXACT")
        self.assertEqual(x["mismatch_n"],1)
        self.assertIn("turn",x["mismatches"][0]["fields"])

    def test_prefix_must_equal_full_subset(self):
        full=self._rows()
        prefix=[r for r in full if r["date"] <= "2024-01-02"]
        x=audit_prefix_invariance(full,prefix,"2024-01-02")
        self.assertEqual(x["status"],"PASS_PREFIX_INVARIANCE")
        self.assertEqual(x["expected_n"],2)

    def test_prefix_missing_row_fails(self):
        x=audit_prefix_invariance(self._rows(),[],"2024-01-02")
        self.assertEqual(x["status"],"REVIEW_PREFIX_INVARIANCE")
        self.assertEqual(x["missing_n"],2)

    def test_adjustflag_turn_is_invariant(self):
        f3=self._rows()
        f2=copy.deepcopy(f3)
        f1=copy.deepcopy(f3)
        x=audit_adjustflag_invariance({"1":f1,"2":f2,"3":f3})
        self.assertEqual(x["status"],"PASS_ADJUSTFLAG_INVARIANCE")
        self.assertEqual(x["mismatch_n"],0)

    def test_adjustflag_turn_change_fails(self):
        f3=self._rows()
        f2=copy.deepcopy(f3); f2[1]["turn"]=9.9
        x=audit_adjustflag_invariance({"2":f2,"3":f3})
        self.assertEqual(x["status"],"REVIEW_ADJUSTFLAG_INVARIANCE")
        self.assertEqual(x["mismatch_n"],1)

    def test_admission_closes_turnover_only_for_844_row_bearing_plus_3_na(self):
        x=build_turnover_pit_admission(self._structural(),self._replay(),self._prefix(),self._flag())
        self.assertEqual(x["status"],"PASS_TURNOVER_RATIO_PIT_ADMISSION")
        self.assertEqual(x["scope"],{
            "universe_symbol_n":847,
            "row_bearing_symbol_n":844,
            "not_applicable_symbol_n":3,
            "trade_row_n":1011607,
            "sample_adjustflag_symbol_n":50,
        })
        self.assertTrue(x["promotion"]["turnover_ratio_blocker_closed"])
        self.assertFalse(x["promotion"]["label_provenance_blocker_closed"])
        self.assertFalse(x["promotion"]["model_freeze_allowed"])
        self.assertFalse(x["promotion"]["oos_metrics_allowed"])
        self.assertEqual(x["remaining_gp12_blockers"],["LABEL_PROVENANCE_UNBOUND"])

    def test_admission_fails_closed_on_prefix_mismatch(self):
        prefix=self._prefix(); prefix["status"]="REVIEW_PREFIX_MATRIX_INVARIANCE"; prefix["mismatch_n"]=1
        with self.assertRaisesRegex(ValueError,"prefix"):
            build_turnover_pit_admission(self._structural(),self._replay(),prefix,self._flag())

    def test_admission_rejects_847_row_bearing_symbols(self):
        prefix=self._prefix(); prefix["symbol_n"]=847; prefix["probe_n"]=847
        with self.assertRaisesRegex(ValueError,"prefix"):
            build_turnover_pit_admission(self._structural(),self._replay(),prefix,self._flag())


if __name__ == "__main__":
    unittest.main()
