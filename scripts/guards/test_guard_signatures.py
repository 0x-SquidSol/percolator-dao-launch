"""Signatures are checked like any other text (issue #26). Their data is
random, so a short private pattern can match it by chance; such a match is
excused only for a genuine signature, in exactly ssh-keygen's form, by a key
pinned in gitfiles.SIGNING_KEYS. Made-up, altered or unpinned signatures are
checked in full, so they can't hide text.

The tests sign with a temporary key and pin it through a small driver that
sets SIGNING_KEYS before running the guard, so the guard itself has no
setting that could pin a key.
"""
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "guard.py")
GOOD = "dev@percolator.trade"
DRIVER = """import runpy, sys
guard = runpy.run_path(sys.argv[1], run_name="guard_under_test")
guard["gitfiles"].SIGNING_KEYS = tuple(k for k in sys.argv[2].split("|") if k)
guard["main"]([sys.argv[1]] + sys.argv[3:])
"""
KEYGEN = shutil.which("ssh-keygen")


def random_word(lines):
    """8 letters or digits from the random part of an ed25519 signature's
    base64 lines: the 64 signature bytes fill its last ~86 characters, while
    the start (magic, key, namespace) is the same in every signature."""
    tail = [lines[-2][-60:], lines[-1]]
    return next(run for line in tail for run in re.findall(r"[A-Za-z0-9]{8}", line))


def load_gitfiles():
    """gitfiles.py compiled from its source (never cached bytecode)."""
    sys.modules.setdefault("textscan", _load("textscan"))
    return _load("gitfiles")


def _load(name):
    path = os.path.join(HERE, name + ".py")
    module = type(sys)(name)
    module.__file__ = path
    with open(path, "rb") as handle:
        exec(compile(handle.read(), path, "exec", dont_inherit=True), module.__dict__)
    return module


class PinnedKeysTest(unittest.TestCase):
    def test_pinned_entries_are_bare_ed25519_keys(self):
        # No comment, principal or email: only the public key itself.
        keys = load_gitfiles().SIGNING_KEYS
        self.assertTrue(keys)
        for key in keys:
            self.assertRegex(key, r"^ssh-ed25519 [A-Za-z0-9+/]{68}$")
            blob = base64.b64decode(key.split()[1])
            self.assertEqual(blob[:15], b"\0\0\0\x0bssh-ed25519")
            self.assertEqual(len(blob), 51)


@unittest.skipUnless(KEYGEN, "ssh-keygen not installed")
class SignatureTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.keys = tempfile.mkdtemp()  # outside the repository
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.key = os.path.join(self.keys, "key")
        subprocess.run([KEYGEN, "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", self.key],
                       check=True, capture_output=True)
        with open(self.key + ".pub", encoding="ascii") as handle:
            self.public = " ".join(handle.read().split()[:2])
        self.git("init", "-q")
        for name, value in (("user.name", "Test"), ("user.email", GOOD),
                            ("gpg.format", "ssh"), ("user.signingKey", self.key)):
            self.git("config", name, value)
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        self.parent = self.git("rev-parse", "HEAD")
        result = subprocess.run(["git", "commit", "-q", "--allow-empty", "-S", "-m", "docs: ok"],
                                cwd=self.dir, capture_output=True, env=self.env)
        if result.returncode != 0:
            self.skipTest("git could not sign with ssh-keygen here")
        self.signed = self.git("rev-parse", "HEAD")
        self.raw = self.git("cat-file", "commit", self.signed, text=False)
        # A pattern that surely matches this signature's random data, as a
        # chance match would.
        head = self.raw.split(b"\n\n", 1)[0].decode()
        self.word = random_word([line[1:] for line in head.split("\n")
                                 if line.startswith(" ") and "-----" not in line])
        self.env["GUARD_PATTERNS"] = re.escape(self.word) + "\n"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self.keys, ignore_errors=True)

    def git(self, *args, data=None, text=True):
        out = subprocess.run(["git", *args], cwd=self.dir, input=data, capture_output=True,
                             check=True, env=self.env).stdout
        return out.decode().strip() if text else out

    def guard(self, pinned, *args, stdin=None):
        driver = os.path.join(self.keys, "driver.py")
        with open(driver, "w", encoding="utf-8") as handle:
            handle.write(DRIVER)
        return subprocess.run(
            [sys.executable, "-I", driver, GUARD, "|".join(pinned), *args], cwd=self.dir,
            input=stdin, capture_output=True, text=True, env=self.env)

    def checks(self, sha, pinned):
        """The CI history scan and the pre-push check of a branch at sha."""
        return (self.guard(pinned, "commits", f"{self.parent}..{sha}"),
                self.guard(pinned, "pre-push",
                           stdin=f"refs/heads/main {sha} refs/heads/main {self.parent}\n"))

    def assert_allowed(self, sha, pinned):
        for result in self.checks(sha, pinned):
            self.assertEqual(result.returncode, 0, result.stderr)

    def assert_blocked(self, sha, pinned, why="signature"):
        for result in self.checks(sha, pinned):
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn(why, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn(self.word, result.stderr)

    def rewrite(self, old, new):
        """The signed commit with part of its stored bytes replaced."""
        self.assertIn(old, self.raw)
        return self.git("hash-object", "-t", "commit", "-w", "--stdin", "--literally",
                        data=self.raw.replace(old, new, 1))

    def test_chance_match_in_genuine_pinned_signature_allowed(self):
        self.assert_allowed(self.signed, [self.public])

    def test_unpinned_key_checked_in_full(self):
        self.assert_blocked(self.signed, [])
        other = load_gitfiles().SIGNING_KEYS
        self.assert_blocked(self.signed, list(other))

    def test_altered_payload_not_excused(self):
        # Same signature, different commit: it no longer verifies.
        self.assert_blocked(self.rewrite(b"docs: ok", b"docs: ox"), [self.public])

    def test_rewrapped_signature_not_excused(self):
        # ssh-keygen accepts other line widths; only its own form is excused.
        head = self.raw.split(b"\n\n", 1)[0]
        lines = [line for line in head.split(b"\n") if line.startswith(b" ")]
        data = b"".join(line[1:] for line in lines[:-1])
        rewrapped = b"\n".join(b" " + data[i:i + 64] for i in range(0, len(data), 64))
        self.assert_blocked(self.rewrite(b"\n".join(lines[:-1]), rewrapped), [self.public])

    def test_non_canonical_signature_not_excused(self):
        # S + L verifies too, but ssh-keygen never writes it.
        head = self.raw.split(b"\n\n", 1)[0]
        lines = [line for line in head.split(b"\n") if line.startswith(b" ")][:-1]
        blob = bytearray(base64.b64decode(b"".join(line[1:] for line in lines)))
        order = 2**252 + 27742317777372353535851937790883648493
        s = int.from_bytes(blob[-32:], "little")
        blob[-32:] = (s + order).to_bytes(32, "little")
        data = base64.b64encode(bytes(blob))
        twin = b"\n".join(b" " + data[i:i + 70] for i in range(0, len(data), 70))
        sha = self.rewrite(b"\n".join(lines), twin)
        # A word from the twin's own data, so the check really meets it.
        self.word = random_word([line[1:] for line in twin.decode().split("\n")])
        self.env["GUARD_PATTERNS"] = re.escape(self.word) + "\n"
        self.assert_blocked(sha, [self.public])

    def test_text_after_the_signature_not_excused(self):
        # ssh-keygen ignores text after the end line; it could hide anything.
        end = b" -----END SSH SIGNATURE-----"
        self.assert_blocked(self.rewrite(end, end + b"\n " + self.word.encode()), [self.public])

    def test_second_signature_header_not_excused(self):
        # git joins repeated gpgsig headers, so neither copy is excused.
        head, message = self.raw.split(b"\n\n", 1)
        lines = head.split(b"\n")
        start = next(i for i, line in enumerate(lines) if line.startswith(b"gpgsig "))
        block = [lines[start]] + [line for line in lines[start + 1:] if line.startswith(b" ")]
        doubled = b"\n".join(lines + block) + b"\n\n" + message
        sha = self.git("hash-object", "-t", "commit", "-w", "--stdin", "--literally", data=doubled)
        self.assert_blocked(sha, [self.public])

    def test_genuine_signed_tag_allowed(self):
        self.git("tag", "-s", "-m", "release", "v1", self.parent)
        tag = self.git("rev-parse", "v1")
        raw = self.git("cat-file", "tag", tag, text=False)
        block = raw.split(b"-----BEGIN SSH SIGNATURE-----\n", 1)[1].decode()
        lines = block.split("-----END SSH SIGNATURE-----", 1)[0].split()
        self.env["GUARD_PATTERNS"] = re.escape(random_word(lines)) + "\n"
        push = f"refs/tags/v1 {tag} refs/tags/v1 {'0' * 40}\n"
        self.assertEqual(self.guard([self.public], "pre-push", stdin=push).returncode, 0)
        result = self.guard([], "pre-push", stdin=push)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("signature", result.stderr)


class SplitTest(unittest.TestCase):
    def test_tag_split_at_the_last_signature_start(self):
        gitfiles = load_gitfiles()
        raw = (b"object x\n\nrelease\n-----BEGIN SSH SIGNATURE-----\nAAAA\n"
               b"-----END SSH SIGNATURE-----\n-----BEGIN PGP SIGNATURE-----\n\nBBBB\n"
               b"-----END PGP SIGNATURE-----\n")
        payload, signature = gitfiles.split_signed_tag(raw)
        self.assertTrue(signature.startswith(b"-----BEGIN PGP SIGNATURE-----"))
        self.assertIn(b"AAAA", payload)
        self.assertEqual(gitfiles.split_signed_tag(b"object x\n\nrelease\n"),
                         (b"object x\n\nrelease\n", b""))


if __name__ == "__main__":
    unittest.main()
