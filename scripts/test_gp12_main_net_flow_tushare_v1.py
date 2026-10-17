import csv
import pathlib
import tempfile
import unittest

from gp12_main_net_flow_tushare_v1 import (
    MONEYFLOW_FIELDS,
    NA_SYMBOLS,
    aggregate_shard_records,
    aggregate_shard_reports,
    audit_symbol_rows,
    build_symbol_evidence,
    expected_dates_from_records,
    fetch_moneyflow_records,
    formal_symbols_from_scope,
    normalize_moneyflow_records,
    run_shard,
    summarize_formal_audit,
    write_panel_csv,
)


class _FakeFrame:
    def __init__(self, records):
        self.records = list(records)

    def to_dict(self, orient):
        if orient != "records":
            raise AssertionError(f"unexpected orient: {orient}")
        return list(self.records)


class _FakeApi:
    def __init__(self, records=None, error=None):
        self.records = records or []
        self.error = error
        self.calls = []

    def moneyflow(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return _FakeFrame(self.records)


class _PerSymbolApi:
    def __init__(self, mapping=None, errors=None):
        self.mapping = mapping or {}
        self.errors = errors or {}
        self.calls = []

    def moneyflow(self, **kwargs):
        self.calls.append(kwargs)
        symbol = kwargs["ts_code"]
        if symbol in self.errors:
            raise self.errors[symbol]
        return _FakeFrame(self.mapping.get(symbol, []))


class MainNetFlowTushareContractTests(unittest.TestCase):
    def test_normalizes_large_and_extra_large_net_flow_to_cny(self):
        rows = normalize_moneyflow_records(
            "000001.SZ",
            [{
                "ts_code": "000001.SZ",
                "trade_date": "20200601",
                "buy_lg_amount": 120.5,
                "sell_lg_amount": 20.25,
                "buy_elg_amount": 50.0,
                "sell_elg_amount": 10.25,
                "net_mf_amount": 140.0,
            }],
        )
        self.assertEqual(rows, [{
            "symbol": "000001.SZ",
            "date": "2020-06-01",
            "main_net_flow_cny": 1_400_000.0,
            "known_at": "2020-06-01T15:00:00+08:00",
            "source": "TUSHARE_MONEYFLOW_LG_ELG_ACTIVE_BUY_MINUS_SELL",
        }])

    def test_zero_and_negative_main_flow_are_valid(self):
        rows = normalize_moneyflow_records(
            "600000.SH",
            [
                {"ts_code":"600000.SH","trade_date":"20200601","buy_lg_amount":1,"sell_lg_amount":2,"buy_elg_amount":3,"sell_elg_amount":2,"net_mf_amount":0},
                {"ts_code":"600000.SH","trade_date":"20200602","buy_lg_amount":1,"sell_lg_amount":3,"buy_elg_amount":1,"sell_elg_amount":4,"net_mf_amount":-5},
            ],
        )
        self.assertEqual(rows[0]["main_net_flow_cny"], 0.0)
        self.assertEqual(rows[1]["main_net_flow_cny"], -50_000.0)

    def test_rejects_identity_missing_fields_and_nonfinite_values(self):
        with self.assertRaises(ValueError):
            normalize_moneyflow_records("000001.SZ", [{
                "ts_code":"600000.SH","trade_date":"20200601",
                "buy_lg_amount":1,"sell_lg_amount":1,"buy_elg_amount":1,"sell_elg_amount":1,
            }])
        with self.assertRaises(ValueError):
            normalize_moneyflow_records("000001.SZ", [{
                "ts_code":"000001.SZ","trade_date":"20200601",
                "buy_lg_amount":1,"sell_lg_amount":1,"buy_elg_amount":float("nan"),"sell_elg_amount":1,
            }])

    def test_symbol_audit_requires_exact_sorted_unique_date_axis(self):
        expected = ["2020-06-01", "2020-06-02"]
        good = [
            {"date":"2020-06-01","main_net_flow_cny":0.0},
            {"date":"2020-06-02","main_net_flow_cny":-1.0},
        ]
        report = audit_symbol_rows("000001.SZ", expected, good)
        self.assertTrue(report["symbol_pass"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["pit_scope"], "SESSION_CLOSE_NO_LOOKAHEAD_POLICY")
        self.assertFalse(report["same_session_main_net_flow_usable_before_close"])
        self.assertFalse(report["historical_provider_publication_timestamp_proven"])

        bad = audit_symbol_rows("000001.SZ", expected, [
            {"date":"2020-06-02","main_net_flow_cny":1.0},
            {"date":"2020-06-02","main_net_flow_cny":2.0},
            {"date":"2020-06-03","main_net_flow_cny":3.0},
        ])
        self.assertFalse(bad["symbol_pass"])
        self.assertIn("MAIN_NET_FLOW_DUPLICATE_DATE", bad["blockers"])
        self.assertIn("MAIN_NET_FLOW_DATE_ORDER_INVALID", bad["blockers"])
        self.assertIn("MAIN_NET_FLOW_DATE_GAP", bad["blockers"])
        self.assertIn("MAIN_NET_FLOW_EXTRA_DATE", bad["blockers"])

    def test_formal_summary_is_fail_closed_until_844_and_exact_total_rows(self):
        one = {
            "symbol":"000001.SZ","symbol_pass":True,"row_n":2,
            "coverage_exact":True,"pit_policy_valid":True,"blockers":[],
        }
        report = summarize_formal_audit([one], expected_trade_rows=1_011_607)
        self.assertFalse(report["main_net_flow_candidate_pit_verified"])
        self.assertFalse(report["model_freeze_allowed"])
        self.assertFalse(report["oos_metrics_allowed"])
        self.assertIn("MAIN_NET_FLOW_FORMAL_SYMBOL_COVERAGE_INCOMPLETE", report["blockers"])
        self.assertIn("MAIN_NET_FLOW_TOTAL_ROW_COVERAGE_MISMATCH", report["blockers"])

    def test_fetch_uses_exchange_symbol_formal_dates_and_explicit_fields(self):
        api = _FakeApi(records=[])
        records = fetch_moneyflow_records(
            api,
            "000001.SZ",
            start_date="2020-06-01",
            end_date="2026-04-17",
        )
        self.assertEqual(records, [])
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(api.calls[0], {
            "ts_code": "000001.SZ",
            "start_date": "20200601",
            "end_date": "20260417",
            "fields": ",".join(MONEYFLOW_FIELDS),
        })

    def test_source_errors_propagate_and_symbol_evidence_fails_closed_on_gap(self):
        error = RuntimeError("permission denied")
        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            fetch_moneyflow_records(_FakeApi(error=error), "000001.SZ")

        api = _FakeApi(records=[{
            "ts_code":"000001.SZ","trade_date":"20200601",
            "buy_lg_amount":1,"sell_lg_amount":0,"buy_elg_amount":0,"sell_elg_amount":0,
            "net_mf_amount":1,
        }])
        evidence = build_symbol_evidence(
            api,
            "000001.SZ",
            ["2020-06-01", "2020-06-02"],
        )
        self.assertFalse(evidence["audit"]["symbol_pass"])
        self.assertIn("MAIN_NET_FLOW_DATE_GAP", evidence["audit"]["blockers"])
        self.assertEqual(len(evidence["rows"]), 1)

    def test_write_panel_csv_is_deterministic(self):
        rows = [
            {"symbol":"600000.SH","date":"2020-06-02","main_net_flow_cny":-1.0,"known_at":"2020-06-02T15:00:00+08:00","source":"S"},
            {"symbol":"000001.SZ","date":"2020-06-01","main_net_flow_cny":2.0,"known_at":"2020-06-01T15:00:00+08:00","source":"S"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "panel.csv"
            write_panel_csv(path, rows)
            with path.open(newline="", encoding="utf-8") as handle:
                got = list(csv.DictReader(handle))
        self.assertEqual([(r["symbol"], r["date"]) for r in got], [
            ("000001.SZ", "2020-06-01"),
            ("600000.SH", "2020-06-02"),
        ])

    def test_aggregate_shards_rejects_duplicate_symbols(self):
        record = {"symbol":"000001.SZ","symbol_pass":True,"row_n":1,"blockers":[]}
        with self.assertRaisesRegex(ValueError, "duplicate shard symbol"):
            aggregate_shard_records([[record], [record]])

    def test_formal_scope_is_exact_847_minus_three_na_symbols(self):
        scope = [f"{i:06d}.SZ" for i in range(1, 845)] + list(NA_SYMBOLS)
        formal = formal_symbols_from_scope(scope)
        self.assertEqual(len(scope), 847)
        self.assertEqual(len(formal), 844)
        self.assertTrue(all(symbol not in formal for symbol in NA_SYMBOLS))
        with self.assertRaisesRegex(ValueError, "Formal847 scope identity mismatch"):
            formal_symbols_from_scope(scope[:-1] + [scope[0]])

    def test_expected_dates_are_taken_from_positive_amount_raw_rows(self):
        records = [
            {"symbol":"000001.SZ","date":"2020-06-01","amount":10},
            {"symbol":"000001.SZ","date":"2020-06-02","amount":20},
            {"symbol":"600000.SH","date":"2020-06-01","amount":30},
        ]
        expected = expected_dates_from_records(records, ["000001.SZ", "600000.SH"])
        self.assertEqual(expected["000001.SZ"], ["2020-06-01", "2020-06-02"])
        self.assertEqual(expected["600000.SH"], ["2020-06-01"])
        with self.assertRaisesRegex(ValueError, "nonpositive or missing"):
            expected_dates_from_records([
                {"symbol":"000001.SZ","date":"2020-06-01","amount":0},
            ], ["000001.SZ"])

    def test_run_shard_continues_after_source_failure_but_materializes_only_passes(self):
        api = _PerSymbolApi(
            mapping={
                "000001.SZ": [{
                    "ts_code":"000001.SZ","trade_date":"20200601",
                    "buy_lg_amount":2,"sell_lg_amount":1,"buy_elg_amount":1,"sell_elg_amount":0,
                    "net_mf_amount":2,
                }],
            },
            errors={"000002.SZ": RuntimeError("temporary source failure")},
        )
        report, materialized = run_shard(
            api,
            ["000001.SZ", "000002.SZ"],
            {
                "000001.SZ": ["2020-06-01"],
                "000002.SZ": ["2020-06-01"],
            },
            shard_index=0,
            shard_count=1,
            inter_symbol_delay=0,
        )
        self.assertEqual(report["symbol_n"], 2)
        self.assertEqual(report["pass_n"], 1)
        self.assertEqual(report["fail_n"], 1)
        failed = next(r for r in report["records"] if r["symbol"] == "000002.SZ")
        self.assertEqual(failed["blockers"], ["MAIN_NET_FLOW_SOURCE_FETCH_FAILED"])
        self.assertEqual(len(materialized), 1)
        self.assertEqual(materialized[0]["symbol"], "000001.SZ")

    def test_aggregate_shard_reports_requires_complete_unique_shard_partition(self):
        base = {
            "artifact":"GP12_MAIN_NET_FLOW_SHARD_V1",
            "version":"1.0",
            "shard_count":2,
            "symbol_n":1,
            "pass_n":1,
            "fail_n":0,
        }
        r0 = {**base, "shard_index":0, "records":[{"symbol":"000001.SZ","symbol_pass":True,"row_n":1,"blockers":[]}]}
        r1 = {**base, "shard_index":1, "records":[{"symbol":"000002.SZ","symbol_pass":True,"row_n":1,"blockers":[]}]}
        out = aggregate_shard_reports([r0, r1])
        self.assertEqual(len(out["records"]), 2)
        self.assertFalse(out["main_net_flow_candidate_pit_verified"])
        with self.assertRaisesRegex(ValueError, "shard partition incomplete"):
            aggregate_shard_reports([r0])


if __name__ == "__main__":
    unittest.main()
