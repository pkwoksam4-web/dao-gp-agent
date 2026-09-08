import base64
import gzip
import io
import json
import pathlib
import tempfile
import unittest

import model_freeze_recovery_v482 as mod


FORMAL_END = '2026-04-17'
OOS_START = '2026-04-18'
OOS_END = '2026-09-08'


def valid_formal():
    return {
        'artifact': 'FORMAL_READINESS_FINAL_V482',
        'version': 'V4.82',
        'formal_ready': True,
        'validated_global_provenance_emitted': True,
        'oos_metrics_allowed': False,
        'universe_n': 847,
        'formal_symbol_n': 844,
        'market_data': {
            'market_data_ready': True,
            'liquidity_threshold_cny': 80_000_000,
        },
    }


def universe_text(n=847):
    rows = [f'{i:06d}.SZ' for i in range(1, n + 1)]
    return '\n'.join(rows) + '\n'


def calendar_payload(dates):
    raw = ('date\n' + '\n'.join(dates) + '\n').encode('utf-8')
    gz = gzip.compress(raw, mtime=0)
    return base64.b64encode(gz).decode('ascii'), gz.hex()


def valid_scope_intent():
    return {
        'artifact': 'OOS_SCOPE_INTENT_V482',
        'version': 'V4.82',
        'formal_end': FORMAL_END,
        'oos_start': OOS_START,
        'oos_end': OOS_END,
        'intent_frozen': True,
        'pre_exposure_confirmed': True,
    }


class ModelFreezeRecoveryV482Tests(unittest.TestCase):
    def test_canonical_json_hash_is_stable(self):
        a = {'b': 2, 'a': {'z': '中文', 'y': 1}}
        b = json.loads('{"a":{"y":1,"z":"中文"},"b":2}')
        self.assertEqual(mod.canonical_json_sha256(a), mod.canonical_json_sha256(b))

    def test_universe_trailing_newline_does_not_change_hash(self):
        a_rows, a_sha = mod.canonical_universe(universe_text())
        b_rows, b_sha = mod.canonical_universe(universe_text().rstrip('\n'))
        self.assertEqual(a_rows, b_rows)
        self.assertEqual(a_sha, b_sha)
        self.assertEqual(len(a_rows), 847)

    def test_universe_count_duplicate_blank_and_order_change_fail(self):
        with self.assertRaises(ValueError):
            mod.canonical_universe(universe_text(846))
        rows = universe_text().splitlines()
        rows[-1] = rows[-2]
        with self.assertRaises(ValueError):
            mod.canonical_universe('\n'.join(rows))
        rows = universe_text().splitlines()
        rows[10] = ''
        with self.assertRaises(ValueError):
            mod.canonical_universe('\n'.join(rows))
        rows = universe_text().splitlines()
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(ValueError):
            mod.canonical_universe('\n'.join(rows), expected_symbols=universe_text().splitlines())

    def test_calendar_representations_must_match(self):
        b64_text, hex_text = calendar_payload(['2026-04-16', '2026-04-17'])
        payload = mod.decode_calendar_representations(b64_text, hex_text)
        self.assertTrue(payload.startswith(b'\x1f\x8b'))
        bad_hex = ('00' + hex_text[2:])
        with self.assertRaises(ValueError):
            mod.decode_calendar_representations(b64_text, bad_hex)

    def test_calendar_parser_requires_strictly_increasing_iso_dates(self):
        b64_text, hex_text = calendar_payload(['2026-04-16', '2026-04-17'])
        dates = mod.parse_calendar_dates(mod.decode_calendar_representations(b64_text, hex_text))
        self.assertEqual(dates, ['2026-04-16', '2026-04-17'])
        bad_b64, bad_hex = calendar_payload(['2026-04-17', '2026-04-16'])
        with self.assertRaises(ValueError):
            mod.parse_calendar_dates(mod.decode_calendar_representations(bad_b64, bad_hex))

    def test_calendar_range_hash_is_exact_and_nonempty(self):
        dates = ['2020-06-01', '2020-06-02', '2026-04-16', '2026-04-17', '2026-04-20']
        selected, digest = mod.calendar_range_sha256(dates, '2020-06-01', '2026-04-17')
        self.assertEqual(selected[0], '2020-06-01')
        self.assertEqual(selected[-1], '2026-04-17')
        self.assertEqual(len(digest), 64)
        with self.assertRaises(ValueError):
            mod.calendar_range_sha256(dates, '2030-01-01', '2030-01-02')

    def test_recovery_checkpoint_missing_strategy_assets_fails_closed(self):
        dates = ['2020-06-01', '2020-06-02', '2026-04-17']
        b64_text, hex_text = calendar_payload(dates)
        out = mod.recover_checkpoint(valid_formal(), universe_text(), b64_text, hex_text)
        self.assertEqual(out['status'], 'MODEL_ASSETS_INCOMPLETE_V482')
        self.assertIn('STRATEGY_CODE_MISSING', out['blockers'])
        self.assertIn('PARAMETER_SET_MISSING', out['blockers'])
        self.assertIn('FACTOR_DEFINITION_MISSING', out['blockers'])
        self.assertIn('OOS_CALENDAR_COVERAGE_MISSING', out['blockers'])
        self.assertFalse(out['model_freeze_allowed'])
        self.assertTrue(out['recoverable']['formal_artifact'])
        self.assertTrue(out['recoverable']['universe'])
        self.assertTrue(out['recoverable']['formal_calendar'])

    def test_wrong_liquidity_rule_is_blocked(self):
        formal = valid_formal()
        formal['market_data']['liquidity_threshold_cny'] = 70_000_000
        b64_text, hex_text = calendar_payload(['2020-06-01', '2026-04-17'])
        out = mod.recover_checkpoint(formal, universe_text(), b64_text, hex_text)
        self.assertIn('LIQUIDITY_RULE_MISMATCH', out['blockers'])

    def test_supplied_strategy_assets_get_real_hashes(self):
        dates = ['2020-06-01', '2026-04-17', '2026-09-08']
        b64_text, hex_text = calendar_payload(dates)
        out = mod.recover_checkpoint(
            valid_formal(), universe_text(), b64_text, hex_text,
            strategy_code_bytes=b'print("gp")\n',
            parameters={'weights': [1, 2, 3]},
            factor_definition={'factors': ['a', 'b']},
        )
        self.assertNotIn('STRATEGY_CODE_MISSING', out['blockers'])
        self.assertNotIn('PARAMETER_SET_MISSING', out['blockers'])
        self.assertNotIn('FACTOR_DEFINITION_MISSING', out['blockers'])
        self.assertEqual(len(out['strategy_assets']['strategy_code_sha256']), 64)
        self.assertEqual(len(out['strategy_assets']['parameter_sha256']), 64)
        self.assertEqual(len(out['strategy_assets']['factor_definition_sha256']), 64)

    def test_incomplete_checkpoint_cannot_promote_model(self):
        with self.assertRaises(ValueError):
            mod.promote_model_freeze({
                'artifact': 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
                'version': 'V4.82',
                'status': 'MODEL_ASSETS_INCOMPLETE_V482',
                'model_freeze_allowed': False,
                'blockers': ['STRATEGY_CODE_MISSING'],
            }, 'GP_V11', 'a' * 64)

    def test_complete_checkpoint_promotes_admission_compatible_model(self):
        checkpoint = {
            'artifact': 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482',
            'version': 'V4.82',
            'status': 'MODEL_ASSETS_COMPLETE_V482',
            'formal_artifact_sha256': '1' * 64,
            'universe_sha256': '2' * 64,
            'formal_calendar_sha256': '3' * 64,
            'liquidity_threshold_cny': 80_000_000,
            'formal_end': FORMAL_END,
            'strategy_assets': {
                'strategy_code_sha256': '4' * 64,
                'parameter_sha256': '5' * 64,
                'factor_definition_sha256': '6' * 64,
            },
            'blockers': [],
            'model_freeze_allowed': True,
        }
        out = mod.promote_model_freeze(checkpoint, 'GP_V11', '7' * 64)
        self.assertEqual(set(out), {
            'artifact', 'version', 'strategy_id', 'strategy_code_sha256',
            'parameter_sha256', 'universe_sha256', 'factor_definition_sha256',
            'calendar_sha256', 'formal_artifact_sha256', 'liquidity_threshold_cny',
            'formal_end', 'frozen',
        })
        self.assertEqual(out['artifact'], 'MODEL_FREEZE_V482')
        self.assertTrue(out['frozen'])

    def test_scope_intent_exact_object_is_valid(self):
        self.assertEqual(mod.validate_scope_intent(valid_scope_intent()), [])

    def test_scope_intent_date_or_preexposure_mutation_is_invalid(self):
        for key, value in [('oos_start', '2026-04-19'), ('oos_end', '2026-09-07'), ('pre_exposure_confirmed', False)]:
            scope = valid_scope_intent()
            scope[key] = value
            self.assertTrue(mod.validate_scope_intent(scope), key)

    def test_scope_intent_rejects_nested_metric_field(self):
        scope = valid_scope_intent()
        scope['extra'] = {'metrics': {'sharpe': 2.0}}
        blockers = mod.validate_scope_intent(scope)
        self.assertIn('FORBIDDEN_OOS_METRIC_FIELD', blockers)
        self.assertIn('SCOPE_INTENT_INVALID', blockers)

    def test_final_scope_inherits_intent_dates_and_model_bindings(self):
        model = {
            'artifact': 'MODEL_FREEZE_V482', 'version': 'V4.82', 'strategy_id': 'GP_V11',
            'strategy_code_sha256': '1' * 64, 'parameter_sha256': '2' * 64,
            'universe_sha256': '3' * 64, 'factor_definition_sha256': '4' * 64,
            'calendar_sha256': '5' * 64, 'formal_artifact_sha256': '6' * 64,
            'liquidity_threshold_cny': 80_000_000, 'formal_end': FORMAL_END, 'frozen': True,
        }
        out = mod.promote_oos_scope(valid_scope_intent(), model, '5' * 64)
        self.assertEqual(out['oos_start'], OOS_START)
        self.assertEqual(out['oos_end'], OOS_END)
        self.assertEqual(out['universe_sha256'], '3' * 64)
        self.assertEqual(out['model_freeze_sha256'], mod.canonical_json_sha256(model))


if __name__ == '__main__':
    unittest.main()
