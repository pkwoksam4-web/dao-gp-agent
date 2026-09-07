import unittest

from materialize_standard_exact_pdfs_v481 import factor_jump_ratio, select_candidate_events, _parse_sina_js


class StandardExactPdfCandidateTests(unittest.TestCase):
    def test_factor_jump_uses_event_factor_over_prior_chronological_factor(self):
        factors=[
            {'d':'2020-01-01','f':2.0},
            {'d':'2021-05-10','f':1.8},
            {'d':'2022-05-10','f':1.71},
        ]
        self.assertAlmostEqual(factor_jump_ratio(factors,'2021-05-10'),0.9)
        self.assertAlmostEqual(factor_jump_ratio(factors,'2022-05-10'),0.95)

    def test_selects_only_events_over_threshold(self):
        record={'events':[
            {'ex_date':'2021-05-10','event_ratio':0.8990},
            {'ex_date':'2022-05-10','event_ratio':0.9500},
        ]}
        factors=[
            {'d':'2020-01-01','f':2.0},
            {'d':'2021-05-10','f':1.8},
            {'d':'2022-05-10','f':1.71},
        ]
        out=select_candidate_events(record,factors,threshold_bp=5.0)
        self.assertEqual([x['ex_date'] for x in out],['2021-05-10'])
        self.assertGreater(out[0]['event_diff_bp'],5.0)

    def test_missing_factor_date_fails_closed(self):
        with self.assertRaises(ValueError):
            factor_jump_ratio([{'d':'2020-01-01','f':2.0}],'2021-05-10')

    def test_parses_live_sina_qfq_js_with_trailing_signature_comment(self):
        raw=(
            'var sz000001qfq={"total":2,"data":['
            '{"d":"2021-05-10","f":"1.8000000000000000"},'
            '{"d":"1900-01-01","f":"2.0000000000000000"}]};\n'
            '/* encrypted signature payload ABCDEFG== */\n'
        ).encode('utf-8')
        rows=_parse_sina_js(raw)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['d'],'2021-05-10')

    def test_sina_parser_rejects_invalid_or_empty_data(self):
        with self.assertRaises(ValueError):
            _parse_sina_js(b'var sz000001qfq={"total":0,"data":[]}; /* sig */')
        with self.assertRaises(ValueError):
            _parse_sina_js(b'not-a-sina-factor-payload')


if __name__=='__main__':
    unittest.main()
