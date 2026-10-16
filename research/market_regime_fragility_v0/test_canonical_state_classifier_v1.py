import copy
import unittest

from atomic_evidence_ledger_v1 import validate_and_hash_ledger
from canonical_state_classifier_v1 import CLASSIFIER_VERSION, classify_canonical_state
from state_resolution_v1 import STATE_TO_SCORE


CUTOFF = "2026-10-16T07:00:00+08:00"


def item(value, *, provenance="source:a"):
    return {
        "value": value,
        "observed_at": "2026-10-16T06:59:00+08:00",
        "provenance": provenance,
        "pit_valid": True,
    }


def base_evidence():
    return {
        "external_shock": item("ABSENT"),
        "shock_source_persistence": item("SOURCE_TRANSIENT_REPRICING"),
        "local_transmission_state": item("REALIZED_SHOCK"),
        "breadth_state": item("HEALTHY"),
        "leadership_state": item("HEALTHY"),
        "small_mid_state": item("HEALTHY"),
        "turnover_state": item("HEALTHY"),
        "repair_state": item("NONE"),
    }


def ledger(evidence=None):
    return validate_and_hash_ledger(
        decision_cutoff=CUTOFF,
        evidence=evidence or base_evidence(),
        classifier_version=CLASSIFIER_VERSION,
    )


class CanonicalStateClassifierV1Tests(unittest.TestCase):
    def test_invalid_ledger_fails_closed(self):
        bad = ledger()
        bad["valid"] = False
        result = classify_canonical_state(bad)
        self.assertEqual(result["canonical_market_state"], "UNAVAILABLE")
        self.assertIsNone(result["risk_evidence_score"])
        self.assertFalse(result["full_classifier_resolution_available"])

    def test_explicit_unavailable_evidence_never_becomes_normal(self):
        evidence = base_evidence()
        evidence["breadth_state"]["value"] = "UNAVAILABLE"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "UNAVAILABLE")
        self.assertIn("REQUIRED_EVIDENCE_UNAVAILABLE", result["reason_codes"])

    def test_breadth_divergence_alone_is_watch(self):
        evidence = base_evidence()
        evidence["breadth_state"]["value"] = "DIVERGENT"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "INTERNAL_FRAGILITY_WATCH")
        self.assertEqual(result["risk_evidence_score"], 1)

    def test_two_mild_channels_are_low_severity_fragility(self):
        evidence = base_evidence()
        evidence["breadth_state"]["value"] = "DIVERGENT"
        evidence["leadership_state"]["value"] = "CONCENTRATED"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY")
        self.assertEqual(result["risk_evidence_score"], 2)

    def test_three_severe_channels_are_high_severity_fragility(self):
        evidence = base_evidence()
        evidence["breadth_state"]["value"] = "DETERIORATING"
        evidence["leadership_state"]["value"] = "DETERIORATING"
        evidence["small_mid_state"]["value"] = "STRESSED"
        evidence["turnover_state"]["value"] = "LIQUIDITY_WITHDRAWAL"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY")
        self.assertEqual(result["risk_evidence_score"], 3)

    def test_distribution_plus_broad_deterioration_is_active_de_risking(self):
        evidence = base_evidence()
        evidence["turnover_state"]["value"] = "DISTRIBUTION"
        evidence["breadth_state"]["value"] = "DETERIORATING"
        evidence["small_mid_state"]["value"] = "STRESSED"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "ACTIVE_DE_RISKING")
        self.assertIn("ACTIVE_DISTRIBUTION_CONFIRMED", result["reason_codes"])

    def test_verified_ongoing_pending_shock_is_external_shock(self):
        evidence = base_evidence()
        evidence["external_shock"]["value"] = "VERIFIED"
        evidence["shock_source_persistence"]["value"] = "SOURCE_ONGOING"
        evidence["local_transmission_state"]["value"] = "PENDING_TRANSMISSION"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "EXTERNAL_SHOCK")
        self.assertEqual(result["risk_evidence_score"], STATE_TO_SCORE["EXTERNAL_SHOCK"])

    def test_active_de_risking_has_precedence_over_external_shock(self):
        evidence = base_evidence()
        evidence["external_shock"]["value"] = "VERIFIED"
        evidence["shock_source_persistence"]["value"] = "SOURCE_ESCALATING"
        evidence["local_transmission_state"]["value"] = "IN_TRANSMISSION"
        evidence["turnover_state"]["value"] = "DISTRIBUTION"
        evidence["breadth_state"]["value"] = "DETERIORATING"
        evidence["leadership_state"]["value"] = "DETERIORATING"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "ACTIVE_DE_RISKING")

    def test_broad_repair_resolves_to_repair_without_mutating_source_evidence(self):
        evidence = base_evidence()
        evidence["external_shock"]["value"] = "VERIFIED"
        evidence["shock_source_persistence"]["value"] = "SOURCE_RESOLVING"
        evidence["local_transmission_state"]["value"] = "REPAIRING"
        evidence["repair_state"]["value"] = "BROAD"
        before = copy.deepcopy(evidence)
        ledger_result = ledger(evidence)
        result = classify_canonical_state(ledger_result)
        self.assertEqual(result["canonical_market_state"], "REPAIR")
        self.assertEqual(evidence, before)
        self.assertEqual(
            ledger_result["normalized_evidence"]["shock_source_persistence"]["value"],
            "SOURCE_RESOLVING",
        )

    def test_absent_external_shock_with_ongoing_source_is_contradictory(self):
        evidence = base_evidence()
        evidence["shock_source_persistence"]["value"] = "SOURCE_ONGOING"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "UNAVAILABLE")
        self.assertIn("CONTRADICTORY_REQUIRED_EVIDENCE", result["reason_codes"])

    def test_pending_transmission_with_broad_repair_is_contradictory(self):
        evidence = base_evidence()
        evidence["local_transmission_state"]["value"] = "PENDING_TRANSMISSION"
        evidence["repair_state"]["value"] = "BROAD"
        result = classify_canonical_state(ledger(evidence))
        self.assertEqual(result["canonical_market_state"], "UNAVAILABLE")
        self.assertIn("CONTRADICTORY_REQUIRED_EVIDENCE", result["reason_codes"])

    def test_all_healthy_evidence_is_risk_on(self):
        result = classify_canonical_state(ledger())
        self.assertEqual(result["canonical_market_state"], "NORMAL_RISK_ON")
        self.assertEqual(result["risk_evidence_score"], STATE_TO_SCORE["NORMAL_RISK_ON"])

    def test_classifier_never_authorizes_production(self):
        result = classify_canonical_state(ledger())
        self.assertEqual(result["classifier_version"], CLASSIFIER_VERSION)
        self.assertFalse(result["production_authorized"])


if __name__ == "__main__":
    unittest.main()
