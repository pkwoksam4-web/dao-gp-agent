import importlib
import unittest


mod = importlib.import_module('gp12_eastmoney_adapter_v1')


def kline_payload(*lines):
    return {'data': {'code': '300592', 'klines': list(lines)}}


class SymbolAndParserTests(unittest.TestCase):
    def test_plans_bounded_calendar_chunks_without_gaps_or_overlaps(self):
        chunks = mod.plan_date_chunks('2026-01-01', '2026-04-17', max_calendar_days=31)
        self.assertEqual(chunks[0], ('2026-01-01', '2026-01-31'))
        self.assertEqual(chunks[-1], ('2026-04-04', '2026-04-17'))
        self.assertEqual(
            [(left, right) for left, right in chunks],
            [('2026-01-01', '2026-01-31'), ('2026-02-01', '2026-03-03'),
             ('2026-03-04', '2026-04-03'), ('2026-04-04', '2026-04-17')],
        )

    def test_normalizes_exchange_qualified_symbols_and_rejects_ambiguous_codes(self):
        self.assertEqual(mod.normalize_symbol('300592.sz'), '300592.SZ')
        self.assertEqual(mod.symbol_to_secid('600000.SH'), '1.600000')
        with self.assertRaises(ValueError):
            mod.normalize_symbol('300592')

    def test_parses_adjusted_daily_kline_without_substituting_raw_close(self):
        rows = mod.parse_kline_payload(
            '300592.SZ',
            kline_payload('2026-04-17,11.57,12.11,12.18,11.49,80300,96449114.00,6.06,6.41,0.73,2.30'),
            interval='1d',
            adjustment='qfq',
        )
        self.assertEqual(rows[0]['date'], '2026-04-17')
        self.assertEqual(rows[0]['adjustment'], 'qfq')
        self.assertEqual(rows[0]['close'], 12.11)
        self.assertEqual(rows[0]['amount_cny'], 96449114.0)
        self.assertEqual(rows[0]['turnover_ratio'], 0.023)
        self.assertEqual(rows[0]['source_id'], 'eastmoney:kline:klt=101:fqt=1')

    def test_parses_intraday_bars_with_explicit_unverified_availability(self):
        rows = mod.parse_kline_payload(
            '300592.SZ',
            kline_payload('2026-04-17 14:45,11.57,12.11,12.18,11.49,803,964491.00,6.06,6.41,0.73,0.00'),
            interval='15m',
            adjustment='qfq',
        )
        self.assertEqual(rows[0]['closed_at'], '2026-04-17 14:45')
        self.assertIsNone(rows[0]['known_at'])
        self.assertEqual(rows[0]['source_id'], 'eastmoney:kline:klt=15:fqt=1')

    def test_parses_main_net_flow_from_flow_daykline(self):
        payload = {
            'data': {
                'code': '300592',
                'klines': ['2026-04-17,-1817173.0,9219133.0,-7401960.0,-1817173.0,0.0,-2.90,14.72,-11.82,-2.90,0.00'],
            }
        }
        rows = mod.parse_flow_payload('300592.SZ', payload)
        self.assertEqual(rows, [{
            'symbol': '300592.SZ',
            'date': '2026-04-17',
            'main_net_flow_cny': -1817173.0,
            'source_id': 'eastmoney:flow:daykline',
        }])


class ReadinessTests(unittest.TestCase):
    def test_empty_pass_response_is_not_treated_as_available_feature_data(self):
        report = mod.build_readiness_report({
            family: {'status': 'PASS', 'rows': 0} for family in mod.REQUIRED_FAMILIES
        })
        self.assertFalse(report['structural_feature_families_complete'])
        self.assertTrue(all(
            status == 'EMPTY' for status in report['family_statuses'].values()))

    def test_probe_report_keeps_missing_feature_families_fail_closed(self):
        report = mod.build_readiness_report({
            'stock_adjusted_close': {'status': 'PASS', 'rows': 121},
            'market_adjusted_close': {'status': 'PASS', 'rows': 121},
            'sector_adjusted_close': {'status': 'MISSING'},
            'amount_turnover': {'status': 'PASS', 'rows': 121},
            'main_net_flow': {'status': 'PASS', 'rows': 121},
            'market_breadth': {'status': 'MISSING'},
            'sector_breadth': {'status': 'MISSING'},
            'status': {'status': 'MISSING'},
            'intraday_15m': {'status': 'FAILED_HTTP'},
            'intraday_60m': {'status': 'FAILED_HTTP'},
        })
        self.assertFalse(report['structural_feature_families_complete'])
        self.assertEqual(report['real_feature_inputs_validated'], False)
        self.assertIn('sector_adjusted_close', report['missing_families'])
        self.assertIn('intraday_15m', report['missing_families'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
