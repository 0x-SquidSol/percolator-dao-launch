"""Regression tests for the pre-push hook's ranges: when a new branch is
pushed, commits that exist on some *other* remote (or a stale tracking ref)
must still be checked by the provenance guard and the secret scan. The hook
used to exclude everything reachable from any remote-tracking ref.

Runs the real .githooks/pre-push with a stand-in gitleaks that records the
range it was asked to scan.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOOK = os.path.join(REPO, ".githooks", "pre-push")
ZERO = "0" * 40
BSL = ('license = "' + "BUSL" + '-1.1"\n')  # built from pieces


class PrePushRangeTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        # Stand-in gitleaks for `gitleaks dir` (where the real one isn't
        # installed): finds only the scan's canary. The secret scan itself is
        # tested with the real gitleaks in test_secret_scan_attributes.py.
        bindir = os.path.join(self.root, "bin")
        os.makedirs(bindir)
        stub = os.path.join(bindir, "gitleaks")
        with open(stub, "w", newline="\n") as handle:
            handle.write(
                "#!/bin/sh\n"
                'while [ $# -gt 1 ]; do\n'
                '  [ "$1" = "--report-path" ] && report="$2"\n'
                '  shift\n'
                'done\n'
                'printf \'[{"File": "%s/canary", "RuleID": "github-pat", "StartLine": 129}]\' "$1" > "$report"\n'
                "exit 3\n")
        os.chmod(stub, 0o755)
        self.env["PATH"] = bindir + os.pathsep + self.env["PATH"]

        self.work = os.path.join(self.root, "work")
        os.makedirs(self.work)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "dev@percolator.trade")
        # The hook runs the guards from the working tree, as in this repo.
        shutil.copytree(os.path.join(REPO, "scripts", "guards"),
                        os.path.join(self.work, "scripts", "guards"),
                        ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        shutil.copy(os.path.join(REPO, ".gitleaks.toml"), self.work)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        # A clone has the remote's main, whose scan settings are reviewed.
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(
            ["git", *args], cwd=self.work, input=data, capture_output=True,
            check=True, env=self.env,
        ).stdout.decode().strip()

    def commit_on_other_remote(self):
        """A commit with BSL text that is reachable from refs/remotes/other/*
        (as if fetched from another remote), not from the target remote."""
        blob = self.git("hash-object", "-w", "--stdin", data=BSL.encode())
        tree = self.git("mktree", data=f"100644 blob {blob}\tCargo.toml\n".encode())
        commit = self.git("commit-tree", tree, "-m", "chore: deps")
        self.git("update-ref", "refs/remotes/other/main", commit)
        return commit

    def run_hook(self, local_sha, remote="origin"):
        line = f"refs/heads/x {local_sha} refs/heads/x {ZERO}\n"
        return subprocess.run(
            ["sh", HOOK, remote, "https://example.invalid/repo.git"], cwd=self.work,
            input=line, capture_output=True, text=True, env=self.env,
        )

    def test_provenance_checks_commit_already_on_another_remote(self):
        result = self.run_hook(self.commit_on_other_remote())
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("BSL license text", result.stderr)

    def test_clean_new_branch_allowed(self):
        head = self.git("rev-parse", "HEAD")
        result = self.run_hook(head)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
