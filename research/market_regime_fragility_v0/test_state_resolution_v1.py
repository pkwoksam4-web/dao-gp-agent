import unittest

from state_resolution_v1 import resolve_decision_state


class StateResolutionV1Tests(unittest.TestCase):
    def test_theme_confirmed_and_external_shock_can_coexist(self):
        result = resolve_decision_state(
            canonical_market_state="EXTERNAL_SHOCK",
            data_valid=True,
            theme_state="CONFIRMED",
        )
        self.assertEqual(result["risk_evidence_score"], 2)
        self.assertEqual(result["theme_state"], "CONFIRMED")
        self.assertEqual(result["canonical_market_state"], "EXTERNAL_SHOCK")

    def test_active_de_risking_blocks_new_high_beta_but_not_forced_liquidation(self):
        result = resolve_decision_state(
            canonical_market_state="ACTIVE_DE_RISKING",
            data_valid=True,
        )
        self.assertTrue(result["block_new_high_beta_attack"])
        self.assertFalse(result["force_liquidate_all"])
        self.assertEqual(result["risk_evidence_score"], 3)

    def test_pending_transmission_with_ongoing_source_blocks_new_high_beta(self):
        result = resolve_decision_state(
            canonical_market_state="EXTERNAL_SHOCK",
            data_valid=True,
            local_transmission_state="PENDING_TRANSMISSION",
            shock_source_persistence="SOURCE_ONGOING",
        )
        self.assertTrue(result["block_new_high_beta_attack"])

    def test_resolving_source_does_not_trigger_pending_transmission_veto(self):
        result = resolve_decision_state(
            canonical_market_state="REPAIR",
            data_valid=True,
            local_transmission_state="PENDING_TRANSMISSION",
            shock_source_persistence="SOURCE_RESOLVING",
        )
        self.assertFalse(result["block_new_high_beta_attack"])

    def test_overheated_lifecycle_vetoes_chase_without_rewriting_theme(self):
        result = resolve_decision_state(
            canonical_market_state="NORMAL",
            data_valid=True,
            theme_state="CONFIRMED",
            lifecycle_state="OVERHEATED",
        )
        self.assertTrue(result["chase_veto_active"])
        self.assertEqual(result["theme_state"], "CONFIRMED")

    def test_unavailable_data_fails_closed(self):
        result = resolve_decision_state(
            canonical_market_state="NORMAL_RISK_ON",
            data_valid=False,
        )
        self.assertIsNone(result["risk_evidence_score"])
        self.assertFalse(result["full_architecture_approval_available"])
        self.assertEqual(result["reason"], "DATA_UNAVAILABLE")

    def test_unknown_canonical_state_fails_closed(self):
        result = resolve_decision_state(
            canonical_market_state="SOMETHING_NEW",
            data_valid=True,
        )
        self.assertIsNone(result["risk_evidence_score"])
        self.assertFalse(result["full_architecture_approval_available"])
        self.assertEqual(result["reason"], "CANONICAL_STATE_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
