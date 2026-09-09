import pathlib
import unittest

import gp12_share_known_at_v1 as mod


class FormalAnchorProbeGateTests(unittest.TestCase):
    def test_structural_blocker_forces_blocked(self):
        gate = mod.formal_anchor_probe_gate(
            structural_blockers=['SINA_STOCK_STRUCTURE_PAYLOAD_INVALID'],
            binding_blockers=[],
            formal_anchor_change_date='2018-12-31',
            formal_chain_mismatch_n=0,
            pit_verified=True,
        )
        self.assertEqual(gate, 'BLOCKED')

    def test_missing_anchor_forces_blocked(self):
        gate = mod.formal_anchor_probe_gate(
            structural_blockers=[],
            binding_blockers=['SINA_FORMAL_ANCHOR_MISSING'],
            formal_anchor_change_date=None,
            formal_chain_mismatch_n=0,
            pit_verified=False,
        )
        self.assertEqual(gate, 'BLOCKED')

    def test_formal_chain_mismatch_forces_blocked(self):
        gate = mod.formal_anchor_probe_gate(
            structural_blockers=[],
            binding_blockers=['SINA_FORMAL_CHAIN_MATCH_MISSING'],
            formal_anchor_change_date='2018-12-31',
            formal_chain_mismatch_n=1,
            pit_verified=False,
        )
        self.assertEqual(gate, 'BLOCKED')

    def test_false_pit_forces_blocked(self):
        gate = mod.formal_anchor_probe_gate(
            structural_blockers=[],
            binding_blockers=[],
            formal_anchor_change_date='2018-12-31',
            formal_chain_mismatch_n=0,
            pit_verified=False,
        )
        self.assertEqual(gate, 'BLOCKED')

    def test_complete_formal_anchor_chain_passes(self):
        gate = mod.formal_anchor_probe_gate(
            structural_blockers=[],
            binding_blockers=[],
            formal_anchor_change_date='2018-12-31',
            formal_chain_mismatch_n=0,
            pit_verified=True,
        )
        self.assertEqual(gate, 'FORMAL_ANCHOR_PIT_PASS')

    def test_production_workflow_uses_formal_anchor_binding_and_gate(self):
        workflow = (
            pathlib.Path(__file__).resolve().parents[1]
            / '.github'
            / 'workflows'
            / 'gp12-turnover-formal-v1.yml'
        ).read_text(encoding='utf-8')
        self.assertIn('known_mod.bind_formal_anchor_states(', workflow)
        self.assertIn('known_mod.formal_anchor_probe_gate(', workflow)
        self.assertNotIn("gate = known_mod.dual_source_probe_gate(", workflow)


if __name__ == '__main__':
    unittest.main()
