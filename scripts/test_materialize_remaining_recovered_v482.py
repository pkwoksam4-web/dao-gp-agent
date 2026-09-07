from __future__ import annotations

import unittest

import materialize_remaining_recovered_v482 as mod


class MaterializeRemainingRecoveredV482Tests(unittest.TestCase):
    def test_selects_only_successfully_matched_recovery_rows(self):
        report={'records':[
            {'symbol':'000631.SZ','ex_date':'2023-05-17','match':{'announcementId':'a','adjunctUrl':'a.pdf'},'error':None},
            {'symbol':'000631.SZ','ex_date':'2024-07-05','match':None,'error':None},
            {'symbol':'001230.SZ','ex_date':'2024-06-06','match':{'announcementId':'b','adjunctUrl':'b.pdf'},'error':None},
            {'symbol':'000550.SZ','ex_date':'2025-08-20','match':None,'error':'TimeoutError'},
        ]}
        rows=mod.select_matched_rows(report)
        self.assertEqual([(r['symbol'],r['ex_date']) for r in rows],[('000631.SZ','2023-05-17'),('001230.SZ','2024-06-06')])

    def test_duplicate_event_key_fails_closed(self):
        report={'records':[
            {'symbol':'000631.SZ','ex_date':'2023-05-17','match':{'announcementId':'a','adjunctUrl':'a.pdf'},'error':None},
            {'symbol':'000631.SZ','ex_date':'2023-05-17','match':{'announcementId':'b','adjunctUrl':'b.pdf'},'error':None},
        ]}
        with self.assertRaises(ValueError):
            mod.select_matched_rows(report)

    def test_unique_announcement_map_deduplicates_shared_pdf(self):
        rows=[
            {'symbol':'000631.SZ','ex_date':'2023-05-17','match':{'announcementId':'a','adjunctUrl':'a.pdf'}},
            {'symbol':'000631.SZ','ex_date':'2023-05-18','match':{'announcementId':'a','adjunctUrl':'a.pdf'}},
        ]
        unique=mod.unique_announcements(rows)
        self.assertEqual(list(unique),['a'])


if __name__=='__main__':
    unittest.main()
