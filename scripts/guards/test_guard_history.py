"""Self-tests for the history, ref-name and pre-push guards."""
import subprocess
import sys
import unittest

import test_guard as base

GUARD = base.GUARD

NEW_REF = "0" * 40


class HistoryGuardTest(unittest.TestCase):
    # Borrow GuardTest's helpers (not its tests).
    setUp = base.GuardTest.setUp
    tearDown = base.GuardTest.tearDown
    git = base.GuardTest.git
    write = base.GuardTest.write
    stage = base.GuardTest.stage
    guard = base.GuardTest.guard
    assertBlocked = base.GuardTest.assertBlocked
    assertAllowed = base.GuardTest.assertAllowed

    def commit(self, path, text, message):
        self.stage(path, text)
        self.git("commit", "-q", "-m", message)

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.decode().strip()

    def pre_push(self, line):
        return subprocess.run(
            [sys.executable, GUARD, "pre-push"],
            cwd=self.dir, input=line + "\n", capture_output=True, text=True,
            env=self.env,
        )

    # --- every commit in history, not just the final files ---

    def test_commits_scan_blocks_leak_removed_later(self):
        self.commit("docs/notes.md", "canary-zz-0000\n", "docs: notes")
        self.commit("docs/notes.md", "clean now\n", "docs: tidy notes")
        self.assertAllowed(self.guard("tree"))
        self.assertBlocked(self.guard("commits", "HEAD"))

    def test_commits_scan_blocks_private_file_in_history(self):
        self.commit("keys/deploy-keypair.json", "[]\n", "chore: add file")
        self.git("rm", "-q", "keys/deploy-keypair.json")
        self.git("commit", "-q", "-m", "chore: remove file")
        self.assertBlocked(self.guard("commits", "HEAD"))

    # --- branch and tag names ---

    def test_ref_name_allowed(self):
        self.assertAllowed(self.guard("ref", "refs/heads/raise-core"))

    def test_ref_name_blocked(self):
        self.assertBlocked(self.guard("ref", "refs/heads/zztest-03"))

    def test_tag_name_blocked(self):
        self.assertBlocked(self.guard("ref", "refs/tags/zztest-05"))

    # --- pre-push: checked before anything leaves the computer ---

    def test_pre_push_allows_clean_push(self):
        self.commit("README.md", "hello\n", "docs: readme")
        line = f"refs/heads/main {self.head()} refs/heads/main {NEW_REF}"
        self.assertAllowed(self.pre_push(line))

    def test_pre_push_blocks_private_ref_name(self):
        self.commit("README.md", "hello\n", "docs: readme")
        line = f"refs/heads/main {self.head()} refs/heads/zztest-09 {NEW_REF}"
        self.assertBlocked(self.pre_push(line))

    def test_pre_push_blocks_leak_in_history(self):
        self.commit("docs/a.md", "canary-zz-0000\n", "docs: a")
        self.commit("docs/a.md", "clean\n", "docs: a again")
        line = f"refs/heads/main {self.head()} refs/heads/main {NEW_REF}"
        self.assertBlocked(self.pre_push(line))

    def test_pre_push_checks_only_new_commits(self):
        self.commit("docs/a.md", "hello\n", "docs: a")
        base = self.head()
        self.commit("docs/b.md", "canary-zz-0000\n", "docs: b")
        line = f"refs/heads/main {self.head()} refs/heads/main {base}"
        self.assertBlocked(self.pre_push(line))

    def test_pre_push_ignores_ref_deletion(self):
        line = f"(delete) {NEW_REF} refs/heads/old {NEW_REF}"
        self.assertAllowed(self.pre_push(line))

    # --- file names that match a private pattern are never printed ---

    def test_output_hides_private_file_names(self):
        self.stage("docs/ZZTEST-12.md", "hello\n")
        result = self.guard("staged")
        self.assertBlocked(result)
        self.assertNotIn("ZZTEST", result.stderr)

    def test_history_output_hides_private_file_names(self):
        self.commit("docs/ZZTEST-12.md", "hello\n", "docs: x")
        result = self.guard("commits", "HEAD")
        self.assertBlocked(result)
        self.assertNotIn("ZZTEST", result.stderr)


if __name__ == "__main__":
    unittest.main()
