import unittest

import strategy_recovery_dependency_v482 as mod


BASE_BLOCKERS = [
    'FACTOR_DEFINITION_MISSING',
    'PARAMETER_SET_MISSING',
    'STRATEGY_CODE_MISSING',
]

MISSING_FIELDS = [
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
]


def recovery_checkpoint():
    return {
        'artifact': 'STRATEGY_ASSET_RECOVERY_CHECKPOINT_V482',
        'version': 'V4.82',
        'strategy_id': 'GP_V11',
        'status': 'STRATEGY_ASSETS_INCOMPLETE_V482',
        'strategy_code_recovered': False,
        'parameter_set_recovered': False,
        'factor_definition_recovered': False,
        'strategy_assets': {},
        'evidence_sha256': 'a' * 64,
        'searched_surfaces': [
            {
                'surface': 'google_drive_authorized_scope_2026_09_09',
                'confidence': 'ABSENT',
                'finding': 'no accessible matching files',
            },
            {
                'surface': 'vercel_connected_team_projects_2026_09_09',
                'confidence': 'ABSENT',
                'finding': 'zero visible projects',
            },
            {
                'surface': 'replit_relevant_window_apps_2026_09_09',
                'confidence': 'UNINSPECTABLE',
                'finding': 'apps exist but read-only code inspection timed out',
            },
            {
                'surface': 'v3_10_internal_source_path_trace',
                'confidence': 'AUTHORITATIVE_FILE',
                'finding': 'auxiliary validator source path existed; not scorer provenance',
            },
        ],
        'confirmed_rules': [],
        'candidate_clues': [
            {
                'key': 'factor_weights_pct',
                'confidence': 'CONVERSATION_CANDIDATE_UNCONFIRMED',
                'value': [8, 4, 10, 7, 8, 12, 10, 8, 7, 8, 10, 8],
                'freeze_eligible': False,
            },
        ],
        'missing_required_fields': MISSING_FIELDS[:],
        'blockers': BASE_BLOCKERS[:],
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


class StrategyRecoveryDependencyV482Tests(unittest.TestCase):
    def test_incomplete_recovery_emits_waiting_dependency(self):
        out = mod.build_strategy_recovery_dependency(recovery_checkpoint())
        self.assertEqual(out['artifact'], 'STRATEGY_RECOVERY_DEPENDENCY_V482')
        self.assertEqual(out['version'], 'V4.82')
        self.assertEqual(out['strategy_id'], 'GP_V11')
        self.assertEqual(out['status'], 'WAITING_FOR_AUTHORITATIVE_STRATEGY_ASSETS_V482')
        self.assertEqual(out['remaining_blockers'], BASE_BLOCKERS)
        self.assertFalse(out['dependency_satisfied'])
        self.assertFalse(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_uninspectable_carrier_is_preserved_as_reopen_trigger(self):
        out = mod.build_strategy_recovery_dependency(recovery_checkpoint())
        self.assertEqual(out['uninspectable_surfaces'], ['replit_relevant_window_apps_2026_09_09'])
        self.assertIn('UNINSPECTABLE_CARRIER_BECOMES_INSPECTABLE', out['reopen_conditions'])

    def test_absent_surfaces_are_marked_exhausted_and_not_retried(self):
        out = mod.build_strategy_recovery_dependency(recovery_checkpoint())
        self.assertEqual(
            out['exhausted_surfaces'],
            [
                'google_drive_authorized_scope_2026_09_09',
                'vercel_connected_team_projects_2026_09_09',
            ],
        )
        self.assertFalse(out['repeat_equivalent_exhausted_searches_allowed'])

    def test_required_authoritative_inputs_map_exactly_to_three_blockers(self):
        out = mod.build_strategy_recovery_dependency(recovery_checkpoint())
        mapped = {item['satisfies_blocker'] for item in out['required_authoritative_inputs']}
        self.assertEqual(mapped, set(BASE_BLOCKERS))
        by_blocker = {item['satisfies_blocker']: item for item in out['required_authoritative_inputs']}
        self.assertTrue(by_blocker['STRATEGY_CODE_MISSING']['requires_sha256'])
        self.assertTrue(by_blocker['STRATEGY_CODE_MISSING']['requires_provenance'])
        self.assertTrue(by_blocker['PARAMETER_SET_MISSING']['complete_package_required'])
        self.assertTrue(by_blocker['FACTOR_DEFINITION_MISSING']['complete_package_required'])

    def test_conversation_candidates_and_auxiliary_components_cannot_satisfy_dependency(self):
        out = mod.build_strategy_recovery_dependency(recovery_checkpoint())
        self.assertFalse(out['conversation_candidate_clues_can_satisfy_blockers'])
        self.assertFalse(out['auxiliary_components_can_satisfy_strategy_code'])

    def test_checkpoint_hash_is_stable_across_key_order(self):
        x = recovery_checkpoint()
        y = {k: x[k] for k in reversed(list(x.keys()))}
        self.assertEqual(mod.canonical_json_sha256(x), mod.canonical_json_sha256(y))
        self.assertEqual(
            mod.build_strategy_recovery_dependency(x)['strategy_recovery_checkpoint_sha256'],
            mod.build_strategy_recovery_dependency(y)['strategy_recovery_checkpoint_sha256'],
        )

    def test_missing_expected_blocker_is_rejected(self):
        x = recovery_checkpoint()
        x['blockers'].remove('STRATEGY_CODE_MISSING')
        with self.assertRaises(ValueError):
            mod.build_strategy_recovery_dependency(x)

    def test_upstream_model_freeze_open_is_rejected(self):
        x = recovery_checkpoint()
        x['model_freeze_allowed'] = True
        with self.assertRaises(ValueError):
            mod.build_strategy_recovery_dependency(x)

    def test_upstream_oos_open_is_rejected(self):
        x = recovery_checkpoint()
        x['oos_metrics_allowed'] = True
        with self.assertRaises(ValueError):
            mod.build_strategy_recovery_dependency(x)

    def test_nested_forbidden_metric_field_is_rejected(self):
        x = recovery_checkpoint()
        x['searched_surfaces'][0]['extra'] = {'sharpe': 1.0}
        with self.assertRaises(ValueError):
            mod.build_strategy_recovery_dependency(x)

    def test_exact_missing_field_contract_is_preserved(self):
        out = mod.build_strategy_recovery_dependency(recovery_checkpoint())
        self.assertEqual(out['missing_required_fields'], MISSING_FIELDS)


if __name__ == '__main__':
    unittest.main()
