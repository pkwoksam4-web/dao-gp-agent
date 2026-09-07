import unittest

import formal_readiness_v482 as mod


class FormalReadinessV482Tests(unittest.TestCase):
    def test_standard_override_chain_requires_exact_270_unique_with_pdf_provenance(self):
        stages = [
            [{'symbol':'000001.SZ','ex_date':'2024-01-02','corrected_event_ratio':0.99,'announcement_id':'a1','pdf_sha256':'1'*64}],
            [{'symbol':'000002.SZ','ex_date':'2024-01-03','corrected_event_ratio':0.98,'announcement_id':'a2','pdf_sha256':'2'*64}],
        ]
        merged = mod.merge_standard_override_rows(stages, expected_n=2)
        self.assertEqual(len(merged), 2)
        self.assertEqual(set(merged), {('000001.SZ','2024-01-02'),('000002.SZ','2024-01-03')})
        with self.assertRaises(ValueError):
            mod.merge_standard_override_rows([stages[0], stages[0]], expected_n=2)

    def test_standard_override_missing_pdf_provenance_fails_closed(self):
        row={'symbol':'000001.SZ','ex_date':'2024-01-02','corrected_event_ratio':0.99,'announcement_id':'a1','pdf_sha256':None}
        with self.assertRaises(ValueError):
            mod.merge_standard_override_rows([[row]], expected_n=1)

    def test_na_partition_is_exact_three_zero_formal_rows(self):
        records=[
            {'symbol':'600074.SH','status':'NOT_APPLICABLE_NO_FORMAL_ROWS','formal_rows':0,'error':None,'source_meta':{'sina':{'sha256':'a'*64},'sohu':{'sha256':'b'*64}}},
            {'symbol':'600485.SH','status':'NOT_APPLICABLE_NO_FORMAL_ROWS','formal_rows':0,'error':None,'source_meta':{'sina':{'sha256':'c'*64},'sohu':{'sha256':'d'*64}}},
            {'symbol':'600677.SH','status':'NOT_APPLICABLE_NO_FORMAL_ROWS','formal_rows':0,'error':None,'source_meta':{'sina':{'sha256':'e'*64},'sohu':{'sha256':'f'*64}}},
        ]
        out=mod.validate_na_records(records)
        self.assertEqual(out['symbols'], ['600074.SH','600485.SH','600677.SH'])
        self.assertEqual(out['count'], 3)

    def test_special_url_only_provenance_blocks_formal_ready(self):
        specials=[{
            'symbol':'000430.SZ','ex_date':'2025-12-29','corrected_event_ratio':0.87,
            'evidence_url':'https://example.com/notice','evidence_kind':'RESTRUCTURING_SPECIAL_EXRIGHT_ANNOUNCEMENT',
            'materialized_sha256':None,
        }]
        p=mod.classify_special_provenance(specials, expected_n=1)
        self.assertEqual(p['materialized_n'],0)
        self.assertEqual(p['blocker_n'],1)
        gate=mod.decide_gate(math_closed=True, standard_provenance_ok=True, na_ok=True, special_provenance=p)
        self.assertFalse(gate['formal_ready'])
        self.assertFalse(gate['validated_global_provenance_emitted'])
        self.assertEqual(gate['status'],'MATH_CLOSED_PROVENANCE_OPEN')

    def test_fully_materialized_provenance_allows_readiness_but_not_oos(self):
        p={'expected_n':1,'materialized_n':1,'blocker_n':0,'blockers':[]}
        gate=mod.decide_gate(math_closed=True, standard_provenance_ok=True, na_ok=True, special_provenance=p)
        self.assertTrue(gate['formal_ready'])
        self.assertTrue(gate['validated_global_provenance_emitted'])
        self.assertFalse(gate['oos_metrics_allowed'])
        self.assertEqual(gate['status'],'FORMAL_READY_V482')


if __name__=='__main__':
    unittest.main()
