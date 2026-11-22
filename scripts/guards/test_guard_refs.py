"""Regression tests: pushing a ref that points straight at a blob or a tree
(directly or through an annotated tag) must not pass the pre-push checks.
git log / rev-list list nothing for a non-commit object, so the guards used
to see nothing to check and pass it.
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
ZERO = "0" * 40


class NonCommitRefTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "dev@percolator.trade")
        self.git("commit", "-q", "--allow-empty", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(
            ["git", *args], cwd=self.dir, input=data, capture_output=True,
            check=True, env=self.env,
        ).stdout.decode().strip()

    def blob(self, content):
        return self.git("hash-object", "-w", "--stdin", data=content)

    def tree_with(self, blob_sha):
        return self.git("mktree", data=f"100644 blob {blob_sha}\tsecret.txt\n".encode())

    def annotated_tag_of(self, sha, kind):
        tag = (f"object {sha}\ntype {kind}\ntag v1\n"
               "tagger Test <dev@percolator.trade> 0 +0000\n\nrelease\n")
        return self.git("hash-object", "-t", "tag", "-w", "--stdin", data=tag.encode())

    def pre_push(self, sha, ref="refs/tags/v1"):
        return subprocess.run(
            [sys.executable, LEAK_GUARD, "pre-push"], cwd=self.dir,
            input=f"{ref} {sha} {ref} {ZERO}\n", capture_output=True, text=True, env=self.env,
        )

    def provenance_new_ref(self, sha):
        # The pre-push hook passes "<sha> --not --remotes" for a new ref.
        return subprocess.run(
            [sys.executable, PROVENANCE, "commits", sha, "--not", "--remotes"], cwd=self.dir,
            capture_output=True, text=True, env=self.env,
        )

    def assert_blocked(self, result):
        # Refused for the right reason, not by a crash.
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("not a commit", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_leak_guard_tag_to_blob_blocked(self):
        self.assert_blocked(self.pre_push(self.blob(b"notes ZZTEST-42\n")))

    def test_leak_guard_tag_to_tree_blocked(self):
        self.assert_blocked(self.pre_push(self.tree_with(self.blob(b"notes ZZTEST-42\n"))))

    def test_leak_guard_annotated_tag_to_blob_blocked(self):
        blob = self.blob(b"notes ZZTEST-42\n")
        self.assert_blocked(self.pre_push(self.annotated_tag_of(blob, "blob")))

    def test_provenance_tag_to_blob_blocked(self):
        bsl = ('license = "' + "BUSL" + '-1.1"\n').encode()  # built from pieces
        self.assert_blocked(self.provenance_new_ref(self.blob(bsl)))

    def test_provenance_tag_to_tree_blocked(self):
        bsl = ('license = "' + "BUSL" + '-1.1"\n').encode()
        self.assert_blocked(self.provenance_new_ref(self.tree_with(self.blob(bsl))))

    def test_tag_chain_to_blob_blocked(self):
        blob = self.blob(b"notes ZZTEST-42\n")
        inner = self.annotated_tag_of(blob, "blob")
        outer = self.annotated_tag_of(inner, "tag")
        self.assert_blocked(self.pre_push(outer))
        self.assert_blocked(self.provenance_new_ref(outer))

    def test_blob_under_custom_ref_blocked(self):
        self.assert_blocked(self.pre_push(self.blob(b"notes ZZTEST-42\n"), "refs/foo/x"))

    def test_range_ending_at_blob_blocked(self):
        # Updating an existing ref: the hook passes "<remote sha>..<local sha>".
        head = self.git("rev-parse", "HEAD")
        blob = self.blob(b"notes ZZTEST-42\n")
        result = subprocess.run(
            [sys.executable, LEAK_GUARD, "pre-push"], cwd=self.dir,
            input=f"refs/tags/v1 {blob} refs/tags/v1 {head}\n",
            capture_output=True, text=True, env=self.env,
        )
        self.assert_blocked(result)
        self.assert_blocked(subprocess.run(
            [sys.executable, PROVENANCE, "commits", f"{head}..{blob}"], cwd=self.dir,
            capture_output=True, text=True, env=self.env,
        ))

    def test_refusal_does_not_name_the_ref(self):
        result = self.pre_push(self.blob(b"notes ZZTEST-42\n"), "refs/tags/zzprivatename")
        self.assert_blocked(result)
        self.assertNotIn("zzprivatename", result.stderr)

    def test_only_excluded_revisions_refused(self):
        # An unknown name is dropped by git, leaving only "already on the
        # remote" revisions: nothing is being checked, so refuse.
        result = subprocess.run(
            [sys.executable, PROVENANCE, "commits", "nosuchname", "--not", "--all"],
            cwd=self.dir, capture_output=True, text=True, env=self.env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no commit to check", result.stderr)

    def test_annotated_tag_of_commit_allowed(self):
        head = self.git("rev-parse", "HEAD")
        tag = self.annotated_tag_of(head, "commit")
        self.assertEqual(self.pre_push(tag).returncode, 0)
        self.assertEqual(self.provenance_new_ref(tag).returncode, 0)

    def test_clean_commit_push_allowed(self):
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(self.pre_push(head, "refs/heads/main").returncode, 0)
        self.assertEqual(self.provenance_new_ref(head).returncode, 0)


if __name__ == "__main__":
    unittest.main()
