import unittest

from merge_global_qfq_nominal_v481 import merge_records


class NominalMergeTests(unittest.TestCase):
    def test_exact_scope_merges_once_and_never_promotes(self):
        scope=['000001.SZ','000002.SZ']
        records=[
            {'symbol':'000001.SZ','status':'PASS_NOMINAL_EVENT_FACTOR','formal_promotion':False},
            {'symbol':'000002.SZ','status':'PASS_PROVEN_NO_FORMAL_ACTIONS','formal_promotion':False},
        ]
        out=merge_records(scope, records)
        self.assertTrue(out['partition_exact'])
        self.assertEqual(out['record_n'],2)
        self.assertFalse(out['formal_promotion'])
        self.assertFalse(out['validated_global_provenance_emitted'])

    def test_duplicate_symbol_fails_closed(self):
        with self.assertRaises(ValueError):
            merge_records(
                ['000001.SZ'],
                [
                    {'symbol':'000001.SZ','status':'PASS_NOMINAL_EVENT_FACTOR'},
                    {'symbol':'000001.SZ','status':'PASS_NOMINAL_EVENT_FACTOR'},
                ],
            )

    def test_missing_symbol_fails_closed(self):
        with self.assertRaises(ValueError):
            merge_records(['000001.SZ','000002.SZ'], [{'symbol':'000001.SZ','status':'PASS_NOMINAL_EVENT_FACTOR'}])

    def test_out_of_scope_symbol_fails_closed(self):
        with self.assertRaises(ValueError):
            merge_records(['000001.SZ'], [{'symbol':'000002.SZ','status':'PASS_NOMINAL_EVENT_FACTOR'}])


if __name__=='__main__':
    unittest.main()
