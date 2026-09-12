import unittest

import gp12_fund_flow_snapshot_admission_v482 as mod


class FundFlowSnapshotAdmissionV482Test(unittest.TestCase):
    def pointer(self):
        return (
            'version https://git-lfs.github.com/spec/v1\n'
            f'oid sha256:{mod.EXPECTED_SHA256}\n'
            f'size {mod.EXPECTED_SIZE_BYTES}\n'
        )

    def summary(self):
        return {
            'repo_id': mod.REPO_ID,
            'source_commit': mod.SOURCE_COMMIT,
            'filename': mod.FILENAME,
            'actual_size_bytes': mod.EXPECTED_SIZE_BYTES,
            'actual_sha256': mod.EXPECTED_SHA256,
            'rows': 9780000,
            'symbols': 5000,
            'first_date': '2021-01-04',
            'last_date': '2025-02-27',
            'columns_present': ['code','date',*mod.FLOW_COLUMNS],
            'flow_non_null_rows': {c: 9000000 for c in mod.FLOW_COLUMNS},
        }

    def test_exact_remote_pointer_contract(self):
        x=mod.validate_remote_pointer(self.pointer())
        self.assertEqual(x['sha256'],mod.EXPECTED_SHA256)
        self.assertEqual(x['size_bytes'],mod.EXPECTED_SIZE_BYTES)

    def test_pointer_hash_or_size_change_fails(self):
        for bad in [
            self.pointer().replace(mod.EXPECTED_SHA256,'0'*64),
            self.pointer().replace(str(mod.EXPECTED_SIZE_BYTES),str(mod.EXPECTED_SIZE_BYTES+1)),
        ]:
            with self.assertRaises(ValueError):
                mod.validate_remote_pointer(bad)

    def test_verified_payload_closes_only_source_byte_subgap(self):
        out=mod.build_fund_flow_snapshot_admission(self.summary(), remote_pointer_verified=True)
        self.assertEqual(out['status'],'PASS_LOCKED_FUND_FLOW_SNAPSHOT_PAYLOAD_VERIFIED_PARTIAL_WINDOW')
        self.assertTrue(out['remote_pointer_identity_verified'])
        self.assertTrue(out['actual_snapshot_bytes_verified_in_current_recovery'])
        self.assertFalse(out['formal_window_coverage_complete'])
        self.assertFalse(out['pit_known_at_semantics_recovered'])
        self.assertFalse(out['factor_formula_recovered'])
        self.assertFalse(out['blocker_closed'])
        self.assertFalse(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])
        self.assertNotIn('FUND_FLOW_SOURCE_BYTES_NOT_VERIFIED_IN_CURRENT_RECOVERY',out['remaining_data_gaps'])
        self.assertIn('FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE',out['remaining_data_gaps'])

    def test_missing_flow_column_fails_closed(self):
        x=self.summary(); x['columns_present'].remove(mod.FLOW_COLUMNS[-1])
        with self.assertRaisesRegex(ValueError,'flow columns'):
            mod.build_fund_flow_snapshot_admission(x,remote_pointer_verified=True)

    def test_wrong_payload_hash_fails_closed(self):
        x=self.summary(); x['actual_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'payload identity'):
            mod.build_fund_flow_snapshot_admission(x,remote_pointer_verified=True)


if __name__=='__main__':
    unittest.main()
