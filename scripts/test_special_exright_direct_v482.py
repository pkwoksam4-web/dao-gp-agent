import unittest

import materialize_special_exright_manifest_v482 as mod


class SpecialExrightDirectV482Tests(unittest.TestCase):
    def test_manifest_requires_exact_key_and_official_cninfo_pdf(self):
        ledger=[{'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87}]
        manifest=[{'symbol':'000430.SZ','ex_date':'2025-12-29','announcement_id':'1224901403','pdf_url':'https://static.cninfo.com.cn/finalpage/2025-12-27/1224901403.PDF'}]
        out=mod.validate_manifest(ledger,manifest,expected_n=1)
        self.assertEqual(out[('000430.SZ','2025-12-29')]['announcement_id'],'1224901403')

    def test_non_cninfo_or_key_mismatch_fails_closed(self):
        ledger=[{'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87}]
        bad=[{'symbol':'000430.SZ','ex_date':'2025-12-29','announcement_id':'x','pdf_url':'https://example.com/x.pdf'}]
        with self.assertRaises(ValueError):
            mod.validate_manifest(ledger,bad,expected_n=1)


if __name__=='__main__': unittest.main()
