"""Regression tests: changing a file's type (symlink <-> regular file) must
not let content past the leak guard or the provenance guard. Both used to
list changed files with --diff-filter=ACMR, which leaves out type changes.

Symlinks are written with git plumbing, so the tests work on Windows too.
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
PRIVATE = b"notes ZZTEST-42\n"
# Built from pieces so this file never holds the marker itself and needs no
# exemption from the provenance guard.
BSL = ('license = "' + "BUSL" + '-1.1"\n').encode()


class TypeChangeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "dev@percolator.trade")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(
            ["git", *args], cwd=self.dir, input=data, capture_output=True,
            check=True, env=self.env,
        ).stdout.decode().strip()

    def stage(self, path, mode, content):
        blob = self.git("hash-object", "-w", "--stdin", data=content)
        self.git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}")

    def commit(self, message="x"):
        self.git("commit", "-q", "--no-verify", "-m", message)

    def run_script(self, script, *args):
        return subprocess.run(
            [sys.executable, script, *args], cwd=self.dir,
            capture_output=True, text=True, env=self.env,
        )

    def assert_blocked(self, result):
        self.assertNotEqual(result.returncode, 0, result.stderr)

    def check_both_ways(self, old_mode, old_content, new_mode, new_content, script):
        self.stage("f", old_mode, old_content)
        self.commit("first")
        self.stage("f", new_mode, new_content)
        self.assertEqual(self.git("diff", "--cached", "--name-status"), "T\tf")
        self.assert_blocked(self.run_script(script, "staged"))
        self.commit("type change")
        self.assert_blocked(self.run_script(script, "commits", "HEAD~1..HEAD"))

    def test_leak_guard_symlink_to_file(self):
        self.check_both_ways("120000", b"target.txt", "100644", PRIVATE, LEAK_GUARD)

    def test_leak_guard_file_to_symlink(self):
        # A symlink's target is stored as text, so it can carry a pattern.
        self.check_both_ways("100644", b"ok\n", "120000", PRIVATE.strip(), LEAK_GUARD)

    def test_provenance_symlink_to_file(self):
        self.check_both_ways("120000", b"target.txt", "100644", BSL, PROVENANCE)

    def test_provenance_file_to_symlink(self):
        self.check_both_ways("100644", b"ok\n", "120000", BSL.strip(), PROVENANCE)

    # --- submodules, unmerged entries, tree mode ---

    def test_submodule_refused_by_both_guards(self):
        # Point the gitlink at a commit that exists here, the case that used
        # to print a commit log and pass.
        self.stage("a.txt", "100644", b"ok\n")
        self.commit("first")
        head = self.git("rev-parse", "HEAD")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},sub")
        for script in (LEAK_GUARD, PROVENANCE):
            result = self.run_script(script, "staged")
            self.assert_blocked(result)
            self.assertIn("submodule", result.stderr)
        self.commit("add submodule")
        for script in (LEAK_GUARD, PROVENANCE):
            self.assert_blocked(self.run_script(script, "commits", "HEAD~1..HEAD"))
            self.assert_blocked(self.run_script(script, "tree"))

    def test_unmerged_entry_refused_in_tree_mode(self):
        blob = self.git("hash-object", "-w", "--stdin", data=b"ok\n")
        index_info = "".join(f"100644 {blob} {stage}\tconflict.txt\n" for stage in (1, 2, 3))
        self.git("update-index", "--index-info", data=index_info.encode())
        for script in (LEAK_GUARD, PROVENANCE):
            result = self.run_script(script, "tree")
            self.assert_blocked(result)
            self.assertIn("unmerged", result.stderr)

    def test_tree_mode_checks_symlink_text_as_stored(self):
        self.stage("link", "120000", PRIVATE.strip())
        self.assert_blocked(self.run_script(LEAK_GUARD, "tree"))
        self.stage("link2", "120000", BSL.strip())
        self.assert_blocked(self.run_script(PROVENANCE, "tree"))

    def test_tree_mode_ignores_unstaged_working_tree(self):
        # tree checks what the next commit publishes (the index), so a file
        # on disk that is not staged neither fails nor passes it.
        self.stage("a.txt", "100644", b"ok\n")
        with open(os.path.join(self.dir, "untracked.txt"), "wb") as handle:
            handle.write(PRIVATE)
        self.assertEqual(self.run_script(LEAK_GUARD, "tree").returncode, 0)

    def test_empty_repository_passes(self):
        for script in (LEAK_GUARD, PROVENANCE):
            self.assertEqual(self.run_script(script, "tree").returncode, 0)
            self.assertEqual(self.run_script(script, "staged").returncode, 0)

    def test_non_utf8_file_name_refused_cleanly(self):
        blob = self.git("hash-object", "-w", "--stdin", data=b"ok\n")
        self.git("update-index", "--index-info", data=f"100644 {blob} 0\t".encode() + b"bad\xffname\n")
        for script in (LEAK_GUARD, PROVENANCE):
            for mode in ("staged", "tree"):
                result = self.run_script(script, mode)
                self.assert_blocked(result)
                self.assertIn("not valid UTF-8", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_unmerged_file_reported_once(self):
        blob = self.git("hash-object", "-w", "--stdin", data=b"ok\n")
        index_info = "".join(f"100644 {blob} {stage}\tconflict.txt\n" for stage in (1, 2, 3))
        self.git("update-index", "--index-info", data=index_info.encode())
        result = self.run_script(LEAK_GUARD, "tree")
        self.assertEqual(result.stderr.count("unmerged entry"), 1, result.stderr)

    def test_provenance_refusal_does_not_print_the_name(self):
        self.stage("a.txt", "100644", b"ok\n")
        self.commit("first")
        head = self.git("rev-parse", "HEAD")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},zzprivatename")
        result = self.run_script(PROVENANCE, "staged")
        self.assert_blocked(result)
        self.assertNotIn("zzprivatename", result.stderr)

    def test_clean_type_change_allowed(self):
        self.stage("f", "120000", b"target.txt")
        self.commit("first")
        self.stage("f", "100644", b"ordinary text\n")
        self.assertEqual(self.run_script(LEAK_GUARD, "staged").returncode, 0)
        self.assertEqual(self.run_script(PROVENANCE, "staged").returncode, 0)


if __name__ == "__main__":
    unittest.main()
