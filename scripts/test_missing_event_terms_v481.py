import unittest

from missing_event_terms_v481 import parse_impl_plan_profile


class MissingEventImplementationTermTests(unittest.TestCase):
    def test_cash_only(self):
        x=parse_impl_plan_profile('10派0.13元')
        self.assertAlmostEqual(x['cash_per_share'],0.013)
        self.assertAlmostEqual(x['stock_ratio'],0.0)
        self.assertAlmostEqual(x['capitalization_ratio'],0.0)

    def test_capitalization_only(self):
        x=parse_impl_plan_profile('10转12.35')
        self.assertAlmostEqual(x['capitalization_ratio'],1.235)
        self.assertAlmostEqual(x['cash_per_share'],0.0)

    def test_capitalization_and_cash(self):
        x=parse_impl_plan_profile('10转2.006395派0.331055元')
        self.assertAlmostEqual(x['capitalization_ratio'],0.2006395)
        self.assertAlmostEqual(x['cash_per_share'],0.0331055)

    def test_stock_capitalization_and_cash(self):
        x=parse_impl_plan_profile('10送1转2派0.5元')
        self.assertAlmostEqual(x['stock_ratio'],0.1)
        self.assertAlmostEqual(x['capitalization_ratio'],0.2)
        self.assertAlmostEqual(x['cash_per_share'],0.05)

    def test_rejects_non_ten_base(self):
        with self.assertRaises(ValueError):
            parse_impl_plan_profile('5派1元')

    def test_rejects_empty_or_unrecognized(self):
        for text in ('', '不分配不转增', '10配3股'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_impl_plan_profile(text)


if __name__=='__main__':
    unittest.main()
