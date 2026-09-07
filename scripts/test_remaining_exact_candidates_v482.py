from __future__ import annotations

import unittest

import remaining_exact_candidates_v482 as mod


class RemainingExactCandidateTests(unittest.TestCase):
    def test_selects_matched_unoverridden_events_even_below_5bp(self):
        remaining={'000001.SZ'}
        frozen={
            'records':[{ 'symbol':'000001.SZ','events':[
                {'ex_date':'2022-01-10','event_ratio':0.9997},
                {'ex_date':'2023-01-10','event_ratio':0.9996},
            ]}]
        }
        index={
            'records':[{'symbol':'000001.SZ','matches':{
                '2022-01-10':{'announcementId':'a'},
                '2023-01-10':{'announcementId':'b'},
            }}]
        }
        already={('000001.SZ','2022-01-10')}
        rows=mod.select_matched_unoverridden(remaining,frozen,index,already)
        self.assertEqual([(r['symbol'],r['ex_date']) for r in rows],[('000001.SZ','2023-01-10')])
        self.assertEqual(rows[0]['announcement']['announcementId'],'b')

    def test_unmatched_events_remain_out_of_materialization_scope(self):
        rows=mod.select_matched_unoverridden(
            {'000001.SZ'},
            {'records':[{'symbol':'000001.SZ','events':[{'ex_date':'2022-01-10','event_ratio':0.999}]}]},
            {'records':[{'symbol':'000001.SZ','matches':{'2022-01-10':None}}]},
            set(),
        )
        self.assertEqual(rows,[])

    def test_scope_is_fail_closed_to_remaining_symbols(self):
        with self.assertRaises(ValueError):
            mod.select_matched_unoverridden(
                {'000001.SZ'},
                {'records':[{'symbol':'000002.SZ','events':[{'ex_date':'2022-01-10','event_ratio':0.99}]}]},
                {'records':[{'symbol':'000002.SZ','matches':{'2022-01-10':{'announcementId':'x'}}}]},
                set(),
            )


if __name__=='__main__':
    unittest.main()
