import copy
import unittest

from atomic_evidence_ledger_v1 import LEDGER_VERSION, validate_and_hash_ledger


DECISION_CUTOFF = "2026-10-16T07:00:00+08:00"
CLASSIFIER_VERSION = "CANONICAL_STATE_CLASSIFIER_V1"


def item(value, *, observed_at="2026-10-16T06:59:00+08:00", provenance="source:a", pit_valid=True):
    return {
        "value": value,
        "observed_at": observed_at,
        "provenance": provenance,
        "pit_valid": pit_valid,
    }


def valid_evidence():
    return {
        "external_shock": item("ABSENT"),
        "shock_source_persistence": item("SOURCE_UNVERIFIED"),
        "local_transmission_state": item("REALIZED_SHOCK"),
        "breadth_state": item("HEALTHY"),
        "leadership_state": item("HEALTHY"),
        "small_mid_state": item("HEALTHY"),
        "turnover_state": item("HEALTHY"),
        "repair_state": item("NONE"),
    }


class AtomicEvidenceLedgerV1Tests(unittest.TestCase):
    def test_valid_ledger_is_versioned_and_hashed(self):
        result = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=valid_evidence(),
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertEqual(result["ledger_version"], LEDGER_VERSION)
        self.assertTrue(result["valid"])
        self.assertEqual(result["reason_codes"], [])
        self.assertEqual(len(result["evidence_hash"]), 64)

    def test_hash_is_deterministic_across_input_order(self):
        evidence = valid_evidence()
        reversed_evidence = dict(reversed(list(evidence.items())))
        a = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        b = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=reversed_evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertEqual(a["evidence_hash"], b["evidence_hash"])

    def test_provenance_mutation_changes_hash(self):
        evidence = valid_evidence()
        changed = copy.deepcopy(evidence)
        changed["breadth_state"]["provenance"] = "source:b"
        a = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        b = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=changed,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertNotEqual(a["evidence_hash"], b["evidence_hash"])

    def test_missing_required_field_fails_closed(self):
        evidence = valid_evidence()
        evidence.pop("breadth_state")
        result = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertFalse(result["valid"])
        self.assertIn("breadth_state", result["missing_fields"])
        self.assertIn("REQUIRED_EVIDENCE_UNAVAILABLE", result["reason_codes"])

    def test_invalid_enum_fails_closed(self):
        evidence = valid_evidence()
        evidence["breadth_state"]["value"] = "VERY_GOOD"
        result = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertFalse(result["valid"])
        self.assertIn("breadth_state", result["invalid_fields"])
        self.assertIn("INVALID_ENUM_VALUE", result["reason_codes"])

    def test_empty_provenance_fails_closed(self):
        evidence = valid_evidence()
        evidence["leadership_state"]["provenance"] = ""
        result = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertFalse(result["valid"])
        self.assertIn("leadership_state", result["invalid_fields"])
        self.assertIn("PROVENANCE_MISSING", result["reason_codes"])

    def test_pit_invalid_item_fails_closed(self):
        evidence = valid_evidence()
        evidence["small_mid_state"]["pit_valid"] = False
        result = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertFalse(result["valid"])
        self.assertIn("small_mid_state", result["invalid_fields"])
        self.assertIn("PIT_INVALID_EVIDENCE", result["reason_codes"])

    def test_post_cutoff_observation_fails_closed(self):
        evidence = valid_evidence()
        evidence["turnover_state"]["observed_at"] = "2026-10-16T07:01:00+08:00"
        result = validate_and_hash_ledger(
            decision_cutoff=DECISION_CUTOFF,
            evidence=evidence,
            classifier_version=CLASSIFIER_VERSION,
        )
        self.assertFalse(result["valid"])
        self.assertIn("turnover_state", result["invalid_fields"])
        self.assertIn("STALE_OR_POST_CUTOFF_EVIDENCE", result["reason_codes"])

    def test_naive_or_malformed_timestamp_fails_closed(self):
        for observed_at in ("2026-10-16T06:59:00", "not-a-time"):
            with self.subTest(observed_at=observed_at):
                evidence = valid_evidence()
                evidence["repair_state"]["observed_at"] = observed_at
                result = validate_and_hash_ledger(
                    decision_cutoff=DECISION_CUTOFF,
                    evidence=evidence,
                    classifier_version=CLASSIFIER_VERSION,
                )
                self.assertFalse(result["valid"])
                self.assertIn("repair_state", result["invalid_fields"])
                self.assertIn("INVALID_TIMESTAMP", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
