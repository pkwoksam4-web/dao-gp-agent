import unittest
from global_qfq_source_v481 import parse_sina_qfq_js, classify_source, sina_symbol, shard_symbols


class ParseTests(unittest.TestCase):
    def test_parse_real_object_rows(self):
        raw = b'var KKE_ShareHFq={total:2,data:[{"d":"2025-07-16","f":"1.0142673216863"},{"d":"2024-05-21","f":"1.0187754257059"}]};'
        rows = parse_sina_qfq_js(raw)
        self.assertEqual(rows[0]['date'], '2025-07-16')
        self.assertGreater(rows[0]['factor'], 0)
        self.assertEqual(len(rows), 2)

    def test_empty_data_is_not_factor_one(self):
        raw = b'var KKE_ShareHFq={total:0,data:[]};'
        rows = parse_sina_qfq_js(raw)
        r = classify_source('000001.SZ', 200, 'application/x-javascript', raw, rows, '2026-04-17')
        self.assertEqual(r['status'], 'UNKNOWN_ZERO_ACTION_OR_SOURCE_EMPTY')
        self.assertIsNone(r['anchor_divisor'])

    def test_invalid_body_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_sina_qfq_js(b'<html>blocked</html>')

    def test_no_factor_at_or_before_anchor_is_unknown(self):
        raw = b'var KKE_ShareHFq={total:1,data:[{"d":"2026-07-15","f":"1.03"}]};'
        rows = parse_sina_qfq_js(raw)
        r = classify_source('000001.SZ', 200, 'application/x-javascript', raw, rows, '2026-04-17')
        self.assertEqual(r['status'], 'UNKNOWN_NO_ANCHOR_DIVISOR_BY_FORMAL_END')
        self.assertIsNone(r['anchor_divisor'])

    def test_ready_source_has_anchor_divisor(self):
        raw = b'var KKE_ShareHFq={total:2,data:[{"d":"2026-07-15","f":"1.03"},{"d":"2025-07-16","f":"1.01"}]};'
        rows = parse_sina_qfq_js(raw)
        r = classify_source('000001.SZ', 200, 'application/x-javascript', raw, rows, '2026-04-17')
        self.assertEqual(r['status'], 'SINA_FACTOR_PATH_SOURCE_READY')
        self.assertAlmostEqual(r['anchor_divisor'], 1.01)


class ScopeTests(unittest.TestCase):
    def test_symbol_mapping(self):
        self.assertEqual(sina_symbol('000001.SZ'), 'sz000001')
        self.assertEqual(sina_symbol('600000.SH'), 'sh600000')

    def test_shards_are_disjoint_and_complete(self):
        xs=[f'{i:06d}.SZ' for i in range(17)]
        parts=[shard_symbols(xs, i, 4) for i in range(4)]
        flat=[x for p in parts for x in p]
        self.assertEqual(sorted(flat), sorted(xs))
        self.assertEqual(len(flat), len(set(flat)))


if __name__ == '__main__':
    unittest.main()
