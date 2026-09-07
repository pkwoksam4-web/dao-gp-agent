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

    def test_extracts_folded_cash_from_explicit_ji_value(self):
        text=('按股权登记日的总股本折算的每股现金红利=实际现金分红总金额÷股权登记日的总股本，'
              '即0.094621元/股=238803276.9元/2523777297股。'
              '除权除息价格=股权登记日收盘价-0.094621元/股。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.094621)

    def test_extracts_explicit_per_share_cash_dividend_value(self):
        text=('按公司总股本折算的最新每10股现金股利金额为3.719542元，'
              '每股现金股利为0.3719542元。因此，本次权益分派实施后的除权除息价格='
              '股权登记日收盘价-0.3719542元/股。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.3719542)

    def test_extracts_unitless_total_share_folded_cash_when_formula_is_explicit(self):
        text=('按总股本折算每股现金分红的比例=本次实际现金分红总额/公司总股本='
              '11677508761.20元/6997053441股=1.67（实际现金分红总额及按总股本折算每股现金分红的比例为四舍五入后保留小数点后两位）。'
              '除权除息价格=股权登记日收盘价-1.67。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],1.67)

    def test_extracts_cash_and_cap_from_explicit_ex_right_formula(self):
        text=('按公司总股本（含回购股份）折算每股现金红利=实际现金分红总额/除权前总股本=0.3472362元/股。'
              '按公司总股本（含回购股份）折算的每10股资本公积金转增股本数量=1.984207股。'
              '本次权益分派实施后的除权除息价格=（权益分派股权登记日收盘价-0.3472362）÷（1+19.842072%）。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.3472362)
        self.assertAlmostEqual(x['cap_ratio'],0.19842072)

    def test_extracts_price_formula_cash_and_decimal_cap_ratio(self):
        text=('按总股本计算的每10股现金分红金额为7.827273元，按总股本计算的每10股资本公积金转增股本数量为2.935227股。'
              '据此计算，年度权益分派实施后的除权除息参考价格=（股权登记日收盘价-0.7827273元/股）/（1+0.2935227）。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.7827273)
        self.assertAlmostEqual(x['cap_ratio'],0.2935227)

    def test_extracts_cap_from_explicit_ex_right_reference_formula(self):
        text=('按总股本（含回购股份）折算后的每10股转增股数=0.993994股。'
              '本次权益分派实施后的除权参考价=除权前一交易日收盘价/（1+按公司总股本折算每股资本公积金转增股本比例）='
              '除权前一交易日收盘价/（1+0.0993994）。')
        x=extract_effective_terms(text)
        self.assertIsNone(x['cash_per_share'])
        self.assertAlmostEqual(x['cap_ratio'],0.0993994)

    def test_price_formula_does_not_capture_unrelated_repurchase_limit(self):
        text=('按公司总股本折算的每股现金分红比例=分红总额/总股本，据此计算的证券除权除息参考价='
              '股权登记日收盘价-按公司总股本折算的每股现金分红比例=公司2024年11月14日收盘价-0.0476118元。'
              '每股现金分红金额应以0.0476118元/股计算。'
              '回购股份价格上限由不超过3.13元/股调整为不超过3.08元/股。')
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.0476118)
        self.assertNotAlmostEqual(x['cash_per_share'],3.13)

    def test_nominal_ten_share_plan_is_not_promoted_as_effective_term(self):
        x=extract_effective_terms('向全体股东每10股派发现金红利8元，每10股转增3股。')
        self.assertIsNone(x['cash_per_share'])
        self.assertIsNone(x['cap_ratio'])

    def test_conflicting_explicit_cash_values_fail_closed(self):
        text=('每股现金红利应以0.6962456元/股计算。'
              '按公司总股本折算每股现金分红比例=0.7000000元/股。')
        with self.assertRaises(ValueError):
            extract_effective_terms(text)


if __name__=='__main__':
    unittest.main()
