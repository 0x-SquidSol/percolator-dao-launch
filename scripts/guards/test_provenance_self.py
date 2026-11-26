"""The provenance guard checks its own files like every other file (issue
#24): none is exempt, they hold no marker in one piece, and the only
history they skip is the exact earlier versions listed in HISTORICAL."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))
GUARD = os.path.join(HERE, "provenance.py")
GUARD_FILES = ("provenance.py", "test_provenance.py", "test_provenance_encodings.py")
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# SHA-256 of the sorted address list, one per line, taken before the
# addresses were split into pieces. Adding or changing an address means
# updating the list and this value together.
ADDRESSES_SHA256 = "f7c0a5077dfc08a8945fb36419c17d05d82c51bf87eff29c6435737ff2b5e4ea"


def load_provenance():
    """provenance.py compiled from its source (never cached bytecode)."""
    module = type(sys)("provenance_under_test")
    module.__file__ = GUARD
    with open(GUARD, "rb") as handle:
        exec(compile(handle.read(), GUARD, "exec", dont_inherit=True), module.__dict__)
    return module


provenance = load_provenance()


def git_top(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=TOP, capture_output=True, env=env)


class OwnFilesTest(unittest.TestCase):
    def test_no_path_is_skipped(self):
        self.assertFalse(hasattr(provenance, "SKIPPED"))

    def test_guard_folder_holds_no_marker(self):
        # Every file here as stored in the index, in every view, with no
        # exemption: a marker written out in one piece fails this test.
        listed = git_top("ls-files", "-s", "-z", "--", "scripts/guards")
        self.assertEqual(listed.returncode, 0)
        entries = [e.split("\t", 1) for e in listed.stdout.decode().split("\0") if e]
        names = [name for _, name in entries]
        for name in GUARD_FILES:
            self.assertIn("scripts/guards/" + name, names)
        for meta, name in entries:
            stored = git_top("cat-file", "blob", meta.split()[1])
            self.assertEqual(stored.returncode, 0, name)
            problems = []
            provenance.check(name, stored.stdout, problems)
            self.assertEqual(problems, [], name)

    def test_addresses_are_whole_and_pinned(self):
        addresses = provenance.BSL_ADDRESSES
        self.assertEqual(len(set(addresses)), len(addresses))
        for address in addresses:
            self.assertRegex(address, r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
            number = 0
            for char in address:
                number = number * 58 + BASE58.index(char)
            self.assertLess(number, 2 ** 256)
        digest = hashlib.sha256("\n".join(sorted(addresses)).encode()).hexdigest()
        self.assertEqual(digest, ADDRESSES_SHA256)

    def test_npm_marker_still_matches(self):
        problems = []
        provenance.check("package.json", ("@metadao" + "project/x").encode(), problems)
        self.assertTrue(problems)

    def test_historical_list_is_only_old_guard_files(self):
        # 11 versions existed when the exemption was removed. A failure here
        # after a merge means regenerating the list from every ref, not
        # loosening the check.
        self.assertEqual(len(provenance.HISTORICAL), 11)
        for path, blob in provenance.HISTORICAL:
            self.assertIn(path, ["scripts/guards/" + name for name in GUARD_FILES])
            self.assertRegex(blob, r"^[0-9a-f]{40}$")


class HistoricalVersionsTest(unittest.TestCase):
    """An old version is skipped by `commits` only at its own path and with
    its exact content; `staged` and `tree` never skip it."""

    def setUp(self):
        path, blob = sorted(provenance.HISTORICAL)[0]
        old = git_top("cat-file", "blob", blob)
        if old.returncode != 0:
            self.skipTest("history not fetched (shallow clone)")
        self.path, self.old = path, old.stdout
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "dev@percolator.trade")
        problems = []
        provenance.check(path, self.old, problems)
        self.assertTrue(problems)  # it really spells a marker out

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.dir, capture_output=True, check=True, env=self.env
        )

    def stage(self, path, data):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)
        self.git("add", "-f", path)

    def commit(self, path, data):
        self.stage(path, data)
        self.git("commit", "-q", "-m", "x")

    def run_guard(self, *args):
        return subprocess.run(
            [sys.executable, GUARD, *args],
            cwd=self.dir, capture_output=True, text=True, env=self.env,
        )

    def test_exact_old_version_passes_commits_only(self):
        self.stage(self.path, self.old)
        self.assertNotEqual(self.run_guard("staged").returncode, 0)
        self.git("commit", "-q", "-m", "x")
        self.assertEqual(self.run_guard("commits", "HEAD").returncode, 0)
        self.assertNotEqual(self.run_guard("tree").returncode, 0)

    def test_old_version_at_another_path_blocked(self):
        other = self.path.replace(".py", "_copy.py")
        self.commit(other, self.old)
        result = self.run_guard("commits", "HEAD")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(other, result.stderr)

    def test_changed_old_version_blocked(self):
        self.commit(self.path, self.old + b"\n")
        result = self.run_guard("commits", "HEAD")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(self.path, result.stderr)


if __name__ == "__main__":
    unittest.main()
