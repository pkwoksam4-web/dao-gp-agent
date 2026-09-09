from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'gp12_formal_input_readiness_v1.py'
PARAMETERS = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
EVIDENCE = ROOT / 'data' / 'GP12_FORMAL_INPUT_EVIDENCE_V1.json'
FORBIDDEN = {
    'return', 'returns', 'pnl', 'alpha', 'sharpe', 'drawdown', 'hit_rate',
    'win_rate', 'performance', 'metrics',
}


def forbidden_keys(value):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN:
                found.append(str(key))
            found.extend(forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(forbidden_keys(child))
    return found


class FormalInputReadinessCliTests(unittest.TestCase):
    def test_cli_materializes_formal_only_fail_closed_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'GP12_FORMAL_INPUT_READINESS_V1.json'
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    '--parameters', str(PARAMETERS),
                    '--factors', str(FACTORS),
                    '--evidence', str(EVIDENCE),
                    '--out', str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists(), result.stdout + result.stderr)
            report = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(report['artifact'], 'GP12_FORMAL_INPUT_READINESS_V1')
            self.assertEqual(report['formal_end'], '2026-04-17')
            self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
            self.assertEqual(report['validated_families'], ['market_calendar'])
            self.assertEqual(report['ready_factor_ids'], [])
            self.assertEqual(report['blocked_factor_ids'], [f'F{i}' for i in range(1, 13)])
            self.assertFalse(report['candidate_scoring_ready'])
            self.assertFalse(report['candidate_freeze_ready'])
            self.assertFalse(report['real_feature_inputs_validated'])
            self.assertFalse(report['model_freeze_allowed'])
            self.assertFalse(report['oos_metrics_allowed'])
            self.assertEqual(forbidden_keys(report), [])
            self.assertTrue(out.read_bytes().endswith(b'\n'))

    def test_cli_rejects_tampered_production_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = json.loads(EVIDENCE.read_text(encoding='utf-8'))
            evidence['formal_calendar_sha256'] = '1' * 64
            bad = pathlib.Path(tmp) / 'bad-evidence.json'
            bad.write_text(json.dumps(evidence), encoding='utf-8')
            out = pathlib.Path(tmp) / 'out.json'
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    '--parameters', str(PARAMETERS),
                    '--factors', str(FACTORS),
                    '--evidence', str(bad),
                    '--out', str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
