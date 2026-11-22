"""Regression tests: git "replace" refs (and similar stand-ins) must not
change what the guards see. A push sends the real objects, so the guards
must read the real objects too, never a registered stand-in.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LEAK_GUARD = os.path.join(HERE, "guard.py")
PROVENANCE = os.path.join(HERE, "provenance.py")
GOOD = "dev@percolator.trade"
# Built from parts so this file doesn't trip the licence check itself.
MARKER = "BUSL" + "-1.1"


class ReplaceRefTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD)
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        self.base = self.git("rev-parse", "HEAD")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(
            ["git", *args], cwd=self.dir, input=data, capture_output=True,
            check=True, env=self.env,
        ).stdout.decode().strip()

    def commit_with_file(self, content, message="docs: add file"):
        blob = self.git("hash-object", "-w", "--stdin", data=content.encode())
        tree = self.git("mktree", data=f"100644 blob {blob}\tnotes.txt\n".encode())
        return self.git("commit-tree", tree, "-p", self.base, "-m", message)

    def run_tool(self, tool, *args, stdin=None):
        return subprocess.run(
            [sys.executable, tool, *args], cwd=self.dir, input=stdin,
            capture_output=True, text=True, env=self.env,
        )

    def leak_guard_results(self, sha):
        return [
            self.run_tool(LEAK_GUARD, "pre-push",
                          stdin=f"refs/heads/main {sha} refs/heads/main {self.base}\n"),
            self.run_tool(LEAK_GUARD, "commits", f"{self.base}..{sha}"),
        ]

    def assert_blocked(self, results):
        for result in results:
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_replaced_commit_message_still_checked(self):
        bad = self.commit_with_file("ok\n", message="leak ZZTEST-42")
        clean = self.commit_with_file("ok\n")
        self.git("replace", bad, clean)
        self.assert_blocked(self.leak_guard_results(bad))

    def test_replaced_file_content_still_checked(self):
        bad = self.commit_with_file("notes ZZTEST-42\n")
        clean = self.commit_with_file("ok\n")
        self.git("replace", bad, clean)
        self.assert_blocked(self.leak_guard_results(bad))

    def test_replaced_blob_still_checked(self):
        bad = self.commit_with_file("notes ZZTEST-42\n")
        blob = self.git("rev-parse", f"{bad}:notes.txt")
        clean_blob = self.git("hash-object", "-w", "--stdin", data=b"ok\n")
        self.git("replace", "-f", blob, clean_blob)
        self.assert_blocked(self.leak_guard_results(bad))

    def test_replaced_commit_still_checked_for_licence_markers(self):
        bad = self.commit_with_file(f"SPDX-License-Identifier: {MARKER}\n")
        clean = self.commit_with_file("ok\n")
        self.git("replace", bad, clean)
        self.assert_blocked([self.run_tool(PROVENANCE, "commits", f"{self.base}..{bad}")])

    def assert_graft_refused(self, results):
        for result in results:
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn("graft", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def all_history_modes(self, sha):
        return self.leak_guard_results(sha) + [
            self.run_tool(PROVENANCE, "commits", f"{self.base}..{sha}")]

    def test_graft_file_refused(self):
        # Grafts rewrite parent links, so the guard and a push could walk
        # different commits; refuse rather than guess.
        real = self.commit_with_file("ok\n")
        fake = self.commit_with_file("ok\n")
        with open(self.graft_file(), "w") as handle:
            handle.write(f"{real} {fake}\n")
        self.assert_graft_refused(self.all_history_modes(real))

    def graft_file(self):
        path = os.path.join(self.dir, self.git("rev-parse", "--git-path", "info/grafts"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def test_empty_graft_file_refused(self):
        real = self.commit_with_file("ok\n")
        open(self.graft_file(), "w").close()
        self.assert_graft_refused(self.all_history_modes(real))

    def test_graft_file_elsewhere_refused(self):
        real = self.commit_with_file("ok\n")
        elsewhere = os.path.join(self.dir, "elsewhere-grafts")
        with open(elsewhere, "w") as handle:
            handle.write(f"{real}\n")
        self.env["GIT_GRAFT_FILE"] = elsewhere
        self.assert_graft_refused(self.all_history_modes(real))

    def test_replaced_commit_allowed_when_real_one_is_clean(self):
        real = self.commit_with_file("ok\n")
        stand_in = self.commit_with_file("notes ZZTEST-42\n")
        self.git("replace", real, stand_in)
        for result in self.leak_guard_results(real):
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
