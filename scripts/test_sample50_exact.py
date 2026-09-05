import unittest

from sample50_official_refinements import refine_actions
from sample50_validate import Action


class OfficialRefinementTests(unittest.TestCase):
    def test_002001_scales_cash_and_cap_and_adds_special_dividend(self):
        actions = [
            Action(
                '002001.SZ',
                '2022-05-25',
                cash_per_share=0.7,
                cap_ratio=0.2,
                source='nominal',
            )
        ]
        out = refine_actions('002001.SZ', actions)
        by_date = {a.ex_date: a for a in out}
        eligible_ratio = 2_562_562_984 / 2_578_394_760
        self.assertAlmostEqual(
            by_date['2022-05-25'].cash_per_share,
            0.7 * eligible_ratio,
            places=12,
        )
        self.assertAlmostEqual(
            by_date['2022-05-25'].cap_ratio,
            0.2 * eligible_ratio,
            places=12,
        )
        self.assertAlmostEqual(by_date['2025-01-22'].cash_per_share, 0.2, places=12)

    def test_300827_uses_virtual_cash_and_capitalization(self):
        actions = [
            Action(
                '300827.SZ',
                '2025-07-04',
                cash_per_share=0.12,
                cap_ratio=0.4,
                source='nominal',
            )
        ]
        out = refine_actions('300827.SZ', actions)
        action = {a.ex_date: a for a in out}['2025-07-04']
        self.assertAlmostEqual(action.cash_per_share, 0.1190897, places=12)
        self.assertAlmostEqual(action.cap_ratio, 0.3969656, places=12)

    def test_unaffected_event_is_unchanged(self):
        action = Action('002236.SZ', '2021-05-12', cash_per_share=0.268, source='nominal')
        out = refine_actions('002236.SZ', [action])
        self.assertEqual(out[0], action)


if __name__ == '__main__':
    unittest.main()
