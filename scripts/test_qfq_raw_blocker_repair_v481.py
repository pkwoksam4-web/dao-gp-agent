import json
import unittest

from qfq_raw_blocker_repair_v481 import (
    parse_eastmoney_raw_kline,
    choose_raw_provider,
)


class EastMoneyRawParserTests(unittest.TestCase):
    def test_parse_daily_raw_kline(self):
        raw=json.dumps({
            'data':{
                'klines':[
                    '2024-05-21,20.00,20.10,20.30,19.80,100,200000,2.5,0.0,0.0,0.0',
                    '2024-05-22,20.20,20.30,20.50,20.00,120,240000,2.4,1.0,0.2,0.0',
                ]
            }
        }).encode()
        rows=parse_eastmoney_raw_kline(raw)
        self.assertEqual(rows[0]['date'],'2024-05-21')
        self.assertEqual(rows[0]['close'],20.10)
        self.assertEqual(rows[1]['high'],20.50)

    def test_empty_or_error_payload_fails(self):
        with self.assertRaises(ValueError):
            parse_eastmoney_raw_kline(b'{"data":null}')


class ProviderSelectionTests(unittest.TestCase):
    def test_valid_sohu_is_preferred(self):
        self.assertEqual(choose_raw_provider(sohu_ok=True, eastmoney_ok=True),'SOHU_RAW')

    def test_eastmoney_is_explicit_fallback(self):
        self.assertEqual(choose_raw_provider(sohu_ok=False, eastmoney_ok=True),'EASTMONEY_FQT0_FALLBACK')

    def test_no_valid_provider_blocks(self):
        self.assertEqual(choose_raw_provider(sohu_ok=False, eastmoney_ok=False),'BLOCKED_NO_RAW_PROVIDER')


if __name__=='__main__':
    unittest.main()
