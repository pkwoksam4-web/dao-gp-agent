from __future__ import annotations

import json
import pathlib
import unittest

import gp12_status_binding_v1 as sut


class StatusBindingManifestTests(unittest.TestCase):
    def test_repository_manifest_is_the_validated_full_status_binding(self):
        path = pathlib.Path("data/GP12_CANDIDATE_STATUS_BINDING_V1.json")
        binding = json.loads(path.read_text(encoding="utf-8"))
        result = sut.validate_status_binding(binding)
        self.assertEqual(result["family"], "status")
        self.assertEqual(result["panel_rows"], 1_021_953)
        self.assertEqual(result["tradable_rows"], 1_011_607)
        self.assertEqual(result["nontradable_rows"], 10_346)
        self.assertEqual(result["semantic_state"]["upper_limit"], "BOUND_PIT_VERIFIED")
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["model_freeze_allowed"])
        self.assertFalse(result["oos_metrics_allowed"])


if __name__ == "__main__":
    unittest.main()
