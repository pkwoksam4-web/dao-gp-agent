import unittest

from merge_cninfo_shards_v481 import merge_shard_reports


class CninfoShardMergeTests(unittest.TestCase):
    def test_merges_exact_partition_and_recomputes_counts(self):
        shards=[]
        for i,records in enumerate((
            [{'symbol':'000001.SZ','event_dates':['2024-01-02'],'matched_event_n':1,'error':None},
             {'symbol':'000003.SZ','event_dates':['2024-01-02','2025-01-02'],'matched_event_n':1,'error':None}],
            [{'symbol':'000002.SZ','event_dates':['2024-01-02'],'matched_event_n':0,'error':'HTTP 504'}],
        )):
            shards.append({'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_V481','version':'V4.81',
                           'full_scope_symbol_n':3,'shard_index':i,'shard_count':2,
                           'scope_symbol_n':len(records),'records':records,
                           'formal_promotion':False,'validated_global_provenance_emitted':False,
                           'formal_ready':False,'oos_metrics_allowed':False})
        out=merge_shard_reports(shards,expected_scope_n=3)
        self.assertEqual(out['scope_symbol_n'],3)
        self.assertEqual(out['query_ok_n'],2)
        self.assertEqual(out['query_error_n'],1)
        self.assertEqual(out['event_date_n'],4)
        self.assertEqual(out['matched_event_n'],2)
        self.assertEqual([r['symbol'] for r in out['records']],['000001.SZ','000002.SZ','000003.SZ'])

    def test_duplicate_symbol_fails_closed(self):
        shards=[
            {'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_V481','version':'V4.81','shard_index':0,'shard_count':2,
             'records':[{'symbol':'000001.SZ','event_dates':[],'matched_event_n':0,'error':None}]},
            {'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_V481','version':'V4.81','shard_index':1,'shard_count':2,
             'records':[{'symbol':'000001.SZ','event_dates':[],'matched_event_n':0,'error':None}]},
        ]
        with self.assertRaises(ValueError):
            merge_shard_reports(shards,expected_scope_n=1)

    def test_missing_shard_fails_closed(self):
        shards=[{'artifact':'CNINFO_STANDARD_EXACT_TERM_INDEX_V481','version':'V4.81','shard_index':0,'shard_count':2,'records':[]}]
        with self.assertRaises(ValueError):
            merge_shard_reports(shards,expected_scope_n=0)


if __name__=='__main__':
    unittest.main()
