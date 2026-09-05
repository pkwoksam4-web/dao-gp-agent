import unittest
from merge_pit_st_shards_v480 import merge_reports


class MergeTests(unittest.TestCase):
    def test_merge_requires_exact_partition(self):
        reports = [
            {'scope_n': 4, 'shard_count': 2, 'shard_index': 0, 'audits': [{'symbol': 'A'}, {'symbol': 'C'}], 'daily_rows': 2},
            {'scope_n': 4, 'shard_count': 2, 'shard_index': 1, 'audits': [{'symbol': 'B'}, {'symbol': 'D'}], 'daily_rows': 2},
        ]
        m = merge_reports(reports, expected_symbols=['A', 'B', 'C', 'D'])
        self.assertEqual(m['scope_n'], 4)
        self.assertEqual(m['audit_symbol_n'], 4)
        self.assertEqual(m['duplicate_audit_symbols'], [])
        self.assertEqual(m['missing_audit_symbols'], [])
        self.assertFalse(m['formal_admission'])

    def test_duplicate_or_missing_does_not_close(self):
        reports = [
            {'scope_n': 3, 'shard_count': 2, 'shard_index': 0, 'audits': [{'symbol': 'A'}, {'symbol': 'B'}], 'daily_rows': 2},
            {'scope_n': 3, 'shard_count': 2, 'shard_index': 1, 'audits': [{'symbol': 'B'}], 'daily_rows': 1},
        ]
        m = merge_reports(reports, expected_symbols=['A', 'B', 'C'])
        self.assertEqual(m['duplicate_audit_symbols'], ['B'])
        self.assertEqual(m['missing_audit_symbols'], ['C'])
        self.assertFalse(m['materialization_partition_ok'])


if __name__ == '__main__':
    unittest.main()
