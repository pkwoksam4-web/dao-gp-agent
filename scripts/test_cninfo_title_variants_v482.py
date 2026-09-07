import unittest

from cninfo_exact_term_v481 import (
    choose_implementation_announcement,
    is_distribution_implementation_title,
)


class CninfoRemainingTitleVariantsV482Tests(unittest.TestCase):
    def test_accepts_annual_dividend_implementation_title(self):
        self.assertTrue(
            is_distribution_implementation_title('2023年度分红<em>实施</em><em>公告</em>')
        )

    def test_accepts_capital_reserve_transfer_implementation_title(self):
        self.assertTrue(
            is_distribution_implementation_title('2024年度资本公积金转增股本<em>实施</em><em>公告</em>')
        )

    def test_accepts_interim_cash_dividend_implementation_title(self):
        self.assertTrue(
            is_distribution_implementation_title('2025年中期现金分红的<em>实施</em><em>公告</em>')
        )

    def test_rejects_buyback_implementation_result_interference(self):
        self.assertFalse(
            is_distribution_implementation_title('关于回购股份<em>实施</em>结果暨股份变动的<em>公告</em>')
        )

    def test_selector_prefers_capital_reserve_transfer_over_buyback_result(self):
        items = [
            {
                'announcementTitle': '2024年度资本公积金转增股本<em>实施</em><em>公告</em>',
                'announcementTime': 1755187200000,
                'adjunctUrl': 'distribution.pdf',
            },
            {
                'announcementTitle': '关于回购股份<em>实施</em>结果暨股份变动的<em>公告</em>',
                'announcementTime': 1753113600000,
                'adjunctUrl': 'buyback.pdf',
            },
        ]
        picked = choose_implementation_announcement(items, '2025-08-21')
        self.assertIsNotNone(picked)
        self.assertEqual(picked['adjunctUrl'], 'distribution.pdf')


if __name__ == '__main__':
    unittest.main()
