import unittest

import cninfo_effective_terms_final_v482 as mod


class FinalEffectiveTermsV482Tests(unittest.TestCase):
    def test_scales_percent_formula_share_change_ratio(self):
        text = '''
        按公司总股本（含回购股份）折算每股现金红利=0.3472362元/股。
        本次权益分派实施后的除权除息价格=（权益分派股权登记日收盘价-0.3472362）÷（1+19.842072%）。
        '''
        x = mod.extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'], 0.3472362, places=10)
        self.assertAlmostEqual(x['cap_ratio'], 0.19842072, places=10)
        self.assertAlmostEqual(x['formula_share_change_ratio'], 0.19842072, places=10)

    def test_extracts_a_share_final_cash_subtraction(self):
        text = '''
        本次权益分派实施后，按公司A、B股总股本分别折算的每股除权除息参考价计算公式如下：
        A股除权除息价格=股权登记日A股收盘价-0.7072694元/股；
        B股除权除息价格=最后交易日B股收盘价-0.78767港元/股。
        '''
        x = mod.extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'], 0.7072694, places=10)
        self.assertEqual(x['cash_evidence_kind'], 'EXPLICIT_A_SHARE_FINAL_EXRIGHT_CASH_V482')

    def test_extracts_effective_cash_per10(self):
        text = '''
        因公司回购股份不参与分红，本次权益分派实施后除权除息价格计算时，
        每10股现金红利应以3.956025元计算。本次权益分派实施后除权除息参考价=
        除权除息日前一日收盘价-按总股本折算每股现金红利。
        '''
        x = mod.extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'], 0.3956025, places=10)
        self.assertEqual(x['cash_evidence_kind'], 'EXPLICIT_EFFECTIVE_CASH_PER10_V482')

    def test_formula_share_change_ratio_is_total_not_additive_cap(self):
        text = '''
        本次权益分派实施后的除权除息参考价=（股权登记日收盘价-0.7943066）÷（1+0.1985766）。
        '''
        x = mod.extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'], 0.7943066, places=10)
        self.assertAlmostEqual(x['formula_share_change_ratio'], 0.1985766, places=10)

    def test_corrected_ratio_uses_formula_total_share_change_instead_of_double_counting_stock(self):
        event = {
            'prev_actual_close': 19.86,
            'cash_per_share_nominal': 0.8,
            'stock_ratio': 0.2,
            'capitalization_ratio': 0.0,
            'rights_ratio': 0.0,
            'rights_price': None,
        }
        terms = {
            'cash_per_share': 0.7943066,
            'cap_ratio': 0.1985766,
            'formula_share_change_ratio': 0.1985766,
        }
        ratio = mod.corrected_event_ratio(event, terms)
        self.assertAlmostEqual(ratio, 0.800953984017745, places=12)


if __name__ == '__main__':
    unittest.main()
