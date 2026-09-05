import unittest
from global_qfq_merge_v481 import merge_records


class MergeTests(unittest.TestCase):
    def test_exact_scope_merges_once(self):
        scope=['000001.SZ','000002.SZ','600000.SH']
        shards=[
            [{'symbol':'000001.SZ','status':'SINA_FACTOR_PATH_SOURCE_READY'}, {'symbol':'600000.SH','status':'UNKNOWN_ZERO_ACTION_OR_SOURCE_EMPTY'}],
            [{'symbol':'000002.SZ','status':'FAILED_HTTP'}],
        ]
        r=merge_records(scope,shards)
        self.assertEqual(r['scope_n'],3)
        self.assertEqual(r['record_n'],3)
        self.assertEqual(r['duplicate_symbols'],[])
        self.assertEqual(r['missing_symbols'],[])
        self.assertEqual(r['extra_symbols'],[])
        self.assertEqual(r['status_counts']['SINA_FACTOR_PATH_SOURCE_READY'],1)

    def test_duplicate_fails_closed(self):
        scope=['000001.SZ']
        r=merge_records(scope,[[{'symbol':'000001.SZ','status':'FAILED_HTTP'}],[{'symbol':'000001.SZ','status':'FAILED_HTTP'}]])
        self.assertEqual(r['duplicate_symbols'],['000001.SZ'])
        self.assertFalse(r['partition_exact'])

    def test_missing_fails_closed(self):
        r=merge_records(['000001.SZ','000002.SZ'],[[{'symbol':'000001.SZ','status':'FAILED_HTTP'}]])
        self.assertEqual(r['missing_symbols'],['000002.SZ'])
        self.assertFalse(r['partition_exact'])


if __name__=='__main__':
    unittest.main()
