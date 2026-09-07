from __future__ import annotations

import unittest

from cninfo_effective_terms_v481 import extract_effective_terms


class RemainingExactParserRegressionTests(unittest.TestCase):
    def test_repurchase_price_ceiling_is_not_promoted_as_effective_cash(self):
        text=(
            '本次分红派息实施后除权除息价格计算时，按股权登记日的总股本折算每股现金红利='
            '实际现金分红总额÷股权登记日的总股本=0.3135332元/股。'
            '本次分红派息实施后的除权除息价格=股权登记日收盘价-0.3135332元/股。'
            '回购股份的价格上限由20元/股调整为19.69元/股，'
            '调整后的回购股份价格上限=调整前回购股份价格上限-按公司总股本折算每股现金红利='
            '20元/股-0.3135332元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.3135332)

    def test_extracts_real_folded_per10_cash_when_value_is_after_literal_ji(self):
        text=(
            '本次权益分派实施后除权除息价格计算时，根据股票市值不变原则，以公司总股本折算后的'
            '每10股现金股利=实际派发现金股利总额÷总股本×10（即2.454060元=253,274,478.75元÷'
            '1,032,062,937股×10）。除权除息参考价=除权除息前一交易日收盘价-0.245406元/股。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.245406)
        self.assertTrue(any(
            c['kind']=='EXPLICIT_FOLDED_CASH_PER10_V482' and abs(c['value']-0.245406)<=1e-7
            for c in x['cash_candidates']
        ))

    def test_extracts_parenthetical_effective_cash_from_reference_price_formula(self):
        text=(
            '本次权益分派实施后除权除息价格计算时，根据股票市值不变原则，以公司总股本折算后的'
            '每10股现金股利=实际派发现金股利总额÷总股本×10（即2.159573元=222,881,541.30元÷'
            '1,032,062,937股×10）。除权除息参考价=股权登记日收盘价-每股派发现金红利金额'
            '（即0.2159573元）。'
        )
        x=extract_effective_terms(text)
        self.assertAlmostEqual(x['cash_per_share'],0.2159573)


if __name__=='__main__':
    unittest.main()
