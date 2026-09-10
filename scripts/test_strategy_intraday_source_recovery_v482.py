import hashlib
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

    def test_single_symbol_resampling_pilot_is_exactly_bound(self):
        doc = json.loads((ROOT / 'data' / 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482.json').read_text(encoding='utf-8'))
        pilot = doc['single_symbol_resampling_pilot']
        self.assertEqual(pilot['scope'], '002002.SZ_ONLY')
        self.assertEqual(pilot['source_pilot_run_id'], 34431397499)
        self.assertEqual(pilot['source_pilot_head_sha'], 'f3d94fb3c6e668f3de550b4872e2935095609d44')
        self.assertEqual(pilot['source_pilot_artifact_id'], 10134644253)
        self.assertEqual(pilot['source_pilot_artifact_digest'], 'sha256:a974fbf4d1974cfa16bc97da2fd28d5c12debaf2ae2ca0ccf06d11e034d55e69')
        self.assertEqual(pilot['source_sha256'], '209907efad308af285f937f913a8c8017ab75eede908a87ce5c109989eb43d92')
        self.assertEqual(pilot['source_bytes'], 8868737)
        self.assertEqual(pilot['source_rows'], 820123)
        self.assertEqual(pilot['trading_dates'], 3403)
        self.assertEqual(pilot['continuous_rows'], 816720)
        self.assertEqual(pilot['bars_15m_rows'], 54448)
        self.assertEqual(pilot['bars_15m_sha256'], 'cfd34f09d29bcaac1c0f9d47197fb640d1a9721a6e929e2458e3d6144d3596a8')
        self.assertEqual(pilot['bars_60m_rows'], 13612)
        self.assertEqual(pilot['bars_60m_sha256'], '6ac057ed46d99d12864ce301ffa4cbc2939c94c69e7d647242b1a17da9bcef99')
        self.assertEqual(pilot['independent_verify_run_id'], 34431659116)
        self.assertEqual(pilot['independent_verify_head_sha'], 'b3436aaa31e93ebb0c9fdd9771067419fc7f9ee3')
        self.assertEqual(pilot['independent_verify_artifact_id'], 10134703581)
        self.assertEqual(pilot['independent_verify_artifact_digest'], 'sha256:a22eaf171b4daec9c2c7d3cadf82de01135e5c1ab0684b17bbdd584bef830cf9')
        self.assertEqual(pilot['independent_verify_report_sha256'], '1eb392c8224d13c0b883ea71ec27cd84f73f599c0526107608e0996725c6068a')
        self.assertTrue(pilot['full_reconstruction_match_15m'])
        self.assertTrue(pilot['full_reconstruction_match_60m'])
        self.assertEqual(pilot['lunch_crossing_count_15m'], 0)
        self.assertEqual(pilot['lunch_crossing_count_60m'], 0)
        self.assertFalse(pilot['historical_authority'])

    def test_independent_verifier_report_is_repository_bound_and_fail_closed(self):
        path = ROOT / 'data' / 'GP_V11_INTRADAY_MINUTE_PILOT_VERIFY_V482.json'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '1eb392c8224d13c0b883ea71ec27cd84f73f599c0526107608e0996725c6068a')
        report = json.loads(raw.decode('utf-8'))
        self.assertEqual(report['artifact'], 'INTRADAY_MINUTE_PILOT_INDEPENDENT_VERIFY_V482')
        self.assertEqual(report['status'], 'PASS_INDEPENDENT_FULL_RECONSTRUCTION_SINGLE_SYMBOL_PILOT_NOT_FORMAL')
        self.assertEqual(report['verification_head_sha'], 'b3436aaa31e93ebb0c9fdd9771067419fc7f9ee3')
        self.assertEqual(report['source_pilot_run_id'], 34431397499)
        self.assertEqual(report['source_pilot_artifact_id'], 10134644253)
        self.assertEqual(report['source_pilot_artifact_digest'], 'sha256:a974fbf4d1974cfa16bc97da2fd28d5c12debaf2ae2ca0ccf06d11e034d55e69')
        self.assertEqual(report['source_sha256'], '209907efad308af285f937f913a8c8017ab75eede908a87ce5c109989eb43d92')
        self.assertEqual(report['source_rows'], 820123)
        self.assertEqual(report['trading_dates'], 3403)
        self.assertEqual(report['continuous_rows'], 816720)
        self.assertEqual(report['bars_15m_rows'], 54448)
        self.assertEqual(report['bars_15m_sha256'], 'cfd34f09d29bcaac1c0f9d47197fb640d1a9721a6e929e2458e3d6144d3596a8')
        self.assertEqual(report['bars_60m_rows'], 13612)
        self.assertEqual(report['bars_60m_sha256'], '6ac057ed46d99d12864ce301ffa4cbc2939c94c69e7d647242b1a17da9bcef99')
        self.assertTrue(report['full_row_by_row_reconstruction_match_15m'])
        self.assertTrue(report['full_row_by_row_reconstruction_match_60m'])
        self.assertEqual(report['lunch_crossing_count_15m'], 0)
        self.assertEqual(report['lunch_crossing_count_60m'], 0)
        self.assertFalse(report['formal_847_coverage_verified'])
        self.assertFalse(report['historical_gp_formula_recovered'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])

    def test_intraday_recovery_upgrades_only_single_symbol_materialization(self):
        doc = json.loads((ROOT / 'data' / 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['status'], 'PARTIAL_FILE_BACKED_FORMAL847_INVENTORY_PLUS_SINGLE_SYMBOL_RESAMPLING_PILOT')
        self.assertTrue(doc['actual_minute_bytes_materialized_in_strategy_recovery'])
        self.assertEqual(doc['actual_minute_bytes_materialized_scope'], 'SINGLE_SYMBOL_002002_ONLY')
        self.assertTrue(doc['single_symbol_session_aware_resampling_pilot_validated'])
        self.assertFalse(doc['formal_847_15m_coverage_verified'])
        self.assertFalse(doc['formal_847_60m_coverage_verified'])
        self.assertFalse(doc['resampling_contract_recovered'])
        self.assertFalse(doc['factor_formula_recovered'])
        self.assertFalse(doc['model_freeze_allowed'])
        self.assertFalse(doc['oos_metrics_allowed'])

    def test_factor_matrix_binds_pilot_without_promoting_formal_intraday(self):
        matrix = json.loads((ROOT / 'data' / 'GP_V11_FACTOR_RECOVERY_MATRIX_V482.json').read_text(encoding='utf-8'))
        by_name = {x['name']: x for x in matrix['factors']}
        intraday = by_name['Intraday Confirmation']
        self.assertEqual(intraday['recovery_status'], 'PARTIAL_FILE_BACKED')
        self.assertTrue(intraday['known_components'])
        missing = ' '.join(intraday['missing']).lower()
        self.assertIn('formal', missing)
        self.assertIn('historical', missing)
        self.assertIn('formula', missing)

        src = matrix['intraday_source_partial']
        self.assertEqual(src['snapshot_commit_full'], 'f311a5f11569e9d541386982d15f2214d9970b8a')
        self.assertEqual(src['evidence_artifact'], 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482')
        self.assertTrue(src['actual_minute_bytes_materialized'])
        self.assertEqual(src['actual_minute_bytes_materialized_scope'], 'SINGLE_SYMBOL_002002_ONLY')
        self.assertFalse(src['formal_15m_coverage_verified'])
        self.assertFalse(src['formal_60m_coverage_verified'])
        self.assertFalse(src['resampling_contract_recovered'])
        self.assertFalse(src['factor_formula_recovered'])

        pilot = matrix['intraday_pilot_partial_source']
        self.assertEqual(pilot['scope'], '002002.SZ_ONLY')
        self.assertEqual(pilot['source_sha256'], '209907efad308af285f937f913a8c8017ab75eede908a87ce5c109989eb43d92')
        self.assertEqual(pilot['bars_15m_sha256'], 'cfd34f09d29bcaac1c0f9d47197fb640d1a9721a6e929e2458e3d6144d3596a8')
        self.assertEqual(pilot['bars_60m_sha256'], '6ac057ed46d99d12864ce301ffa4cbc2939c94c69e7d647242b1a17da9bcef99')
        self.assertEqual(pilot['independent_verify_report_sha256'], '1eb392c8224d13c0b883ea71ec27cd84f73f599c0526107608e0996725c6068a')
        self.assertTrue(pilot['full_reconstruction_match_15m'])
        self.assertTrue(pilot['full_reconstruction_match_60m'])
        self.assertFalse(pilot['historical_gp_resampling_contract_recovered'])
        self.assertFalse(pilot['formal_847_coverage_verified'])
        self.assertFalse(pilot['factor_formula_recovered'])


if __name__ == '__main__':
    unittest.main()
