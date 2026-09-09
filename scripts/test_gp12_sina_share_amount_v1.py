import hashlib
import unittest
from unittest import mock

import gp12_sina_share_amount_v1 as mod


UNIVERSE_SHA = 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb'


def valid_raw():
    return b'var KKE_ShareAmount_sh600000=[["2020-01-01","123.45"],["2021-01-01","150"]];'


def valid_symbol_evidence():
    return mod.build_symbol_evidence('600000.SH', valid_raw(), '2026-09-09T08:00:00Z', 200)


def valid_date_semantics():
    return {
        'source': 'SINA_STOCK_STRUCTURE_HISTORY',
        'evidence_type': 'EFFECTIVE_HISTORICAL_SHARE_STATE',
        'verified': True,
        'source_identity': 'sina-stock-structure-history-v1',
    }


class SinaShareAmountV1Tests(unittest.TestCase):
    def test_normalize_and_sina_symbol(self):
        self.assertEqual(mod.normalize_symbol('600000.sh'), '600000.SH')
        self.assertEqual(mod.to_sina_symbol('600000.SH'), 'sh600000')
        self.assertEqual(mod.to_sina_symbol('000001.SZ'), 'sz000001')
        with self.assertRaises(ValueError):
            mod.normalize_symbol('600000')
        with self.assertRaises(ValueError):
            mod.normalize_symbol('600000.HK')

    def test_parse_valid_jsonp_multiplies_10000_share_units(self):
        rows = mod.parse_share_amount_bytes('600000.SH', valid_raw())
        self.assertEqual(rows[0]['record_date'], '2020-01-01')
        self.assertEqual(rows[0]['outstanding_share_shares'], 1_234_500.0)
        self.assertEqual(rows[1]['outstanding_share_shares'], 1_500_000.0)

    def test_parser_accepts_postformal_source_records_but_formal_evidence_filters_them(self):
        raw = b'var KKE_ShareAmount_sh600000=[["2020-01-01","100"],["2026-05-01","200"]];'
        rows = mod.parse_share_amount_bytes('600000.SH', raw)
        self.assertEqual([r['record_date'] for r in rows], ['2020-01-01', '2026-05-01'])
        ev = mod.build_symbol_evidence('600000.SH', raw, '2026-09-09T08:00:00Z', 200)
        self.assertEqual(ev['normalized_record_count'], 1)
        self.assertEqual(ev['post_formal_record_n'], 1)
        self.assertEqual(ev['record_start'], '2020-01-01')
        self.assertEqual(ev['record_end'], '2020-01-01')
        self.assertTrue(all(r['record_date'] <= '2026-04-17' for r in ev['records']))

    def test_parser_rejects_empty_malformed_nonpositive_and_duplicate_dates(self):
        payloads = [
            b'',
            b'not jsonp',
            b'var KKE_ShareAmount_sh600000=[["2020-01-01","0"]];',
            b'var KKE_ShareAmount_sh600000=[["2020-01-01","1"],["2020-01-01","2"]];',
        ]
        for raw in payloads:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    mod.parse_share_amount_bytes('600000.SH', raw)

    def test_resolver_uses_latest_record_not_after_trade_date(self):
        records = [
            {'record_date': '2020-01-01', 'outstanding_share_shares': 100.0},
            {'record_date': '2020-03-01', 'outstanding_share_shares': 200.0},
        ]
        resolved = mod.resolve_share_state(records, '2020-02-15')
        self.assertEqual(resolved['record_date'], '2020-01-01')
        self.assertEqual(resolved['outstanding_share_shares'], 100.0)

    def test_future_record_is_never_backfilled(self):
        records = [{'record_date': '2020-03-01', 'outstanding_share_shares': 200.0}]
        self.assertIsNone(mod.resolve_share_state(records, '2020-02-15'))

    def test_symbol_evidence_binds_raw_sha_and_endpoint_family(self):
        ev = valid_symbol_evidence()
        self.assertEqual(ev['symbol'], '600000.SH')
        self.assertEqual(ev['sina_symbol'], 'sh600000')
        self.assertEqual(ev['raw_sha256'], hashlib.sha256(valid_raw()).hexdigest())
        self.assertEqual(ev['source_endpoint_family'], 'SINA_STOCKSERVICE_SHARE_AMOUNT')
        self.assertEqual(ev['http_status'], 200)
        self.assertEqual(ev['normalized_record_count'], 2)
        self.assertEqual(ev['post_formal_record_n'], 0)

    def test_manifest_without_date_semantics_stays_blocked(self):
        manifest = mod.build_share_manifest([valid_symbol_evidence()], UNIVERSE_SHA, None)
        self.assertEqual(manifest['artifact'], 'SINA_SHARE_AMOUNT_MANIFEST_GP12_V1')
        self.assertIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', manifest['blockers'])
        self.assertFalse(manifest['model_freeze_allowed'])
        self.assertFalse(manifest['oos_metrics_allowed'])
        self.assertFalse(manifest['formal_admission'])

    def test_exact_date_semantics_schema_can_clear_semantics_blocker(self):
        manifest = mod.build_share_manifest(
            [valid_symbol_evidence()], UNIVERSE_SHA, valid_date_semantics())
        self.assertNotIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', manifest['blockers'])
        self.assertEqual(manifest['share_date_semantics_evidence'], valid_date_semantics())

    def test_extra_date_semantics_field_is_not_accepted(self):
        evidence = valid_date_semantics()
        evidence['note'] = 'extra field must not broaden contract'
        manifest = mod.build_share_manifest([valid_symbol_evidence()], UNIVERSE_SHA, evidence)
        self.assertIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', manifest['blockers'])

    def test_missing_or_false_date_semantics_is_not_accepted(self):
        missing = valid_date_semantics()
        del missing['source_identity']
        false_value = valid_date_semantics()
        false_value['verified'] = False
        for evidence in (missing, false_value):
            with self.subTest(evidence=evidence):
                manifest = mod.build_share_manifest([valid_symbol_evidence()], UNIVERSE_SHA, evidence)
                self.assertIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', manifest['blockers'])

    def test_generic_akshare_behavior_is_not_pit_evidence(self):
        evidence = {
            'source': 'AKSHARE_FORWARD_FILL',
            'evidence_type': 'IMPLEMENTATION_BEHAVIOR',
            'verified': True,
            'source_identity': 'akshare-stock-zh-a-daily',
        }
        manifest = mod.build_share_manifest([valid_symbol_evidence()], UNIVERSE_SHA, evidence)
        self.assertIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', manifest['blockers'])

    def test_manifest_rejects_wrong_universe_hash(self):
        with self.assertRaises(ValueError):
            mod.build_share_manifest([valid_symbol_evidence()], '0' * 64, None)

    def test_fetch_network_failure_is_normalized(self):
        session = mock.Mock()
        session.get.side_effect = OSError('network down')
        raw, meta = mod.fetch_share_amount(session, '600000.SH', timeout=1, retries=1)
        self.assertIsNone(raw)
        self.assertEqual(meta['status'], 'BLOCKED')
        self.assertIn('SINA_SHARE_SOURCE_UNAVAILABLE', meta['blockers'])
        self.assertEqual(meta['symbol'], '600000.SH')

    def test_fetch_success_returns_exact_bytes_and_metadata(self):
        response = mock.Mock()
        response.status_code = 200
        response.content = valid_raw()
        response.raise_for_status.return_value = None
        session = mock.Mock()
        session.get.return_value = response
        raw, meta = mod.fetch_share_amount(session, '600000.SH', timeout=1, retries=1)
        self.assertEqual(raw, valid_raw())
        self.assertEqual(meta['status'], 'FETCHED')
        self.assertEqual(meta['http_status'], 200)
        self.assertEqual(meta['raw_sha256'], hashlib.sha256(valid_raw()).hexdigest())
        self.assertEqual(meta['blockers'], [])


if __name__ == '__main__':
    unittest.main()
