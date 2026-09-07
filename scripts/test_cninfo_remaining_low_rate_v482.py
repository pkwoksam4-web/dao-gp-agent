from __future__ import annotations

import unittest

import cninfo_remaining_low_rate_v482 as mod


class RemainingLowRateV482Tests(unittest.TestCase):
    def test_selects_only_unmatched_events_for_current_remaining_symbols(self):
        base={
            'records':[
                {'symbol':'000631.SZ','event_dates':['2023-05-17','2024-07-05'],'matches':{'2023-05-17':None,'2024-07-05':None}},
                {'symbol':'000541.SZ','event_dates':['2024-06-03'],'matches':{'2024-06-03':None}},
                {'symbol':'001230.SZ','event_dates':['2024-06-06','2025-06-13'],'matches':{'2024-06-06':None,'2025-06-13':{'announcementId':'x'}}},
            ]
        }
        closure={'remaining_symbols':['000631.SZ','001230.SZ']}
        self.assertEqual(
            mod.select_remaining_unmatched_targets(base,closure),
            {'000631.SZ':['2023-05-17','2024-07-05'],'001230.SZ':['2024-06-06']},
        )

    def test_preseed_probe_removes_already_recovered_targets(self):
        targets={'000631.SZ':['2023-05-17','2024-07-05'],'001230.SZ':['2024-06-06','2024-10-18']}
        probe={'records':[
            {'symbol':'000631.SZ','ex_date':'2023-05-17','match':{'announcementId':'a'}},
            {'symbol':'001230.SZ','ex_date':'2024-06-06','match':{'announcementId':'b'}},
        ]}
        remaining,recovered=mod.remove_preseeded_matches(targets,probe)
        self.assertEqual(remaining,{'000631.SZ':['2024-07-05'],'001230.SZ':['2024-10-18']})
        self.assertEqual(sorted(recovered),[('000631.SZ','2023-05-17'),('001230.SZ','2024-06-06')])

    def test_merge_refuses_to_overwrite_existing_match(self):
        base={'records':[{'symbol':'000631.SZ','event_dates':['2023-05-17'],'matches':{'2023-05-17':{'announcementId':'old'}}}]}
        rows=[{'symbol':'000631.SZ','ex_date':'2023-05-17','match':{'announcementId':'new'},'error':None}]
        with self.assertRaises(ValueError):
            mod.merge_matches(base,rows)


if __name__=='__main__':
    unittest.main()
