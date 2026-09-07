import unittest

import sohu_raw_v482 as m


class SohuRawV482Tests(unittest.TestCase):
    def test_parse_known_hishq_row_normalizes_volume_and_amount(self):
        raw=(
            'historySearchHandler([{"status":0,"hq":['
            '["2019-01-02","9.39","9.19","-0.19","-2.03%","9.16","9.42","539386","49869.51","0.31%"]'
            '],"code":"cn_000001"}])'
        ).encode('utf-8')
        rows=m.parse_hishq_bytes('000001.SZ',raw)
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r['date'],'2019-01-02')
        self.assertAlmostEqual(r['open'],9.39)
        self.assertAlmostEqual(r['close'],9.19)
        self.assertAlmostEqual(r['low'],9.16)
        self.assertAlmostEqual(r['high'],9.42)
        self.assertAlmostEqual(r['volume'],53_938_600.0)
        self.assertAlmostEqual(r['amount'],498_695_100.0)
        self.assertEqual(r['source'],'SOHU_HISHQ_RAW')

    def test_empty_or_status_nonzero_returns_no_rows(self):
        self.assertEqual(m.parse_hishq_bytes('000001.SZ',b'historySearchHandler([{"status":0,"hq":[]}])'),[])
        self.assertEqual(m.parse_hishq_bytes('000001.SZ',b'historySearchHandler([{"status":1}])'),[])

    def test_chunk_plan_is_contiguous_nonoverlapping_and_bounded(self):
        chunks=m.plan_chunks('2020-06-01','2021-01-15',max_calendar_days=90)
        self.assertGreater(len(chunks),1)
        self.assertEqual(chunks[0][0],'2020-06-01')
        self.assertEqual(chunks[-1][1],'2021-01-15')
        from datetime import date
        prev=None
        for a,b in chunks:
            da,db=date.fromisoformat(a),date.fromisoformat(b)
            self.assertLessEqual((db-da).days+1,90)
            if prev is not None:
                self.assertEqual((da-prev).days,1)
            prev=db

    def test_symbol_requires_exchange_qualification(self):
        self.assertEqual(m.normalize_symbol('600000.SH'),'600000.SH')
        self.assertEqual(m.normalize_symbol('1.sz'),'000001.SZ')
        with self.assertRaises(ValueError):
            m.normalize_symbol('000001')


if __name__=='__main__':
    unittest.main()
