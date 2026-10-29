"""W1 governance bootstrap contract; standard-library-only, no side effects."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("CHARTER.md", "STATUS.md", "DECISIONS.md", "INTERFACES.md")

def body(name):
    return (ROOT / name).read_text(encoding="utf-8")

class W1GovernanceContract(unittest.TestCase):
    def test_four_canonical_files_exist(self):
        for name in REQUIRED:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file(), name)

    def test_charter_scope_and_owner_only_actions(self):
        doc = body("CHARTER.md")
        for token in ("W1 数据与证据", "DRAFT_NOT_OWNER_RATIFIED",
                      "生产写入", "凭据操作", "合并 PR", "创建 tag", "绕过访问限制"):
            with self.subTest(token=token):
                self.assertIn(token, doc)

    def test_status_is_auditable_and_has_decision_deadlines(self):
        doc = body("STATUS.md")
        for token in ("自上次以来的变化", "NOT_DONE", "NEEDS_OWNER",
                      "INFERRED", "证据", "截止日", "NON_LIVE",
                      "https://github.com/pkwoksam4-web/dao-gp-agent/issues/41"):
            with self.subTest(token=token):
                self.assertIn(token, doc)
        self.assertRegex(doc, r"20\d{2}-\d{2}-\d{2}")

    def test_decisions_do_not_grant_permissions(self):
        doc = body("DECISIONS.md")
        self.assertIn("PENDING_OWNER_DECISION", doc)
        self.assertIn("截止日", doc)
        self.assertIn("不构成授权", doc)

    def test_interface_requires_issues_and_no_cross_workflow_edits(self):
        doc = body("INTERFACES.md")
        self.assertIn("interface issue", doc)
        self.assertIn("不修改其他工作流", doc)
        self.assertIn("provenance", doc)

if __name__ == "__main__":
    unittest.main()
