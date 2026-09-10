import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class StrategyIntradaySourceRecoveryV482Tests(unittest.TestCase):
    def test_intraday_evidence_binds_exact_historical_inventory(self):
        path = ROOT / 'data' / 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(doc['artifact'], 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482')
        self.assertEqual(doc['version'], 'V4.82')
        src = doc['primary_source']
        self.assertEqual(src['dataset'], 'neigezhu/china-a-share-1min-ohlcv')
        self.assertEqual(src['snapshot_commit_full'], 'f311a5f11569e9d541386982d15f2214d9970b8a')
        self.assertEqual(src['frequency'], '1min')
        self.assertEqual(src['price_basis'], 'RAW_UNADJUSTED')
        self.assertEqual(src['volume_unit'], 'shares')
        self.assertEqual(src['turnover_unit'], 'CNY')

        hist = doc['historical_delisted_inventory']
        self.assertEqual(hist['evidence_sha256'], 'e4ef39e67de755c41605e869338a55b722cc0fc146a64c662bae4b82c260d839')
        self.assertEqual(hist['symbols'], 163)
        self.assertEqual(hist['found_in_inventory'], 163)
        self.assertEqual(hist['complete'], 129)
        self.assertEqual(hist['partial'], 34)
        self.assertEqual(hist['audited_missing_trading_days'], 3935)
        self.assertEqual(hist['unique_canonical_files'], 163)

    def test_supporting_project_evidence_hashes_are_exact(self):
        doc = json.loads((ROOT / 'data' / 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482.json').read_text(encoding='utf-8'))
        ev = doc['supporting_project_evidence']
        self.assertEqual(ev['PRICE_SOURCE_SCOPE_CORRECTION_V402_sha256'], 'b68ee062101f0b833b126b1cb1281d8f2bb792f8058442db95ce467b3c0a612f')
        self.assertEqual(ev['DELISTED_GAP_SEMANTICS_V404_sha256'], '665788453a2bba67efeaf950f1d34c86b5db74bbbd9034f6bca38a6336be06b9')
        self.assertEqual(ev['FORMAL_GATE_CHECKPOINT_V456_sha256'], '20c282f080f4e17d9fc3450017c50ed61b4b8ecaa38112244f7251c3143857c6')
        self.assertEqual(ev['EXECUTION_ROUTE_MATRIX_V457_sha256'], '4bd22dfcdd007ed011b81e71533664930f3269783d643a90252f6f6bc3329a76')
        self.assertEqual(ev['NON_MAIN_DELISTED_NEIGEZHU_COVERAGE_V402_sha256'], '4d3ff7c1952148d2eea08732ea369fb58c3585afa721663feeb292d1687807b4')
        self.assertEqual(ev['PRICE_SOURCE_SCOPE_ROUTING_V402_sha256'], '5a09443ae4e3eb10343b2b22174844f1beb7c4b5fee0743bb7e2f79585f7a289')

    def test_intraday_recovery_is_partial_and_fail_closed(self):
        doc = json.loads((ROOT / 'data' / 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['status'], 'PARTIAL_FILE_BACKED_SOURCE_INVENTORY_ONLY')
        self.assertFalse(doc['actual_minute_bytes_materialized_in_strategy_recovery'])
        self.assertFalse(doc['formal_847_15m_coverage_verified'])
        self.assertFalse(doc['formal_847_60m_coverage_verified'])
        self.assertFalse(doc['resampling_contract_recovered'])
        self.assertFalse(doc['factor_formula_recovered'])
        self.assertFalse(doc['model_freeze_allowed'])
        self.assertFalse(doc['oos_metrics_allowed'])

    def test_factor_matrix_upgrades_intraday_only_to_partial(self):
        matrix = json.loads((ROOT / 'data' / 'GP_V11_FACTOR_RECOVERY_MATRIX_V482.json').read_text(encoding='utf-8'))
        by_name = {x['name']: x for x in matrix['factors']}
        intraday = by_name['Intraday Confirmation']
        self.assertEqual(intraday['recovery_status'], 'PARTIAL_FILE_BACKED')
        self.assertTrue(intraday['known_components'])
        missing = ' '.join(intraday['missing']).lower()
        self.assertIn('15-minute', missing)
        self.assertIn('60-minute', missing)
        self.assertIn('resampling', missing)
        self.assertIn('formula', missing)
        src = matrix['intraday_source_partial']
        self.assertEqual(src['snapshot_commit_full'], 'f311a5f11569e9d541386982d15f2214d9970b8a')
        self.assertEqual(src['evidence_artifact'], 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482')
        self.assertFalse(src['actual_minute_bytes_materialized'])
        self.assertFalse(src['formal_15m_coverage_verified'])
        self.assertFalse(src['formal_60m_coverage_verified'])
        self.assertFalse(src['factor_formula_recovered'])


if __name__ == '__main__':
    unittest.main()
