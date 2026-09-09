import csv
import io
import math
import unittest

import gp12_turnover_formal_v1 as mod


def synthetic_manifest(blockers=None):
    return {
        'artifact': 'SINA_SHARE_AMOUNT_MANIFEST_GP12_V1',
        'version': '1.0',
        'formal_end': '2026-04-17',
        'universe_sha256': 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb',
        'symbol_n': 1,
        'symbols_fetched': 1,
        'symbols_failed': 0,
        'raw_response_count': 1,
        'normalized_record_count': 1,
        'parser_version': '1.0',
        'source_endpoint_family': 'SINA_STOCKSERVICE_SHARE_AMOUNT',
        'share_date_semantics_evidence': {
            'source': 'SINA_STOCK_STRUCTURE_HISTORY',
            'evidence_type': 'EFFECTIVE_HISTORICAL_SHARE_STATE',
            'verified': True,
            'source_identity': 'synthetic-test',
        },
        'symbol_evidence': [],
        'blockers': list(blockers or []),
        'formal_admission': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def one_raw(date='2020-06-01', volume=1_000_000.0):
    return [{'symbol': '600000.SH', 'date': date, 'volume': volume}]


def shares(
    record_date='2020-01-01',
    outstanding=100_000_000.0,
    announcement_date=None,
):
    announcement_date = announcement_date or record_date
    known_at = max(record_date, announcement_date)
    return {
        '600000.SH': [{
            # Kept only so the pre-Amendment-2 implementation can execute in RED.
            # GREEN must ignore this field and consume the known-at state fields below.
            'record_date': record_date,
            'change_date': record_date,
            'announcement_date': announcement_date,
            'known_at': known_at,
            'outstanding_share_shares': outstanding,
            'share_raw_sha256': 'a' * 64,
            'share_amount_raw_sha256': 'a' * 64,
            'stock_structure_raw_sha256': 'b' * 64,
        }]
    }


class TurnoverFormalV1Tests(unittest.TestCase):
    def test_exact_ratio_uses_raw_volume_shares(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(),
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows[0]['turnover_ratio'], 0.01)
        self.assertEqual(rows[0]['volume_shares'], 1_000_000.0)
        self.assertEqual(rows[0]['outstanding_share_shares'], 100_000_000.0)
        self.assertEqual(summary['nonfinite_turnover_n'], 0)

    def test_late_announcement_state_is_not_used_before_known_at(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(date='2025-01-03'),
            share_records_by_symbol=shares(
                record_date='2024-12-31',
                outstanding=29_352_178_302.0,
                announcement_date='2025-01-04',
            ),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows, [])
        self.assertIn('TURNOVER_PRIOR_SHARE_RECORD_MISSING', summary['blockers'])
        self.assertEqual(summary['unresolved_prior_share_record_n'], 1)

    def test_state_is_usable_on_known_at_and_carries_dual_source_provenance(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(date='2025-01-04'),
            share_records_by_symbol=shares(
                record_date='2024-12-31',
                outstanding=29_352_178_302.0,
                announcement_date='2025-01-04',
            ),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['share_change_date'], '2024-12-31')
        self.assertEqual(row['share_announcement_date'], '2025-01-04')
        self.assertEqual(row['share_known_at'], '2025-01-04')
        self.assertEqual(row['share_amount_raw_sha256'], 'a' * 64)
        self.assertEqual(row['stock_structure_raw_sha256'], 'b' * 64)
        self.assertNotIn('share_record_date', row)
        self.assertEqual(summary['status'], 'PASS_FORMAL_TURNOVER_V1')

    def test_future_share_record_never_materializes_prior_trade_row(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(),
            share_records_by_symbol=shares(record_date='2020-07-01'),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows, [])
        self.assertIn('TURNOVER_PRIOR_SHARE_RECORD_MISSING', summary['blockers'])
        self.assertEqual(summary['unresolved_prior_share_record_n'], 1)

    def test_missing_share_records_create_rowset_mismatch(self):
        raw = one_raw() + [{'symbol': '600000.SH', 'date': '2020-06-02', 'volume': 2_000_000.0}]
        rows, summary = mod.materialize_turnover(
            raw_rows=raw,
            share_records_by_symbol={},
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows, [])
        self.assertIn('TURNOVER_ROWSET_MISMATCH', summary['blockers'])
        self.assertEqual(summary['missing_turnover_row_n'], 2)

    def test_pit_unverified_cannot_pass_even_with_complete_rows(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(),
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=False,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(summary['status'], 'BLOCKED_FORMAL_TURNOVER_V1')
        self.assertEqual(summary['pit_state'], 'PIT_UNVERIFIED')
        self.assertIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', summary['blockers'])
        self.assertFalse(summary['formal_feature_ready'])

    def test_full_synthetic_pass(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(),
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(summary['status'], 'PASS_FORMAL_TURNOVER_V1')
        self.assertEqual(summary['pit_state'], 'PIT_VERIFIED')
        self.assertTrue(summary['formal_feature_ready'])
        self.assertFalse(summary['candidate_freeze_ready'])
        self.assertFalse(summary['model_freeze_allowed'])
        self.assertFalse(summary['oos_metrics_allowed'])

    def test_duplicate_raw_key_blocks(self):
        raw = one_raw() + one_raw()
        rows, summary = mod.materialize_turnover(
            raw_rows=raw,
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertIn('TURNOVER_DUPLICATE_ROW', summary['blockers'])
        self.assertGreater(summary['duplicate_row_n'], 0)
        self.assertEqual(summary['status'], 'BLOCKED_FORMAL_TURNOVER_V1')

    def test_nonpositive_volume_blocks(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(volume=0.0),
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows, [])
        self.assertEqual(summary['nonpositive_volume_n'], 1)
        self.assertEqual(summary['status'], 'BLOCKED_FORMAL_TURNOVER_V1')

    def test_nonpositive_outstanding_share_blocks(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(),
            share_records_by_symbol=shares(outstanding=0.0),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows, [])
        self.assertEqual(summary['nonpositive_outstanding_share_n'], 1)
        self.assertEqual(summary['status'], 'BLOCKED_FORMAL_TURNOVER_V1')

    def test_nonfinite_volume_blocks(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(volume=math.inf),
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows, [])
        self.assertEqual(summary['nonfinite_turnover_n'], 1)
        self.assertEqual(summary['status'], 'BLOCKED_FORMAL_TURNOVER_V1')

    def test_postformal_trade_date_is_rejected(self):
        with self.assertRaises(ValueError):
            mod.materialize_turnover(
                raw_rows=one_raw(date='2026-04-18'),
                share_records_by_symbol=shares(),
                universe=['600000.SH'],
                share_manifest=synthetic_manifest(),
                share_date_semantics_verified=True,
            )

    def test_canonical_csv_is_deterministic_and_lf_terminated(self):
        rows, _ = mod.materialize_turnover(
            raw_rows=[
                {'symbol': '600000.SH', 'date': '2020-06-02', 'volume': 2_000_000.0},
                {'symbol': '600000.SH', 'date': '2020-06-01', 'volume': 1_000_000.0},
            ],
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        data = mod.canonical_turnover_csv_bytes(rows)
        self.assertTrue(data.endswith(b'\n'))
        self.assertNotIn(b'\r\n', data)
        parsed = list(csv.DictReader(io.StringIO(data.decode('utf-8'))))
        self.assertEqual([r['date'] for r in parsed], ['2020-06-01', '2020-06-02'])
        self.assertIn('share_known_at', parsed[0])
        self.assertNotIn('share_record_date', parsed[0])

    def test_summary_hash_and_row_hash_are_distinct(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=one_raw(),
            share_records_by_symbol=shares(),
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(len(summary['turnover_rows_sha256']), 64)
        self.assertEqual(len(mod.canonical_json_sha256(summary)), 64)
        self.assertNotEqual(summary['turnover_rows_sha256'], mod.canonical_json_sha256(summary))


if __name__ == '__main__':
    unittest.main()
