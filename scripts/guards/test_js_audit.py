"""Self-tests for the JavaScript dependency audit gate."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "js_audit.py")

SUMMARY = {"type": "auditSummary", "data": {"vulnerabilities": {}}}


def advisory(ghsa, package="pkg", severity="high", title="A problem"):
    return {
        "type": "auditAdvisory",
        "data": {
            "resolution": {"path": f"top>{package}"},
            "advisory": {
                "id": 1,
                "github_advisory_id": ghsa,
                "module_name": package,
                "severity": severity,
                "title": title,
            },
        },
    }


def entry(ghsa, reason="Reviewed: test tooling only."):
    return {"id": ghsa, "package": "pkg", "severity": "high", "reason": reason}


class JsAuditTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.allowlist = os.path.join(self.dir, "allowlist.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_gate(self, records, entries):
        with open(self.allowlist, "w", encoding="utf-8") as handle:
            json.dump(entries, handle)
        audit = "".join(json.dumps(r) + "\n" for r in records)
        return subprocess.run(
            [sys.executable, GATE, self.allowlist],
            input=audit.encode("utf-8"), capture_output=True,
        )

    def test_all_reviewed_passes(self):
        result = self.run_gate([advisory("GHSA-aaaa"), SUMMARY], [entry("GHSA-aaaa")])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_advisories_passes(self):
        self.assertEqual(self.run_gate([SUMMARY], []).returncode, 0)

    def test_new_advisory_fails(self):
        result = self.run_gate(
            [advisory("GHSA-aaaa"), advisory("GHSA-bbbb"), SUMMARY], [entry("GHSA-aaaa")]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"GHSA-bbbb", result.stderr)
        self.assertNotIn(b"GHSA-aaaa ", result.stderr)

    def test_unfinished_audit_fails_closed(self):
        # No summary line: the audit was cut short (network error, crash, ...).
        result = self.run_gate([advisory("GHSA-aaaa")], [entry("GHSA-aaaa")])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"did not finish", result.stderr)

    def test_empty_output_fails_closed(self):
        self.assertNotEqual(self.run_gate([], []).returncode, 0)

    def test_error_record_fails_closed(self):
        result = self.run_gate([{"type": "error", "data": "boom"}, SUMMARY], [])
        self.assertNotEqual(result.returncode, 0)

    def test_stale_entry_warns_but_passes(self):
        result = self.run_gate([SUMMARY], [entry("GHSA-gone")])
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"GHSA-gone no longer appears", result.stderr)

    def test_entry_without_reason_rejected(self):
        result = self.run_gate([SUMMARY], [entry("GHSA-aaaa", reason=" ")])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"bad allowlist", result.stderr)

    def test_duplicate_entry_rejected(self):
        result = self.run_gate([SUMMARY], [entry("GHSA-aaaa"), entry("GHSA-aaaa")])
        self.assertNotEqual(result.returncode, 0)

    def test_non_ascii_title_does_not_crash(self):
        result = self.run_gate(
            [advisory("GHSA-cccc", title="O(depth²) → slow"), SUMMARY], []
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("GHSA-cccc".encode(), result.stderr)


if __name__ == "__main__":
    unittest.main()
