import copy
import hashlib
import json
import pathlib
import unittest

import oos_calendar_v482 as cal


SSE_HTML = '''
<html><body>
2026年休市安排
劳动节：5月1日（星期五）至5月5日（星期二）休市，5月6日（星期三）起照常开市。另外，5月9日（星期六）为周末休市。
端午节：6月19日（星期五）至6月21日（星期日）休市，6月22日（星期一）起照常开市。
</body></html>
'''

SZSE_HTML = '''
<html><body>
关于2026年部分节假日休市安排的通知
劳动节：5月1日（星期五）至5月5日（星期二）休市，5月6日（星期三）起照常开市。另外，5月9日（星期六）为周末休市。
端午节：6月19日（星期五）至6月21日（星期日）休市，6月22日（星期一）起照常开市。
</body></html>
'''


def official_evidence():
    path = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'OOS_CALENDAR_OFFICIAL_EVIDENCE_V482.json'
    return json.loads(path.read_text(encoding='utf-8'))


class OosCalendarV482Tests(unittest.TestCase):
    def test_dual_exchange_schedule_builds_exact_98_day_oos_calendar(self):
        out = cal.build_oos_calendar(SSE_HTML, SZSE_HTML)
        self.assertEqual(out['status'], 'OOS_CALENDAR_READY_V482')
        self.assertTrue(out['source_agreement'])
        self.assertEqual(out['oos_date_n'], 98)
        self.assertEqual(out['first_oos_trade_date'], '2026-04-20')
        self.assertEqual(out['last_oos_trade_date'], '2026-09-08')
        self.assertEqual(out['weekday_holiday_closures'], [
            '2026-05-01', '2026-05-04', '2026-05-05', '2026-06-19'
        ])
        self.assertEqual(
            out['oos_calendar_sha256'],
            '897a76ff4a857c9712f98877491f03e975f0ee591025cfa543e1a618b240b992',
        )

    def test_exchange_disagreement_fails_closed(self):
        bad_szse = SZSE_HTML.replace('6月19日', '6月18日')
        with self.assertRaises(ValueError):
            cal.build_oos_calendar(SSE_HTML, bad_szse)

    def test_missing_official_schedule_marker_fails_closed(self):
        with self.assertRaises(ValueError):
            cal.build_oos_calendar('<html>劳动节</html>', SZSE_HTML)

    def test_materialized_official_evidence_builds_same_calendar(self):
        evidence = official_evidence()
        out = cal.build_oos_calendar_from_evidence(evidence)
        self.assertEqual(out['status'], 'OOS_CALENDAR_READY_V482')
        self.assertEqual(out['oos_date_n'], 98)
        self.assertEqual(out['oos_calendar_sha256'], cal.OOS_CALENDAR_SHA256)
        self.assertEqual(
            out['official_evidence_sha256'],
            '082ce4579a5d526faaa01249babef41dccd79caee6f35a2fa383ea62a6ef2f87',
        )
        self.assertEqual([s['exchange'] for s in out['official_sources']], ['SSE', 'SZSE'])
        self.assertTrue(all(len(s['evidence_sha256']) == 64 for s in out['official_sources']))

    def test_materialized_evidence_exchange_disagreement_fails_closed(self):
        evidence = official_evidence()
        evidence['sources'][1]['dragon_boat']['closed_start'] = '2026-06-18'
        with self.assertRaises(ValueError):
            cal.build_oos_calendar_from_evidence(evidence)

    def test_materialized_evidence_schema_is_strict(self):
        evidence = official_evidence()
        evidence['sources'][0]['unexpected'] = True
        with self.assertRaises(ValueError):
            cal.build_oos_calendar_from_evidence(evidence)

    def test_extended_calendar_binds_formal_and_oos_hashes(self):
        formal_dates = ['2020-06-01', '2020-06-02', '2026-04-17']
        oos = cal.build_oos_calendar(SSE_HTML, SZSE_HTML)
        out = cal.bind_extended_calendar(formal_dates, oos['dates'])
        self.assertEqual(out['formal_date_n'], 3)
        self.assertEqual(out['oos_date_n'], 98)
        self.assertEqual(out['total_date_n'], 101)
        self.assertEqual(out['first_date'], '2020-06-01')
        self.assertEqual(out['last_date'], '2026-09-08')
        self.assertEqual(
            out['calendar_sha256'],
            hashlib.sha256(('\n'.join(formal_dates + oos['dates'])).encode('ascii')).hexdigest(),
        )

    def test_recovery_checkpoint_accepts_valid_oos_calendar_binding(self):
        checkpoint = {
            'artifact': 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
            'version': 'V4.82',
            'status': 'MODEL_ASSETS_INCOMPLETE_V482',
            'formal_artifact_sha256': '1' * 64,
            'universe_sha256': '2' * 64,
            'formal_calendar_sha256': cal.FORMAL_CALENDAR_SHA256,
            'liquidity_threshold_cny': 80_000_000,
            'formal_end': '2026-04-17',
            'recoverable': {
                'formal_artifact': True,
                'universe': True,
                'formal_calendar': True,
                'liquidity_rule': True,
            },
            'strategy_assets': {
                'strategy_code_sha256': None,
                'parameter_sha256': None,
                'factor_definition_sha256': None,
            },
            'evidence': {'formal_calendar': {'sha256': cal.FORMAL_CALENDAR_SHA256}},
            'blockers': [
                'FACTOR_DEFINITION_MISSING',
                'OOS_CALENDAR_COVERAGE_MISSING',
                'PARAMETER_SET_MISSING',
                'STRATEGY_CODE_MISSING',
            ],
            'model_freeze_allowed': False,
        }
        manifest = cal.build_oos_calendar_from_evidence(official_evidence())
        manifest.update({
            'formal_calendar_sha256': cal.FORMAL_CALENDAR_SHA256,
            'formal_date_n': 1426,
            'total_date_n': 1524,
            'calendar_sha256': cal.FULL_CALENDAR_SHA256,
        })
        out = cal.bind_oos_calendar_checkpoint(checkpoint, manifest)
        self.assertNotIn('OOS_CALENDAR_COVERAGE_MISSING', out['blockers'])
        self.assertEqual(set(out['blockers']), {
            'FACTOR_DEFINITION_MISSING', 'PARAMETER_SET_MISSING', 'STRATEGY_CODE_MISSING'
        })
        self.assertEqual(out['calendar_sha256'], cal.FULL_CALENDAR_SHA256)
        self.assertEqual(out['oos_calendar_sha256'], cal.OOS_CALENDAR_SHA256)
        self.assertFalse(out['model_freeze_allowed'])

    def test_bad_formal_hash_binding_is_rejected(self):
        checkpoint = {
            'artifact': 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
            'version': 'V4.82',
            'formal_calendar_sha256': cal.FORMAL_CALENDAR_SHA256,
            'blockers': ['OOS_CALENDAR_COVERAGE_MISSING'],
            'model_freeze_allowed': False,
            'strategy_assets': {}, 'evidence': {},
        }
        manifest = cal.build_oos_calendar_from_evidence(official_evidence())
        manifest.update({
            'formal_calendar_sha256': '0' * 64,
            'formal_date_n': 1426,
            'total_date_n': 1524,
            'calendar_sha256': cal.FULL_CALENDAR_SHA256,
        })
        with self.assertRaises(ValueError):
            cal.bind_oos_calendar_checkpoint(checkpoint, manifest)


if __name__ == '__main__':
    unittest.main()
