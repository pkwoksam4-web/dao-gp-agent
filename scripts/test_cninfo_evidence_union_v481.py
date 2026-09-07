import unittest

from cninfo_evidence_union_v481 import merge_cninfo_evidence_sources
from cninfo_narrow_supplement_v481 import select_unmatched_targets


def ann(i, title='2024年年度权益分派实施公告'):
    return {'announcementId': str(i), 'announcementTitle': title, 'adjunctUrl': f'finalpage/{i}.PDF'}


def report(a=None, b=None):
    return {
        'records': [
            {'symbol': '000001.SZ', 'event_dates': ['2024-05-10', '2025-05-12'], 'matches': {
                '2024-05-10': a, '2025-05-12': None,
            }, 'matched_event_n': 1 if a else 0, 'error': None},
            {'symbol': '000002.SZ', 'event_dates': ['2024-06-20'], 'matches': {
                '2024-06-20': b,
            }, 'matched_event_n': 1 if b else 0, 'error': 'timeout' if b is None else None},
        ],
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }


class EvidenceUnionTests(unittest.TestCase):
    def test_positive_union_only_adds_matches_and_recomputes_counts(self):
        first = report(ann('a'), None)
        second = report(None, ann('b'))
        supplement = report(ann('a'), None)
        supplement['records'][0]['matches']['2025-05-12'] = ann('c', '2024年度利润分配实施公告')
        supplement['records'][0]['matched_event_n'] = 2

        out = merge_cninfo_evidence_sources([
            ('first_long', first), ('second_long', second), ('narrow', supplement)
        ], expected_scope_n=2)

        self.assertEqual(out['scope_symbol_n'], 2)
        self.assertEqual(out['event_date_n'], 3)
        self.assertEqual(out['matched_event_n'], 3)
        self.assertEqual(out['unmatched_event_n'], 0)
        self.assertEqual(out['symbols_all_events_matched_n'], 2)
        self.assertEqual(out['conflict_event_n'], 0)
        self.assertFalse(out['formal_ready'])
        self.assertFalse(out['oos_metrics_allowed'])
        by = {r['symbol']: r for r in out['records']}
        self.assertEqual(by['000001.SZ']['matches']['2024-05-10']['announcementId'], 'a')
        self.assertEqual(by['000001.SZ']['matches']['2025-05-12']['announcementId'], 'c')
        self.assertEqual(by['000002.SZ']['matches']['2024-06-20']['announcementId'], 'b')

    def test_partial_union_exposes_only_true_unmatched_dates_to_retry_selector(self):
        first = report(ann('a'), ann('b'))
        second = report(None, ann('b'))
        out = merge_cninfo_evidence_sources([('first', first), ('second', second)], expected_scope_n=2)
        by = {r['symbol']: r for r in out['records']}
        self.assertIsNone(by['000001.SZ']['error'])
        self.assertEqual(by['000001.SZ']['unmatched_event_dates'], ['2025-05-12'])
        self.assertEqual(select_unmatched_targets(out), {'000001.SZ': ['2025-05-12']})

    def test_negative_or_failed_source_never_overwrites_positive_evidence(self):
        first = report(ann('a'), ann('b'))
        failed = report(None, None)
        out = merge_cninfo_evidence_sources([('first', first), ('failed', failed)], expected_scope_n=2)
        by = {r['symbol']: r for r in out['records']}
        self.assertEqual(by['000001.SZ']['matches']['2024-05-10']['announcementId'], 'a')
        self.assertEqual(by['000002.SZ']['matches']['2024-06-20']['announcementId'], 'b')

    def test_conflicting_positive_announcement_identity_fails_closed(self):
        first = report(ann('a'), None)
        second = report(ann('DIFFERENT'), None)
        with self.assertRaises(ValueError):
            merge_cninfo_evidence_sources([('first', first), ('second', second)], expected_scope_n=2)

    def test_scope_or_event_date_mismatch_fails_closed(self):
        first = report(ann('a'), None)
        second = report(ann('a'), None)
        second['records'][0]['event_dates'] = ['2024-05-11', '2025-05-12']
        with self.assertRaises(ValueError):
            merge_cninfo_evidence_sources([('first', first), ('second', second)], expected_scope_n=2)


if __name__ == '__main__':
    unittest.main()
