from __future__ import annotations

import pathlib
import tempfile
import unittest

import reparse_existing_effective_terms_v482 as mod


class ReparseExistingEffectiveTermsV482Tests(unittest.TestCase):
    def test_reparses_frozen_text_file_without_refetching_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            (root/'text').mkdir()
            (root/'text'/'a.txt').write_text(
                '本次权益分派实施后的除权除息参考价格=（股权登记日收盘价格-0.2961638）元/股。',
                encoding='utf-8',
            )
            report={
                'matched_candidate_event_n':1,
                'records':[{
                    'symbol':'001203.SZ','ex_date':'2023-05-16',
                    'pdf_evidence':{'text_extract_ok':True,'text_file':'a.txt','sha256':'abc'},
                }],
                'formal_promotion':False,
                'validated_global_provenance_emitted':False,
            }
            out=mod.reparse_report(report,root)
            self.assertEqual(out['reparsed_event_n'],1)
            self.assertEqual(out['effective_term_event_n'],1)
            terms=out['records'][0]['pdf_evidence']['effective_terms']
            self.assertAlmostEqual(terms['cash_per_share'],0.2961638)
            self.assertFalse(out['formal_promotion'])

    def test_parse_error_is_recorded_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            (root/'text').mkdir()
            (root/'text'/'b.txt').write_text(
                '每股现金红利应以0.10元/股计算。按公司总股本折算每股现金分红比例=0.20元/股。',
                encoding='utf-8',
            )
            report={
                'matched_candidate_event_n':1,
                'records':[{
                    'symbol':'000001.SZ','ex_date':'2023-01-01',
                    'pdf_evidence':{'text_extract_ok':True,'text_file':'b.txt','sha256':'def'},
                }],
                'formal_promotion':False,
                'validated_global_provenance_emitted':False,
            }
            out=mod.reparse_report(report,root)
            self.assertEqual(out['parse_error_event_n'],1)
            self.assertIsNone(out['records'][0]['pdf_evidence']['effective_terms'])


if __name__=='__main__':
    unittest.main()
