import unittest

import gp12_share_known_at_v1 as mod


FORMAL_END = '2026-04-17'


def share_row(record_date='2024-12-31', shares=29352178302.0):
    return {
        'symbol': '600000.SH',
        'record_date': record_date,
        'outstanding_share_shares': shares,
    }


def structure_row(
    change_date='2024-12-31',
    announcement_date='2025-01-04',
    display='2935217.83',
    scale=2,
):
    return {
        'symbol': '600000.SH',
        'change_date': change_date,
        'announcement_date': announcement_date,
        'change_reason': '债转股',
        'circulating_a_10k_display': display,
        'circulating_a_display_scale': scale,
    }


class ShareKnownAtV1Tests(unittest.TestCase):
    def test_late_announcement_delays_state_availability(self):
        result = mod.bind_known_at_states(
            '600000.SH',
            [share_row()],
            [structure_row()],
            'a' * 64,
            'b' * 64,
        )
        self.assertEqual(result['blockers'], [])
        self.assertEqual(len(result['states']), 1)
        state = result['states'][0]
        self.assertEqual(state['known_at'], '2025-01-04')
        self.assertIsNone(mod.resolve_known_at_state(result['states'], '2025-01-03'))
        resolved = mod.resolve_known_at_state(result['states'], '2025-01-04')
        self.assertEqual(resolved['change_date'], '2024-12-31')
        self.assertEqual(resolved['announcement_date'], '2025-01-04')

    def test_announcement_before_change_uses_change_date_as_known_at(self):
        result = mod.bind_known_at_states(
            '600000.SH',
            [share_row('2025-06-01', 1104320470.0)],
            [structure_row('2025-06-01', '2025-05-29', '110432.047', 3)],
            'a' * 64,
            'b' * 64,
        )
        self.assertEqual(result['blockers'], [])
        self.assertEqual(result['states'][0]['known_at'], '2025-06-01')

    def test_decimal_display_precision_match_is_deterministic(self):
        result = mod.bind_known_at_states(
            '600000.SH',
            [share_row(shares=29352178302.0)],
            [structure_row(display='2935217.83', scale=2)],
            'a' * 64,
            'b' * 64,
        )
        self.assertEqual(result['blockers'], [])
        self.assertEqual(result['states'][0]['outstanding_share_shares'], 29352178302.0)

    def test_amount_mismatch_blocks_same_date(self):
        result = mod.bind_known_at_states(
            '600000.SH',
            [share_row()],
            [structure_row(display='2935217.82', scale=2)],
            'a' * 64,
            'b' * 64,
        )
        self.assertEqual(result['states'], [])
        self.assertIn('SINA_STOCK_STRUCTURE_AMOUNT_MISMATCH', result['blockers'])

    def test_missing_same_date_structure_row_blocks(self):
        result = mod.bind_known_at_states(
            '600000.SH',
            [share_row()],
            [structure_row(change_date='2024-09-30')],
            'a' * 64,
            'b' * 64,
        )
        self.assertEqual(result['states'], [])
        self.assertIn('SINA_STOCK_STRUCTURE_MATCH_MISSING', result['blockers'])

    def test_multiple_matching_rows_are_ambiguous(self):
        rows = [
            structure_row(announcement_date='2025-01-04'),
            structure_row(announcement_date='2025-01-05'),
        ]
        result = mod.bind_known_at_states(
            '600000.SH',
            [share_row()],
            rows,
            'a' * 64,
            'b' * 64,
        )
        self.assertEqual(result['states'], [])
        self.assertIn('SINA_STOCK_STRUCTURE_MATCH_AMBIGUOUS', result['blockers'])

    def test_postformal_share_rows_are_excluded_from_states(self):
        result = mod.bind_known_at_states(
            '600000.SH',
            [
                share_row('2025-12-31', 29352178302.0),
                share_row('2026-05-01', 30000000000.0),
            ],
            [
                structure_row('2025-12-31', '2026-01-04', '2935217.83', 2),
                structure_row('2026-05-01', '2026-05-02', '3000000', 0),
            ],
            'a' * 64,
            'b' * 64,
            formal_end=FORMAL_END,
        )
        self.assertEqual(result['blockers'], [])
        self.assertEqual([s['change_date'] for s in result['states']], ['2025-12-31'])
        self.assertEqual(result['post_formal_share_row_n'], 1)

    def test_invalid_raw_sha_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'sha256'):
            mod.bind_known_at_states(
                '600000.SH',
                [share_row()],
                [structure_row()],
                'not-a-sha',
                'b' * 64,
            )

    def test_resolver_never_uses_future_known_at(self):
        states = [
            {
                'symbol': '600000.SH',
                'change_date': '2024-12-31',
                'announcement_date': '2025-01-04',
                'known_at': '2025-01-04',
                'outstanding_share_shares': 29352178302.0,
                'share_amount_raw_sha256': 'a' * 64,
                'stock_structure_raw_sha256': 'b' * 64,
            },
            {
                'symbol': '600000.SH',
                'change_date': '2025-03-31',
                'announcement_date': '2025-04-03',
                'known_at': '2025-04-03',
                'outstanding_share_shares': 29352178996.0,
                'share_amount_raw_sha256': 'c' * 64,
                'stock_structure_raw_sha256': 'd' * 64,
            },
        ]
        resolved = mod.resolve_known_at_state(states, '2025-04-02')
        self.assertEqual(resolved['change_date'], '2024-12-31')


if __name__ == '__main__':
    unittest.main()
