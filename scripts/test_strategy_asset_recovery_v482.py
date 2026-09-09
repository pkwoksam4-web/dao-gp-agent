import unittest

import strategy_asset_recovery_v482 as mod


BASE_BLOCKERS = [
    'FACTOR_DEFINITION_MISSING',
    'PARAMETER_SET_MISSING',
    'STRATEGY_CODE_MISSING',
]


def base_recovery_checkpoint():
    return {
        'artifact': 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
        'version': 'V4.82',
        'status': 'MODEL_ASSETS_INCOMPLETE_V482',
        'formal_artifact_sha256': '1' * 64,
        'universe_sha256': '2' * 64,
        'formal_calendar_sha256': '3' * 64,
        'calendar_sha256': '4' * 64,
        'oos_calendar_sha256': '5' * 64,
        'liquidity_threshold_cny': 80_000_000,
        'formal_end': '2026-04-17',
        'strategy_assets': {
            'strategy_code_sha256': None,
            'parameter_sha256': None,
            'factor_definition_sha256': None,
        },
        'blockers': BASE_BLOCKERS[:],
        'model_freeze_allowed': False,
    }


def evidence():
    return {
        'artifact': 'GP_V11_STRATEGY_RECOVERY_EVIDENCE_V482',
        'version': 'V4.82',
        'strategy_id': 'GP_V11',
        'searched_surfaces': [
            {
                'surface': 'github',
                'confidence': 'AUTHORITATIVE_FILE',
                'finding': 'repository root initialized 2026-09-04; no August GP V1.1 source ancestor',
            },
            {
                'surface': 'file_library',
                'confidence': 'AUTHORITATIVE_FILE',
                'finding': 'August 13-26 contains no GP strategy source bundle; GP files begin with data-remediation assets on August 27',
            },
            {
                'surface': 'gmail',
                'confidence': 'AUTHORITATIVE_FILE',
                'finding': 'read-only attachment search returned no matching GP V1.1 or Quant_Research source package',
            },
        ],
        'confirmed_rules': [
            {
                'key': 'label_clock',
                'confidence': 'USER_CONFIRMED',
                'value': 'T+1/T+2/T+3 advance by market trading days, not next available stock K-line',
            },
            {
                'key': 'lookback_windows',
                'confidence': 'USER_CONFIRMED',
                'value': [5, 10, 20, 60, 120],
            },
        ],
        'candidate_clues': [
            {
                'key': 'factor_weights_pct',
                'confidence': 'CONVERSATION_CANDIDATE_UNCONFIRMED',
                'value': [8, 4, 10, 7, 8, 12, 10, 8, 7, 8, 10, 8],
                'note': 'recovered from prior assistant output only; not freeze eligible',
            },
            {
                'key': 'score_layers',
                'confidence': 'CONVERSATION_CANDIDATE_UNCONFIRMED',
                'value': ['Structure', 'Inertia', 'Execution'],
                'note': 'recovered from prior assistant output only; not freeze eligible',
            },
        ],
        'missing_required_fields': [
            'strategy_code_bytes',
            'exact_factor_formulas',
            'exact_normalization_and_clipping',
            'authoritative_weight_vector',
            'score_layer_aggregation',
            'probability_mapping',
            'ranking_topn_semantics',
            'entry_exit_thresholds',
            'holding_and_rebalance_policy',
            'position_sizing_and_risk_rules',
        ],
    }


class StrategyAssetRecoveryV482Tests(unittest.TestCase):
    def test_candidate_weights_never_clear_parameter_blocker(self):
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), evidence())
        self.assertIn('PARAMETER_SET_MISSING', out['blockers'])
        self.assertFalse(out['parameter_set_recovered'])
        clue = next(x for x in out['candidate_clues'] if x['key'] == 'factor_weights_pct')
        self.assertFalse(clue['freeze_eligible'])

    def test_confirmed_coarse_rules_do_not_clear_factor_definition(self):
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), evidence())
        self.assertIn('FACTOR_DEFINITION_MISSING', out['blockers'])
        self.assertFalse(out['factor_definition_recovered'])

    def test_missing_strategy_code_remains_blocked(self):
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), evidence())
        self.assertIn('STRATEGY_CODE_MISSING', out['blockers'])
        self.assertFalse(out['strategy_code_recovered'])

    def test_production_evidence_keeps_exact_three_blockers(self):
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), evidence())
        self.assertEqual(out['status'], 'STRATEGY_ASSETS_INCOMPLETE_V482')
        self.assertEqual(out['blockers'], BASE_BLOCKERS)
        self.assertFalse(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_uninspectable_searched_surface_is_preserved_without_clearing_blockers(self):
        x = evidence()
        x['searched_surfaces'].append({
            'surface': 'replit_random_name_apps',
            'confidence': 'UNINSPECTABLE',
            'finding': 'two relevant-window apps exist but read-only inspection timed out',
        })
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), x)
        surface = next(s for s in out['searched_surfaces'] if s['surface'] == 'replit_random_name_apps')
        self.assertEqual(surface['confidence'], 'UNINSPECTABLE')
        self.assertEqual(out['blockers'], BASE_BLOCKERS)
        self.assertFalse(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_uninspectable_is_not_valid_for_confirmed_rules(self):
        x = evidence()
        x['confirmed_rules'][0]['confidence'] = 'UNINSPECTABLE'
        with self.assertRaises(ValueError):
            mod.evaluate_strategy_recovery(base_recovery_checkpoint(), x)

    def test_unknown_confidence_is_rejected(self):
        x = evidence()
        x['confirmed_rules'][0]['confidence'] = 'MAYBE'
        with self.assertRaises(ValueError):
            mod.evaluate_strategy_recovery(base_recovery_checkpoint(), x)

    def test_unknown_top_level_evidence_field_is_rejected(self):
        x = evidence()
        x['mystery'] = True
        with self.assertRaises(ValueError):
            mod.evaluate_strategy_recovery(base_recovery_checkpoint(), x)

    def test_recursive_oos_metric_field_is_rejected(self):
        x = evidence()
        x['candidate_clues'][0]['value'] = {'nested': {'sharpe': 3.0}}
        with self.assertRaises(ValueError):
            mod.evaluate_strategy_recovery(base_recovery_checkpoint(), x)

    def test_authoritative_complete_assets_can_clear_all_three_in_synthetic_case(self):
        x = evidence()
        assets = {
            'strategy_code': {
                'confidence': 'AUTHORITATIVE_FILE',
                'bytes_sha256': 'a' * 64,
                'source_id': 'synthetic-test-only',
            },
            'parameters': {
                'confidence': 'AUTHORITATIVE_FILE',
                'canonical_sha256': 'b' * 64,
                'source_id': 'synthetic-test-only',
                'complete': True,
            },
            'factor_definition': {
                'confidence': 'AUTHORITATIVE_FILE',
                'canonical_sha256': 'c' * 64,
                'source_id': 'synthetic-test-only',
                'complete': True,
            },
        }
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), x, authoritative_assets=assets)
        self.assertEqual(out['blockers'], [])
        self.assertEqual(out['status'], 'STRATEGY_ASSETS_COMPLETE_V482')
        self.assertTrue(out['strategy_code_recovered'])
        self.assertTrue(out['parameter_set_recovered'])
        self.assertTrue(out['factor_definition_recovered'])
        self.assertTrue(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_incomplete_authoritative_parameters_stay_blocked(self):
        assets = {
            'parameters': {
                'confidence': 'AUTHORITATIVE_FILE',
                'canonical_sha256': 'b' * 64,
                'source_id': 'synthetic-test-only',
                'complete': False,
            }
        }
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), evidence(), authoritative_assets=assets)
        self.assertIn('PARAMETER_SET_MISSING', out['blockers'])

    def test_candidate_clues_are_marked_not_freeze_eligible(self):
        out = mod.evaluate_strategy_recovery(base_recovery_checkpoint(), evidence())
        self.assertTrue(out['candidate_clues'])
        self.assertTrue(all(x['freeze_eligible'] is False for x in out['candidate_clues']))


if __name__ == '__main__':
    unittest.main()
