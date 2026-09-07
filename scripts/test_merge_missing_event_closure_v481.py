import unittest

from merge_missing_event_closure_v481 import merge_resolved_record, summarize_merged_records


class MissingEventClosureMergeTests(unittest.TestCase):
    def test_pass_resolution_replaces_only_missing_event_record(self):
        base={
            'symbol':'000430.SZ','status':'REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH',
            'missing_in_ledger':['2025-12-29'],'sina_event_dates':['2025-12-29'],
            'factor_validation':{'status':'FAIL','max_diff_bp':1303.0},'events':[],
        }
        resolved={
            'symbol':'000430.SZ','status':'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR',
            'coverage_complete':True,'factor_validation':{'status':'PASS','max_diff_bp':0.1},
            'events':[{'ex_date':'2025-12-29','source':'EASTMONEY_F10_PAGEAJAX_IMPLEMENTED'}],
            'source_meta':{'f10_raw_sha256':'abc'},'error':None,
            'formal_promotion':False,'validated_global_provenance_emitted':False,
        }
        out=merge_resolved_record(base,resolved,'recalc53')
        self.assertEqual(out['status'],'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR')
        self.assertEqual(out['missing_in_ledger'],[])
        self.assertEqual(out['factor_validation']['status'],'PASS')
        self.assertEqual(out['events'][0]['ex_date'],'2025-12-29')
        self.assertEqual(out['missing_event_resolution']['source_group'],'recalc53')
        self.assertEqual(out['missing_event_resolution']['prior_status'],'REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH')

    def test_exact_term_resolution_remains_review(self):
        base={'symbol':'000981.SZ','status':'REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH','missing_in_ledger':['2022-02-25']}
        resolved={
            'symbol':'000981.SZ','status':'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',
            'coverage_complete':True,'factor_validation':{'status':'FAIL','max_diff_bp':4892.0},
            'events':[],'source_meta':{},'error':None,
            'formal_promotion':False,'validated_global_provenance_emitted':False,
        }
        out=merge_resolved_record(base,resolved,'recalc7')
        self.assertEqual(out['status'],'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT')
        self.assertEqual(out['missing_in_ledger'],[])

    def test_refuses_to_replace_non_missing_base_record(self):
        base={'symbol':'000001.SZ','status':'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR'}
        resolved={'symbol':'000001.SZ','status':'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR','coverage_complete':True}
        with self.assertRaises(ValueError):
            merge_resolved_record(base,resolved,'bad')

    def test_summary_separates_pass_exact_missing_and_na(self):
        records=(
            [{'status':'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR'}]*462+
            [{'status':'PASS_GLOBAL_LEDGER_PROVEN_NO_ACTION'}]*240+
            [{'status':'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR'}]*44+
            [{'status':'REVIEW_GLOBAL_LEDGER_EXACT_TERMS'}]*82+
            [{'status':'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT'}]*16+
            [{'status':'NOT_APPLICABLE_NO_FORMAL_ROWS'}]*3
        )
        s=summarize_merged_records(records)
        self.assertEqual(s['record_n'],847)
        self.assertEqual(s['pass_n'],746)
        self.assertEqual(s['exact_review_n'],98)
        self.assertEqual(s['missing_event_n'],0)
        self.assertEqual(s['not_applicable_n'],3)


if __name__=='__main__':
    unittest.main()
