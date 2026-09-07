import unittest

import eastmoney_raw_v482 as m


class EastmoneyRawTests(unittest.TestCase):
    def test_exchange_qualified_symbol_maps_to_secid(self):
        self.assertEqual(m.symbol_to_secid('000001.SZ'),'0.000001')
        self.assertEqual(m.symbol_to_secid('600634.SH'),'1.600634')

    def test_parse_fqt0_kline_normalizes_volume_lots_to_shares(self):
        payload={'data':{'klines':['2020-06-01,10.00,10.20,10.30,9.90,12345,12500000.50,0,0,0,0']}}
        rows=m.parse_payload('000001.SZ',payload)
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r['date'],'2020-06-01')
        self.assertEqual(r['open'],10.0)
        self.assertEqual(r['close'],10.2)
        self.assertEqual(r['high'],10.3)
        self.assertEqual(r['low'],9.9)
        self.assertEqual(r['volume'],1_234_500.0)
        self.assertEqual(r['amount'],12_500_000.50)
        self.assertEqual(r['source'],'EASTMONEY_FQT0_RAW')

    def test_payload_none_is_empty_not_fake_zero_row(self):
        self.assertEqual(m.parse_payload('600634.SH',{'data':None}),[])

    def test_scope_loader_requires_exchange_suffix(self):
        self.assertEqual(m.normalize_symbol('300104.SZ'),'300104.SZ')
        with self.assertRaises(ValueError):
            m.normalize_symbol('300104')


if __name__=='__main__':
    unittest.main()
