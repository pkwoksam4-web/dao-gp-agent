import importlib
import unittest


mod = importlib.import_module('gp12_source_router_v1')


def reports():
    return {
        'sohu_sina_qfq': {
            'families': {
                'stock_adjusted_close': {'status': 'PASS', 'rows': 121},
                'amount_turnover': {'status': 'PASS', 'rows': 121},
            },
            'point_in_time_known_at': False,
            'source_ids_substantively_verified': False,
        },
        'eastmoney': {
            'families': {
                'stock_adjusted_close': {'status': 'PASS', 'rows': 12},
                'amount_turnover': {'status': 'PASS', 'rows': 12},
                'intraday_15m': {'status': 'PASS', 'rows': 5},
                'intraday_60m': {'status': 'PASS', 'rows': 5},
                'main_net_flow': {'status': 'FAILED_SOURCE', 'rows': 0},
            },
            'point_in_time_known_at': False,
            'source_ids_substantively_verified': False,
        },
    }


class SourceRouterTests(unittest.TestCase):
    def test_prefers_longer_priority_source_for_overlapping_families(self):
        report = mod.build_source_switch_report(reports())
        self.assertEqual(
            report['routes']['stock_adjusted_close']['source_id'], 'sohu_sina_qfq')
        self.assertEqual(report['routes']['stock_adjusted_close']['rows'], 121)
        self.assertEqual(
            report['routes']['amount_turnover']['source_id'], 'sohu_sina_qfq')

    def test_routes_intraday_to_eastmoney_when_fallback_is_the_only_pass(self):
        report = mod.build_source_switch_report(reports())
        self.assertEqual(report['routes']['intraday_15m']['source_id'], 'eastmoney')
        self.assertEqual(report['routes']['intraday_60m']['source_id'], 'eastmoney')
        self.assertEqual(report['routes']['intraday_15m']['rows'], 5)

    def test_failed_and_unrepresented_families_remain_fail_closed(self):
        report = mod.build_source_switch_report(reports())
        self.assertIn('main_net_flow', report['missing_families'])
        self.assertIn('market_breadth', report['missing_families'])
        self.assertEqual(report['failed_families']['main_net_flow'], ['eastmoney'])
        self.assertFalse(report['structural_feature_families_complete'])
        self.assertFalse(report['point_in_time_known_at'])
        self.assertFalse(report['real_feature_inputs_validated'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])

    def test_source_order_is_explicit_and_deterministic(self):
        report = mod.build_source_switch_report(
            reports(), priority=('eastmoney', 'sohu_sina_qfq'))
        self.assertEqual(
            report['routes']['stock_adjusted_close']['source_id'], 'eastmoney')
        self.assertEqual(report['priority'], ['eastmoney', 'sohu_sina_qfq'])


if __name__ == '__main__':
    unittest.main()
