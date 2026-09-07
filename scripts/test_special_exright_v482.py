from __future__ import annotations

import unittest

import sample50_validate as qfq
from sample50_validate import Action


class SpecialExRightV482Tests(unittest.TestCase):
    def test_adjusted_reference_override_uses_exchange_reference_price(self):
        self.assertTrue(
            hasattr(qfq, 'event_ratio_v482'),
            'V4.82 must expose event_ratio_v482 before special ex-right cases can close',
        )
        action = Action(
            symbol='600306.SH',
            ex_date='2023-12-26',
            cap_ratio=0.85,
            source='RESTRUCTURING_SPECIAL_EXRIGHT',
        )
        ratio = qfq.event_ratio_v482(
            action,
            11.98,
            adjusted_reference_price=8.14,
        )
        self.assertAlmostEqual(ratio, 8.14 / 11.98, places=12)
        self.assertGreater(abs(ratio - qfq.event_ratio(action, 11.98)), 0.10)

    def test_nominal_path_is_identical_when_no_override_is_supplied(self):
        self.assertTrue(
            hasattr(qfq, 'event_ratio_v482'),
            'V4.82 must preserve the nominal event-ratio path',
        )
        action = Action(
            symbol='000030.SZ',
            ex_date='2025-06-30',
            cash_per_share=0.25,
            source='EASTMONEY_RPT_SHAREBONUS_DET',
        )
        self.assertAlmostEqual(
            qfq.event_ratio_v482(action, 6.50),
            qfq.event_ratio(action, 6.50),
            places=15,
        )

    def test_override_is_fail_closed_for_invalid_reference_price(self):
        self.assertTrue(hasattr(qfq, 'event_ratio_v482'))
        action = Action(symbol='000796.SZ', ex_date='2023-12-20', cap_ratio=1.0)
        with self.assertRaises(ValueError):
            qfq.event_ratio_v482(action, 4.08, adjusted_reference_price=0.0)


if __name__ == '__main__':
    unittest.main()
