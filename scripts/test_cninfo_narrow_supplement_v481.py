import unittest

from cninfo_narrow_supplement_v481 import (
    select_unmatched_targets,
    merge_base_with_supplement,
)


class NarrowSupplementScopeTests(unittest.TestCase):
    def test_selects_all_events_for_query_error_and_only_missing_for_partial(self):
        base={'records':[
            {'symbol':'000001.SZ','event_dates':['2024-01-02','2025-01-02'],'error':'HTTP 504','matches':{}},
            {'symbol':'000002.SZ','event_dates':['2024-01-02','2025-01-02'],'error':None,
             'matches':{'2024-01-02':{'announcementId':'a'},'2025-01-02':None}},
            {'symbol':'000003.SZ','event_dates':['2024-01-02'],'error':None,
             'matches':{'2024-01-02':{'announcementId':'b'}}},
        ]}
        out=select_unmatched_targets(base)
        self.assertEqual(out,{
            '000001.SZ':['2024-01-02','2025-01-02'],
            '000002.SZ':['2025-01-02'],
        })

    def test_merge_fills_only_previously_unmatched_events(self):
        base={'scope_symbol_n':2,'records':[
            {'symbol':'000001.SZ','event_dates':['2024-01-02'],'error':'HTTP 504','matches':{}},
            {'symbol':'000002.SZ','event_dates':['2024-01-02','2025-01-02'],'error':None,
             'matches':{'2024-01-02':{'announcementId':'a'},'2025-01-02':None}},
        ],'formal_promotion':False,'validated_global_provenance_emitted':False,
           'formal_ready':False,'oos_metrics_allowed':False}
        supplement={'records':[
            {'symbol':'000001.SZ','ex_date':'2024-01-02','match':{'announcementId':'x'},'error':None},
            {'symbol':'000002.SZ','ex_date':'2025-01-02','match':{'announcementId':'y'},'error':None},
        ]}
        out=merge_base_with_supplement(base,supplement,expected_scope_n=2)
        by={r['symbol']:r for r in out['records']}
        self.assertEqual(by['000001.SZ']['matches']['2024-01-02']['announcementId'],'x')
        self.assertEqual(by['000002.SZ']['matches']['2024-01-02']['announcementId'],'a')
        self.assertEqual(by['000002.SZ']['matches']['2025-01-02']['announcementId'],'y')
        self.assertEqual(out['matched_event_n'],3)
        self.assertEqual(out['unmatched_event_n'],0)
        self.assertEqual(out['symbols_all_events_matched_n'],2)

    def test_merge_refuses_to_overwrite_existing_match(self):
        base={'scope_symbol_n':1,'records':[
            {'symbol':'000001.SZ','event_dates':['2024-01-02'],'error':None,
             'matches':{'2024-01-02':{'announcementId':'a'}}},
        ],'formal_promotion':False,'validated_global_provenance_emitted':False,
           'formal_ready':False,'oos_metrics_allowed':False}
        supplement={'records':[{'symbol':'000001.SZ','ex_date':'2024-01-02','match':{'announcementId':'x'},'error':None}]}
        with self.assertRaises(ValueError):
            merge_base_with_supplement(base,supplement,expected_scope_n=1)


if __name__=='__main__':
    unittest.main()
