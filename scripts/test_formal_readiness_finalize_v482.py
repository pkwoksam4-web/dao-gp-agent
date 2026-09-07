import unittest

import formal_readiness_finalize_v482 as mod


class FormalReadinessFinalizeV482Tests(unittest.TestCase):
    def test_merge_requires_exact_key_price_and_materialized_sha(self):
        special=[{'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87,'corrected_event_ratio':0.86}]
        report={'target_n':1,'materialized_n':1,'unresolved_n':0,'records':[{
            'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87,'status':'PASS_CNINFO_MATERIALIZED',
            'provenance':{'source':'CNINFO_OFFICIAL_PDF','announcement_id':'123','materialized_sha256':'a'*64}
        }]}
        rows=mod.enrich_special_rows(special,report,expected_n=1)
        self.assertEqual(rows[0]['materialized_sha256'],'a'*64)
        self.assertEqual(rows[0]['announcement_id'],'123')

    def test_unresolved_special_blocks_enrichment(self):
        special=[{'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87,'corrected_event_ratio':0.86}]
        report={'target_n':1,'materialized_n':0,'unresolved_n':1,'records':[{
            'symbol':'000430.SZ','ex_date':'2025-12-29','status':'UNRESOLVED','provenance':None
        }]}
        with self.assertRaises(ValueError):
            mod.enrich_special_rows(special,report,expected_n=1)


if __name__=='__main__': unittest.main()
