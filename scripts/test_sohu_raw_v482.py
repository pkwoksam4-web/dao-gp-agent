import unittest
from unittest.mock import patch

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

    def test_resilient_fetch_bisects_failed_range_and_merges_rows(self):
        calls=[]

        def fake_fetch_chunk(session,symbol,start,end,timeout=20,retries=3):
            from datetime import date
            calls.append((start,end))
            days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
            if days>45:
                raise RuntimeError('synthetic 503')
            return [
                {'symbol':symbol,'date':start,'open':1.0,'high':1.0,'low':1.0,'close':1.0,'volume':100.0,'amount':1000.0,'source':'SOHU_HISHQ_RAW'},
                {'symbol':symbol,'date':end,'open':1.0,'high':1.0,'low':1.0,'close':1.0,'volume':100.0,'amount':1000.0,'source':'SOHU_HISHQ_RAW'},
            ]

        with patch.object(m,'fetch_chunk',side_effect=fake_fetch_chunk):
            rows,meta=m.fetch_chunk_resilient(object(),'000001.SZ','2020-06-01','2020-08-29',timeout=1,retries=1)

        self.assertGreater(len(calls),1)
        self.assertEqual(rows[0]['date'],'2020-06-01')
        self.assertEqual(rows[-1]['date'],'2020-08-29')
        self.assertEqual(meta['split_recovery_n'],1)
        self.assertGreaterEqual(meta['leaf_chunk_n'],2)

    def test_resilient_fetch_can_recover_six_day_window_by_splitting_to_single_days(self):
        calls=[]

        def fake_fetch_chunk(session,symbol,start,end,timeout=20,retries=3):
            from datetime import date
            calls.append((start,end))
            days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
            if days>1:
                raise RuntimeError('synthetic pathological multi-day Sohu window')
            weekday=date.fromisoformat(start).weekday()
            if weekday>=5:
                return []
            return [
                {'symbol':symbol,'date':start,'open':1.0,'high':1.0,'low':1.0,'close':1.0,'volume':100.0,'amount':1000.0,'source':'SOHU_HISHQ_RAW'},
            ]

        with patch.object(m,'fetch_chunk',side_effect=fake_fetch_chunk):
            rows,meta=m.fetch_chunk_resilient(object(),'300064.SZ','2020-08-18','2020-08-23',timeout=1,retries=1)

        self.assertEqual([r['date'] for r in rows],['2020-08-18','2020-08-19','2020-08-20','2020-08-21'])
        self.assertTrue(any(a==b for a,b in calls))
        self.assertGreater(meta['split_recovery_n'],1)
        self.assertEqual(meta['leaf_chunk_n'],6)


if __name__=='__main__':
    unittest.main()
