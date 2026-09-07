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

    def test_extracts_final_exright_cash_when_announcement_says_closing_price(self):
        text=(
            '因本次分红存在差异化安排，本次权益分派实施后的除权除息参考价格按照以下公式计算。'
            '公司除权（息）参考价格=（股权登记日收盘价格-0.2961638）元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.2961638)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_FINAL_EXRIGHT_CASH_SUBTRACTION')

    def test_extracts_total_share_cash_calculation_without_word_ratio(self):
        text=(
            '按股权登记日的总股本折算每股现金红利=实际现金分红总金额÷股权登记日的总股本='
            '273,108,941.30÷1,076,419,000=0.2537199元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.2537199)

    def test_extracts_folded_per_share_cash_from_explicit_formula(self):
        text=(
            '因公司回购股份不参与利润分配，本次权益分派实施后需要计算除权除息参考价格。'
            '折算每股现金红利=实际现金分红总额÷股权登记日的总股本='
            '369,000,000÷1,176,862,492=0.3135332元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.3135332)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_FOLDED_CASH_PER_SHARE_V482')

    def test_extracts_a_share_folded_per10_cash(self):
        text='按A股除权前总股本（含回购股份及其他不参与分红的股份）计算的每10股派息（含税）：2.941285元。'
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.2941285)

    def test_extracts_a_share_specific_effective_cash_formula(self):
        text=(
            '本公告为A股权益分派实施公告。A股除权除息价格计算时，'
            '每股现金红利=现金分红总额/总股本，即0.097115元/股。'
            'B股现金红利折算结果另行计算。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.097115)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_A_SHARE_EFFECTIVE_CASH_V482')

    def test_extracts_virtual_differential_cash_from_computed_formula(self):
        text=(
            '本次利润分配采用差异化分红，除权除息参考价格按虚拟分派计算。'
            '虚拟分派的每股现金红利=本次实际参与分配的股本数×实际分派的每股现金红利÷'
            '本次利润分配股权登记日的总股本=0.1109元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.1109)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_DIFFERENTIAL_FOLDED_CASH_V482')

    def test_extracts_folded_per10_cash_from_differential_formula(self):
        text=(
            '因公司回购股份不参与本次权益分派，本次除权除息参考价按差异化分红规则计算。'
            '折算后的每10股现金股利=实际参与分配股份数×每10股现金股利÷总股本=2.454060元，'
            '所以每股现金红利为0.245406元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.245406)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_FOLDED_CASH_PER10_V482')

    def test_symbolic_complex_divisor_does_not_promote_partial_cash(self):
        text=(
            '本次权益分派实施后的除权除息参考价格='
            '（除权除息前一交易日收盘价-按公司总股本折算每股现金分红金额）/'
            '（1+按公司总股本折算每股资本公积转增股本比例）。'
        )
        x=extract_effective_terms(text)
        self.assertIsNone(x['cash_per_share'])
        self.assertIsNone(x['cap_ratio'])

    def test_extracts_complete_numeric_cash_and_cap_exright_formula(self):
        text=(
            '本次权益分派实施后的除权除息参考价格='
            '（除权除息前一交易日收盘价-按总股本折算每股现金分红金额）/'
            '（1+按公司总股本折算每股资本公积转增股本股数）='
            '（股权登记日收盘价-0.0988848元/股）/（1+0.3955395）。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.0988848)
        self.assertAlmostEqual(x['cap_ratio'],0.3955395)
        self.assertEqual(x['cash_evidence_kind'],'EXPLICIT_COUPLED_EXRIGHT_FORMULA_CASH_V482')
        self.assertEqual(x['cap_evidence_kind'],'EXPLICIT_COUPLED_EXRIGHT_FORMULA_CAP_V482')

    def test_extracts_cap_only_numeric_exright_denominator(self):
        text=(
            '本次权益分派实施后的每股除权除息参考价格='
            '股权登记日股票收盘价÷（1+0.2941856）。'
        )
        x=extract_effective_terms(text)
        self.assertIsNone(x['cash_per_share'])
        self.assertAlmostEqual(x['cap_ratio'],0.2941856)

    def test_extracts_explicit_effective_per_share_cap_ratio(self):
        text=(
            '考虑到回购专户不参与权益分派，本次权益分派实施后除权价格计算时，'
            '每股转增股本比例应以0.096600计算（每股转增股本数=实际转增股本数/总股本）。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cap_ratio'],0.096600)

    def test_extracts_parenthetical_folded_cash_in_exright_formula(self):
        text=(
            '本次权益分派实施后的除权除息价格按照上述原则及计算方式执行，'
            '即本次权益分派实施后的除权除息价格=权益分派股权登记日收盘价-'
            '按公司总股本折算的每股现金红利（0.1117002元/股）。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.1117002)

    def test_derives_a_share_effective_cash_when_repurchase_shares_do_not_participate(self):
        text=(
            '本公告为A股权益分派实施公告。公司总股本未发生变化，为8,677,992,236股；'
            '回购股份不参与本次权益分派；公司实施本次分配方案的总股份数为8,254,035,470股，'
            '其中A股6,672,070,922股、H股1,581,964,548股；'
            '每10股派发现金红利人民币3.2元（含税）。'
        )
        x=extract_effective_terms(text)
        expected=(3.2/10.0)*6672070922/(8677992236-1581964548)
        self.assertAlmostEqual(x['cash_per_share'],expected,places=12)
        self.assertEqual(x['cash_evidence_kind'],'DERIVED_A_SHARE_FOLDED_CASH_FROM_REPURCHASE_V482')


if __name__=='__main__':
    unittest.main()
