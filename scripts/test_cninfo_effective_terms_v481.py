import unittest

from cninfo_effective_terms_v481 import extract_effective_terms


class CninfoEffectiveTermParserTests(unittest.TestCase):
    def test_extracts_explicit_per_share_cash_for_ex_dividend_price(self):
        text='计算除权除息价格时，每股现金红利应以0.6962456元/股计算。'
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.6962456)
        self.assertIsNone(x['cap_ratio'])
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_EFFECTIVE_CASH_PER_SHARE')

    def test_extracts_total_share_folded_cash_ratio(self):
        text='按公司总股本折算每股现金分红比例=471,547,972.68元/696,016,545股=0.6774953元/股。'
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.6774953)

    def test_extracts_virtual_cash_and_cap_ratio_from_formula_parameters(self):
        text=('D为每股派发现金红利0.44957元/股（上述每股现金股利D为虚拟分派的现金红利），'
              'n为每股转增股本0.29971股（上述每股分派的送转比例n为虚拟流通股份变动比例）。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.44957)
        self.assertAlmostEqual(x['cap_ratio'],0.29971)
        self.assertEqual(x['cap_evidence_kind'],'EXPLICIT_VIRTUAL_CAP_RATIO')

    def test_nominal_ten_share_plan_is_not_promoted_as_effective_term(self):
        x=extract_effective_terms('向全体股东每10股派发现金红利8元，每10股转增3股。')
        self.assertIsNone(x['cash_per_share'])
        self.assertIsNone(x['cap_ratio'])

    def test_conflicting_explicit_cash_values_fail_closed(self):
        text=('每股现金红利应以0.6962456元/股计算。'
              '按公司总股本折算每股现金分红比例=0.7000000元/股。')
        with self.assertRaises(ValueError):
            extract_effective_terms(text)

    def test_extracts_final_exright_cash_subtraction_from_long_formula(self):
        text=(
            '因回购专户股份不参与分红，本次权益分派实施后除权除息价格按照上述原则及计算方式执行。'
            '本次利润分配实施后的除权除息价格=前收盘价-按公司总股本折算每股现金分红比例='
            '股权登记日收盘价-2.3337380元。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],2.3337380)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_FINAL_EXRIGHT_CASH_SUBTRACTION')

    def test_extracts_total_share_cash_calculation_without_word_ratio(self):
        text=(
            '按股权登记日的总股本折算每股现金红利=实际现金分红总金额÷股权登记日的总股本='
            '273,108,941.30÷1,076,419,000=0.2537199元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.2537199)

    def test_extracts_a_share_folded_per10_cash(self):
        text='按A股除权前总股本（含回购股份及其他不参与分红的股份）计算的每10股派息（含税）：2.941285元。'
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.2941285)

    def test_complex_divisor_formula_does_not_promote_cash_without_cap_ratio(self):
        text=(
            '本次权益分派实施后的除权除息参考价格='
            '（除权除息前一交易日收盘价-按公司总股本折算每股现金分红金额）/'
            '（1+按公司总股本折算每股资本公积转增股本比例）='
            '（股权登记日收盘价-0.0988848元/股）/（1+0.40）。'
        )
        x=extract_effective_terms(text)
        self.assertIsNone(x['cash_per_share'])
        self.assertIsNone(x['cap_ratio'])


if __name__=='__main__':
    unittest.main()
