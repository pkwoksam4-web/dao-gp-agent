import unittest

from gp12_event_timing_admission_v482 import (
    audit_event_timing,
    build_expected_events,
    infer_supplemental_pit_date,
)


class GP12EventTimingAdmissionV482Test(unittest.TestCase):
    def _expected(self):
        return [
            {"symbol": "000001.SZ", "ex_date": "2024-01-10", "source": "SRC_A"},
            {"symbol": "000002.SZ", "ex_date": "2024-02-20", "source": "SRC_B"},
            {"symbol": "000003.SZ", "ex_date": "2024-03-15", "source": "SRC_B"},
        ]

    def _observed(self):
        return [
            {
                "symbol": "000001.SZ",
                "ex_date": "2024-01-10",
                "source": "SRC_A",
                "pit_date": "2024-01-05",
                "evidence_id": "e1",
            },
            {
                "symbol": "000002.SZ",
                "ex_date": "2024-02-20",
                "source": "SRC_B",
                "pit_date": "2024-02-20",
                "evidence_id": "e2",
            },
            {
                "symbol": "000003.SZ",
                "ex_date": "2024-03-15",
                "source": "SRC_B",
                "pit_date": "2024-03-01",
                "evidence_id": "e3",
            },
        ]

    def test_complete_partition_passes(self):
        result = audit_event_timing(
            self._expected(),
            self._observed(),
            required_source_counts={"SRC_A": 1, "SRC_B": 2},
        )
        self.assertEqual(result["status"], "PASS_EVENT_TIMING_ADMISSION")
        self.assertEqual(result["expected_n"], 3)
        self.assertEqual(result["covered_n"], 3)
        self.assertEqual(result["missing_n"], 0)
        self.assertEqual(result["extra_n"], 0)
        self.assertEqual(result["late_n"], 0)
        self.assertEqual(result["source_counts"], {"SRC_A": 1, "SRC_B": 2})

    def test_missing_event_fails_closed(self):
        result = audit_event_timing(self._expected(), self._observed()[:-1])
        self.assertEqual(result["status"], "REVIEW_EVENT_TIMING_ADMISSION")
        self.assertEqual(result["missing_n"], 1)
        self.assertEqual(result["covered_n"], 2)

    def test_late_event_fails_closed(self):
        observed = self._observed()
        observed[1] = dict(observed[1], pit_date="2024-02-21")
        result = audit_event_timing(self._expected(), observed)
        self.assertEqual(result["status"], "REVIEW_EVENT_TIMING_ADMISSION")
        self.assertEqual(result["late_n"], 1)
        self.assertEqual(result["late_rows"][0]["symbol"], "000002.SZ")

    def test_duplicate_expected_key_is_rejected(self):
        expected = self._expected() + [dict(self._expected()[0])]
        with self.assertRaisesRegex(ValueError, "duplicate expected event key"):
            audit_event_timing(expected, self._observed())

    def test_duplicate_observed_key_is_rejected(self):
        observed = self._observed() + [dict(self._observed()[0])]
        with self.assertRaisesRegex(ValueError, "duplicate observed event key"):
            audit_event_timing(self._expected(), observed)

    def test_required_source_partition_mismatch_fails_closed(self):
        result = audit_event_timing(
            self._expected(),
            self._observed(),
            required_source_counts={"SRC_A": 2, "SRC_B": 1},
        )
        self.assertEqual(result["status"], "REVIEW_EVENT_TIMING_ADMISSION")
        self.assertFalse(result["source_partition_exact"])

    def test_build_expected_events_uses_final_ledger_events(self):
        ledger = {
            "records": [
                {
                    "symbol": "000001.SZ",
                    "events": [
                        {"ex_date": "2024-01-10", "source": "SRC_A"},
                        {"ex_date": "2024-06-11", "source": "SRC_B"},
                    ],
                },
                {"symbol": "000002.SZ", "events": []},
            ]
        }
        self.assertEqual(
            build_expected_events(ledger),
            [
                {"symbol": "000001.SZ", "ex_date": "2024-01-10", "source": "SRC_A"},
                {"symbol": "000001.SZ", "ex_date": "2024-06-11", "source": "SRC_B"},
            ],
        )

    def test_infer_sina_supplemental_date_from_frozen_dividend_row(self):
        record = {
            "source": "SINA_SHAREBONUS",
            "context": (
                "分红 公告日期 分红方案(每10股) 进度 除权除息日 股权登记日 "
                "2021-08-13 0 0 0.13 实施 2021-08-20 2021-08-19 -- 查看 "
                "2020-07-13 0 0 0.03 实施 2020-07-20 2020-07-17 -- 查看"
            ),
        }
        self.assertEqual(
            infer_supplemental_pit_date(record, "2020-07-20", "SINA_SHAREBONUS_FROZEN_HTML"),
            "2020-07-13",
        )

    def test_infer_sohu_supplemental_date_from_target_term(self):
        record = {
            "source": "SOHU_MAJOR_EVENTS",
            "expected_term": "10转增14.82",
            "context": (
                "2022-02-25 关于公司资本公积转增股本实施进展 "
                "2022-02-16 2020年特别转增，10转增14.82除权日 ，2022-02-25 除权除息日，分配方案"
            ),
        }
        self.assertEqual(
            infer_supplemental_pit_date(record, "2022-02-25", "SOHU_MAJOR_EVENTS"),
            "2022-02-16",
        )

    def test_infer_ths_supplemental_date_from_implementation_row(self):
        record = {
            "source": "THS_BONUS_HISTORY",
            "expected_term": "10转22.035714",
            "context": (
                "报告期 董事会日期 股东大会预案公告日期 实施公告日 分红方案说明 A股股权登记日 A股除权除息日 "
                "2021-09-16 2021-09-16 2021-09-30 2021-12-27 10转22.035714股 2021-12-30 2021-12-31"
            ),
        }
        self.assertEqual(
            infer_supplemental_pit_date(record, "2021-12-31", "THS_BONUS_HISTORY"),
            "2021-12-27",
        )

    def test_unparseable_supplemental_date_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "cannot infer supplemental PIT date"):
            infer_supplemental_pit_date(
                {"source": "SOHU_MAJOR_EVENTS", "expected_term": "missing", "context": "no dates here"},
                "2022-02-25",
                "SOHU_MAJOR_EVENTS",
            )


if __name__ == "__main__":
    unittest.main()
