import importlib
import unittest


mod = importlib.import_module('gp12_sohu_qfq_adapter_v1')


SOHU = b'''historySearchHandler([{"status":0,"hq":[
["2025-07-15","10.00","10.00","0","0.00%","9.90","10.10","100","100.00","1.00%","0.00"],
["2025-07-16","10.00","10.20","0.20","2.00%","9.90","10.30","100","102.00","1.00%","0.00"],
["2025-07-17","10.20","10.10","-0.10","-0.98%","10.00","10.30","100","101.00","1.00%","0.00"]
]}]);'''
SINA = b'''var sz300592qfq={"total":3,"data":[
{"d":"2026-07-09", "f":"1.0000000000000000"},
{"d":"2025-07-16", "f":"1.0142673216863000"},
{"d":"1900-01-01", "f":"1.0142673216863000"}]};'''


class ParserTests(unittest.TestCase):
    def test_sohu_parser_normalizes_units_and_rejects_duplicate_dates(self):
        rows = mod.parse_sohu_hishq_bytes('300592.SZ', SOHU)
        self.assertEqual(rows[0]['date'], '2025-07-15')
        self.assertEqual(rows[0]['volume_shares'], 10000.0)
        self.assertEqual(rows[0]['amount_cny'], 1_000_000.0)
        self.assertEqual(rows[0]['turnover_ratio'], 0.01)
        with self.assertRaises(ValueError):
            mod.parse_sohu_hishq_bytes('300592.SZ', SOHU.replace(
                b'["2025-07-17"', b'["2025-07-16"', 1))

    def test_sina_factor_normalization_is_anchor_bounded(self):
        factors = mod.parse_sina_qfq_js('300592.SZ', SINA)
        self.assertEqual(mod.factor_for_date(factors, '2025-07-16'), 1.0142673216863)
        self.assertEqual(
            mod.sina_normalized_for_date(factors, '2025-07-15', '2025-07-17'),
            1.0,
        )
        with self.assertRaises(ValueError):
            mod.sina_normalized_for_date(factors, '2025-07-15', '2027-01-01')

    def test_materializer_keeps_raw_and_adjusted_close_distinct(self):
        rows = mod.parse_sohu_hishq_bytes('300592.SZ', SOHU)
        factors = mod.parse_sina_qfq_js('300592.SZ', SINA)
        out = mod.materialize_qfq_rows(rows, factors, anchor='2025-07-17')
        self.assertEqual(out[0]['raw_close'], 10.0)
        self.assertEqual(out[0]['adjusted_close'], 10.0)
        self.assertEqual(out[0]['adjustment'], 'sina_qfq_normalized')
        self.assertEqual(out[0]['known_at'], None)


if __name__ == '__main__':
    unittest.main()
