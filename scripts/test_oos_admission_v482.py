import copy
import json
import pathlib
import tempfile
import unittest

import oos_admission_v482 as mod


NA_SYMBOLS = ['600074.SH', '600485.SH', '600677.SH']


def valid_formal():
    return {
        'artifact': 'FORMAL_READINESS_FINAL_V482',
        'version': 'V4.82',
        'checkpoint': {
            'PASS': 844,
            'EXACT_TERM_REVIEW': 0,
            'MISSING_EVENT_REVIEW': 0,
            'NOT_APPLICABLE': 3,
        },
        'universe_n': 847,
        'formal_symbol_n': 844,
        'full_path_pass_n': 844,
        'full_path_fail_n': 0,
        'max_full_path_diff_bp': 0.0,
        'formal_ready': True,
        'validated_global_provenance_emitted': True,
        'oos_metrics_allowed': False,
        'na': {'count': 3, 'symbols': list(NA_SYMBOLS)},
        'special_provenance': {'materialized_n': 11, 'blocker_n': 0},
        'market_data': {
            'market_data_ready': True,
            'symbol_n': 847,
            'raw_trade_rows': 1_011_607,
            'missing_trade_dates_n': 0,
            'extra_trade_dates_n': 0,
            'duplicate_symbol_dates': 0,
            'zero_trade_symbols': list(NA_SYMBOLS),
            'liquidity_threshold_cny': 80_000_000,
            'raw_pitst_status': 'PASS_EXACT_RAW_PITST',
            'current_trade_violation_n': 0,
            'st_overlay_violation_n': 0,
        },
    }


def valid_model(formal):
    return {
        'artifact': 'MODEL_FREEZE_V482',
        'version': 'V4.82',
        'strategy_id': 'GP_V11_RECOVERED',
        'strategy_code_sha256': '1' * 64,
        'parameter_sha256': '2' * 64,
        'universe_sha256': '3' * 64,
        'factor_definition_sha256': '4' * 64,
        'calendar_sha256': '5' * 64,
        'formal_artifact_sha256': mod.canonical_sha256(formal),
        'liquidity_threshold_cny': 80_000_000,
        'formal_end': '2026-04-17',
        'frozen': True,
    }


def valid_scope(model):
    return {
        'artifact': 'OOS_SCOPE_V482',
        'version': 'V4.82',
        'formal_end': '2026-04-17',
        'oos_start': '2026-04-18',
        'oos_end': '2026-09-08',
        'calendar_sha256': model['calendar_sha256'],
        'universe_sha256': model['universe_sha256'],
        'model_freeze_sha256': mod.canonical_sha256(model),
        'scope_frozen': True,
    }


class OosAdmissionV482Tests(unittest.TestCase):
    def _triplet(self):
        formal = valid_formal()
        model = valid_model(formal)
        scope = valid_scope(model)
        return formal, model, scope

    def test_valid_frozen_package_is_admitted(self):
        formal, model, scope = self._triplet()
        out = mod.evaluate(formal, model, scope)
        self.assertEqual(out['status'], 'OOS_ADMITTED_V482')
        self.assertEqual(out['blockers'], [])
        self.assertTrue(out['oos_metrics_allowed'])
        self.assertEqual(out['formal_artifact_sha256'], mod.canonical_sha256(formal))
        self.assertEqual(out['model_freeze_sha256'], mod.canonical_sha256(model))
        self.assertEqual(out['oos_scope_sha256'], mod.canonical_sha256(scope))

    def test_upstream_oos_already_open_is_blocked(self):
        formal, model, scope = self._triplet()
        formal['oos_metrics_allowed'] = True
        model['formal_artifact_sha256'] = mod.canonical_sha256(formal)
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('UPSTREAM_OOS_ALREADY_OPEN', out['blockers'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_formal_checkpoint_change_is_blocked(self):
        formal, model, scope = self._triplet()
        formal['checkpoint']['PASS'] = 843
        model['formal_artifact_sha256'] = mod.canonical_sha256(formal)
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('FORMAL_ARTIFACT_INVALID', out['blockers'])

    def test_formal_max_diff_above_5bp_is_blocked(self):
        formal, model, scope = self._triplet()
        formal['max_full_path_diff_bp'] = 5.000001
        model['formal_artifact_sha256'] = mod.canonical_sha256(formal)
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('FORMAL_ARTIFACT_INVALID', out['blockers'])

    def test_formal_hash_mismatch_is_blocked(self):
        formal, model, scope = self._triplet()
        model['formal_artifact_sha256'] = 'a' * 64
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('FORMAL_HASH_MISMATCH', out['blockers'])

    def test_invalid_model_sha_is_blocked(self):
        formal, model, scope = self._triplet()
        model['strategy_code_sha256'] = 'xyz'
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('MODEL_FREEZE_INVALID', out['blockers'])

    def test_model_not_frozen_is_blocked(self):
        formal, model, scope = self._triplet()
        model['frozen'] = False
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('MODEL_NOT_FROZEN', out['blockers'])

    def test_oos_start_must_be_strictly_after_formal_end(self):
        formal, model, scope = self._triplet()
        scope['oos_start'] = '2026-04-17'
        out = mod.evaluate(formal, model, scope)
        self.assertIn('OOS_WINDOW_OVERLAP', out['blockers'])

    def test_oos_end_before_start_is_blocked(self):
        formal, model, scope = self._triplet()
        scope['oos_start'] = '2026-04-20'
        scope['oos_end'] = '2026-04-19'
        out = mod.evaluate(formal, model, scope)
        self.assertIn('OOS_SCOPE_INVALID', out['blockers'])

    def test_calendar_hash_mismatch_is_blocked(self):
        formal, model, scope = self._triplet()
        scope['calendar_sha256'] = '6' * 64
        out = mod.evaluate(formal, model, scope)
        self.assertIn('CALENDAR_HASH_MISMATCH', out['blockers'])

    def test_universe_hash_mismatch_is_blocked(self):
        formal, model, scope = self._triplet()
        scope['universe_sha256'] = '7' * 64
        out = mod.evaluate(formal, model, scope)
        self.assertIn('UNIVERSE_HASH_MISMATCH', out['blockers'])

    def test_model_freeze_hash_mismatch_is_blocked(self):
        formal, model, scope = self._triplet()
        scope['model_freeze_sha256'] = '8' * 64
        out = mod.evaluate(formal, model, scope)
        self.assertIn('MODEL_FREEZE_HASH_MISMATCH', out['blockers'])

    def test_nested_forbidden_metric_field_is_blocked(self):
        formal, model, scope = self._triplet()
        scope['nested'] = {'safe': [{'metrics': {'sharpe': 2.0}}]}
        out = mod.evaluate(formal, model, scope)
        self.assertIn('FORBIDDEN_OOS_METRIC_FIELD', out['blockers'])
        self.assertFalse(out['data_isolation_pass'])

    def test_canonical_hash_is_stable_across_key_order_and_whitespace(self):
        a = {'z': 1, 'nested': {'b': 2, 'a': '中文'}}
        b = json.loads('{\n  "nested": {"a": "中文", "b": 2},\n  "z": 1\n}')
        self.assertEqual(mod.canonical_sha256(a), mod.canonical_sha256(b))

    def test_missing_model_file_emits_blocked(self):
        formal, model, scope = self._triplet()
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            formal_path = root / 'formal.json'
            scope_path = root / 'scope.json'
            formal_path.write_text(json.dumps(formal), encoding='utf-8')
            scope_path.write_text(json.dumps(scope), encoding='utf-8')
            out = mod.run_paths(formal_path, root / 'missing-model.json', scope_path)
        self.assertEqual(out['status'], 'OOS_BLOCKED_V482')
        self.assertIn('MODEL_FREEZE_INVALID', out['blockers'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_missing_scope_file_emits_blocked(self):
        formal, model, scope = self._triplet()
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            formal_path = root / 'formal.json'
            model_path = root / 'model.json'
            formal_path.write_text(json.dumps(formal), encoding='utf-8')
            model_path.write_text(json.dumps(model), encoding='utf-8')
            out = mod.run_paths(formal_path, model_path, root / 'missing-scope.json')
        self.assertEqual(out['status'], 'OOS_BLOCKED_V482')
        self.assertIn('OOS_SCOPE_INVALID', out['blockers'])

    def test_malformed_formal_json_emits_blocked(self):
        formal, model, scope = self._triplet()
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            formal_path = root / 'formal.json'
            model_path = root / 'model.json'
            scope_path = root / 'scope.json'
            formal_path.write_text('{bad json', encoding='utf-8')
            model_path.write_text(json.dumps(model), encoding='utf-8')
            scope_path.write_text(json.dumps(scope), encoding='utf-8')
            out = mod.run_paths(formal_path, model_path, scope_path)
        self.assertEqual(out['status'], 'OOS_BLOCKED_V482')
        self.assertIn('FORMAL_ARTIFACT_INVALID', out['blockers'])

    def test_unknown_model_field_is_blocked(self):
        formal, model, scope = self._triplet()
        model['extra_field'] = 'not allowed'
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('MODEL_FREEZE_INVALID', out['blockers'])

    def test_current_trade_or_st_overlay_violation_is_blocked(self):
        formal, model, scope = self._triplet()
        formal['market_data']['current_trade_violation_n'] = 1
        formal['market_data']['st_overlay_violation_n'] = 1
        model['formal_artifact_sha256'] = mod.canonical_sha256(formal)
        scope['model_freeze_sha256'] = mod.canonical_sha256(model)
        out = mod.evaluate(formal, model, scope)
        self.assertIn('FORMAL_ARTIFACT_INVALID', out['blockers'])


if __name__ == '__main__':
    unittest.main()
