import unittest

from manual_override_ledger_v1 import build_ledger, validate_override_record


VALID_RECORD = {
    "override_id": "OVR-20261016-0001",
    "recorded_at": "2026-10-16T14:30:00+08:00",
    "action_cutoff": "2026-10-16T14:31:00+08:00",
    "scope_type": "SYMBOL",
    "scope_id": "000001.SZ",
    "module_version": "EXAMPLE_MODULE_V1",
    "model_output_hash": "model-output-hash-abc123",
    "original_action": "HOLD",
    "override_action": "REDUCE",
    "reason_code": "RISK_OWNER_DISCRETION",
    "reason_text": "Independent execution-risk concern not represented by the frozen model.",
    "actor_role": "RISK_OWNER",
    "evidence_refs": ["evidence://ticket/1", "evidence://market/2"],
    "production_authorized": False,
}


class ManualOverrideLedgerV1Tests(unittest.TestCase):
    def test_valid_override_is_auditable_and_never_rewrites_model_output(self):
        result = validate_override_record(dict(VALID_RECORD))
        self.assertTrue(result["valid"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual(len(result["record_hash"]), 64)
        self.assertEqual(result["original_action"], "HOLD")
        self.assertEqual(result["override_action"], "REDUCE")
        self.assertFalse(result["production_authorized"])

    def test_override_must_be_recorded_no_later_than_action_cutoff(self):
        record = dict(VALID_RECORD)
        record["recorded_at"] = "2026-10-16T14:32:00+08:00"
        result = validate_override_record(record)
        self.assertFalse(result["valid"])
        self.assertIn("OVERRIDE_RECORDED_AFTER_ACTION_CUTOFF", result["reasons"])

    def test_original_model_identity_and_action_are_required(self):
        record = dict(VALID_RECORD)
        record["model_output_hash"] = ""
        record["original_action"] = ""
        result = validate_override_record(record)
        self.assertFalse(result["valid"])
        self.assertIn("MODEL_OUTPUT_HASH_MISSING", result["reasons"])
        self.assertIn("ORIGINAL_ACTION_MISSING", result["reasons"])

    def test_override_must_change_the_action(self):
        record = dict(VALID_RECORD)
        record["override_action"] = record["original_action"]
        result = validate_override_record(record)
        self.assertFalse(result["valid"])
        self.assertIn("OVERRIDE_ACTION_EQUALS_ORIGINAL", result["reasons"])

    def test_reason_and_actor_role_are_required(self):
        record = dict(VALID_RECORD)
        record["reason_code"] = ""
        record["actor_role"] = ""
        result = validate_override_record(record)
        self.assertFalse(result["valid"])
        self.assertIn("REASON_CODE_MISSING", result["reasons"])
        self.assertIn("ACTOR_ROLE_INVALID", result["reasons"])

    def test_future_outcome_fields_are_forbidden_in_predecision_record(self):
        record = dict(VALID_RECORD)
        record["forward_return_5d"] = 0.12
        result = validate_override_record(record)
        self.assertFalse(result["valid"])
        self.assertIn("FUTURE_OUTCOME_FIELD_FORBIDDEN", result["reasons"])

    def test_hash_is_deterministic_across_evidence_ref_order(self):
        record_a = dict(VALID_RECORD)
        record_b = dict(VALID_RECORD)
        record_b["evidence_refs"] = list(reversed(record_b["evidence_refs"]))
        self.assertEqual(
            validate_override_record(record_a)["record_hash"],
            validate_override_record(record_b)["record_hash"],
        )

    def test_ledger_rejects_duplicate_override_ids(self):
        result = build_ledger([dict(VALID_RECORD), dict(VALID_RECORD)])
        self.assertFalse(result["valid"])
        self.assertIn("DUPLICATE_OVERRIDE_ID", result["reasons"])

    def test_ledger_hash_is_deterministic_across_input_order(self):
        first = dict(VALID_RECORD)
        second = dict(VALID_RECORD)
        second["override_id"] = "OVR-20261016-0002"
        second["recorded_at"] = "2026-10-16T14:30:30+08:00"
        second["scope_id"] = "000002.SZ"
        second["model_output_hash"] = "model-output-hash-def456"
        a = build_ledger([first, second])
        b = build_ledger([second, first])
        self.assertTrue(a["valid"])
        self.assertTrue(b["valid"])
        self.assertEqual(a["ledger_hash"], b["ledger_hash"])
        self.assertEqual(a["override_count"], 2)


if __name__ == "__main__":
    unittest.main()
