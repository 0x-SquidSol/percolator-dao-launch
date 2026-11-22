"""Regression tests: a commit's header fields (author and committer names,
mergetag blocks, signatures, extra headers) must be checked, not just its
emails and message. The leak guard used to read only the message.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LEAK_GUARD = os.path.join(HERE, "guard.py")
ZERO = "0" * 40
GOOD = "dev@percolator.trade"


class CommitHeaderTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD)
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        self.parent = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(
            ["git", *args], cwd=self.dir, input=data, capture_output=True,
            check=True, env=self.env,
        ).stdout.decode().strip()

    def commit(self, author="Test", committer="Test", extra="", message="docs: ok"):
        body = (f"tree {self.tree}\nparent {self.parent}\n"
                f"author {author} <{GOOD}> 0 +0000\ncommitter {committer} <{GOOD}> 0 +0000\n"
                f"{extra}\n{message}\n")
        return self.git("hash-object", "-t", "commit", "-w", "--stdin", "--literally",
                        data=body.encode())

    def run_both(self, sha):
        """The pre-push hook's path and CI's history scan."""
        pre_push = subprocess.run(
            [sys.executable, LEAK_GUARD, "pre-push"], cwd=self.dir,
            input=f"refs/heads/main {sha} refs/heads/main {self.parent}\n",
            capture_output=True, text=True, env=self.env,
        )
        history = subprocess.run(
            [sys.executable, LEAK_GUARD, "commits", f"{self.parent}..{sha}"], cwd=self.dir,
            capture_output=True, text=True, env=self.env,
        )
        return pre_push, history

    def assert_blocked(self, sha, why):
        for result in self.run_both(sha):
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn(why, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def assert_allowed(self, sha):
        for result in self.run_both(sha):
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_private_author_name_blocked(self):
        self.assert_blocked(self.commit(author="ZZTEST-42 Smith"), "private pattern")

    def test_private_committer_name_blocked(self):
        self.assert_blocked(self.commit(committer="ZZTEST-42 Smith"), "private pattern")

    def test_mergetag_message_blocked(self):
        mergetag = (f"mergetag object {self.parent}\n type commit\n tag v9\n"
                    f" tagger Test <{GOOD}> 0 +0000\n \n release ZZTEST-42\n")
        self.assert_blocked(self.commit(extra=mergetag), "private pattern")

    def test_mergetag_personal_tagger_email_blocked(self):
        mergetag = (f"mergetag object {self.parent}\n type commit\n tag v9\n"
                    " tagger Test <someone@gmail.example> 0 +0000\n \n release\n")
        self.assert_blocked(self.commit(extra=mergetag), "email")

    def test_extra_header_blocked(self):
        self.assert_blocked(self.commit(extra="x-note ZZTEST-42\n"), "private pattern")

    def test_clean_signed_commit_allowed(self):
        # Signature base64 that happens to contain a short pattern must not
        # block a clean commit (same rule as signed tags).
        self.env["GUARD_PATTERNS"] = "\\bZZ\\d{2}\\b\n"
        gpgsig = ("gpgsig -----BEGIN PGP SIGNATURE-----\n \n"
                  " iQEzBAABCAAdFiEE+ZZ42/aa+Qx/bb==\n =AbCd\n"
                  " -----END PGP SIGNATURE-----\n")
        self.assert_allowed(self.commit(extra=gpgsig))

    def raw_commit(self, header_lines, message=b"docs: ok"):
        body = (f"tree {self.tree}\nparent {self.parent}\n".encode()
                + header_lines + b"\n" + message + b"\n")
        return self.git("hash-object", "-t", "commit", "-w", "--stdin", "--literally", data=body)

    def assert_refused(self, sha, why):
        for result in self.run_both(sha):
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn(why, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_second_author_line_refused(self):
        # git log shows only the first author; a second could hide an address.
        lines = (f"author Test <{GOOD}> 0 +0000\nauthor Other <someone@gmail.example> 0 +0000\n"
                 f"committer Test <{GOOD}> 0 +0000\n").encode()
        self.assert_refused(self.raw_commit(lines), "exactly one author")

    def test_malformed_author_line_refused(self):
        lines = f"author Test no-email 0 +0000\ncommitter Test <{GOOD}> 0 +0000\n".encode()
        self.assert_refused(self.raw_commit(lines), "author or committer")

    def test_every_mergetag_of_an_octopus_merge_checked(self):
        clean = (f"mergetag object {self.parent}\n type commit\n tag v1\n"
                 f" tagger Test <{GOOD}> 0 +0000\n \n release\n")
        bad = (f"mergetag object {self.parent}\n type commit\n tag v2\n"
               f" tagger Test <{GOOD}> 0 +0000\n \n release ZZTEST-42\n")
        self.assert_blocked(self.commit(extra=clean + bad), "mergetag 2")

    def test_declared_encoding_is_read(self):
        # A Shift-JIS name and message: only the declared-encoding view can
        # read them as text.
        self.env["GUARD_PATTERNS"] = "秘密計画\n"
        lines = ("author ".encode() + "秘密計画".encode("shift_jis") + f" <{GOOD}> 0 +0000\n".encode()
                 + f"committer Test <{GOOD}> 0 +0000\nencoding shift_jis\n".encode())
        self.assert_blocked(self.raw_commit(lines), "declared encoding")

    def test_unknown_declared_encoding_refused(self):
        lines = (f"author Test <{GOOD}> 0 +0000\ncommitter Test <{GOOD}> 0 +0000\n"
                 "encoding no-such-codec\n").encode()
        self.assert_refused(self.raw_commit(lines), "unknown text encoding")

    def test_private_author_name_caught_at_commit_time(self):
        # The pre-commit hook checks the configured name, not just the email.
        self.env["GIT_AUTHOR_NAME"] = "ZZTEST-42 Smith"
        self.git("add", "--all")
        result = subprocess.run(
            [sys.executable, LEAK_GUARD, "staged"], cwd=self.dir,
            capture_output=True, text=True, env=self.env,
        )
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("author name", result.stderr)

    def test_report_never_shows_the_name(self):
        result = self.run_both(self.commit(author="ZZTEST-42 Smith"))[0]
        self.assertNotIn("Smith", result.stderr)

    def test_signature_comment_line_checked(self):
        # Armor header lines are free text, so they are kept and checked.
        gpgsig = ("gpgsig -----BEGIN PGP SIGNATURE-----\n Comment: ZZTEST-42\n \n"
                  " iQEzBAABCAAdFiEE+aa/bb==\n =AbCd\n"
                  " -----END PGP SIGNATURE-----\n")
        self.assert_blocked(self.commit(extra=gpgsig), "private pattern")

    def test_non_text_codec_refused_cleanly(self):
        for codec in ("rot13", "base64", "hex"):
            lines = (f"author Test <{GOOD}> 0 +0000\ncommitter Test <{GOOD}> 0 +0000\n"
                     f"encoding {codec}\n").encode()
            self.assert_refused(self.raw_commit(lines), "unknown text encoding")

    def test_empty_author_name_allowed(self):
        lines = f"author <{GOOD}> 0 +0000\ncommitter Test <{GOOD}> 0 +0000\n".encode()
        self.assert_allowed(self.raw_commit(lines))

    def test_empty_author_name_personal_email_blocked(self):
        lines = (f"author <someone@gmail.example> 0 +0000\n"
                 f"committer Test <{GOOD}> 0 +0000\n").encode()
        self.assert_blocked(self.raw_commit(lines), "email")

    def test_show_signature_setting_ignored(self):
        self.git("config", "log.showSignature", "true")
        self.assert_allowed(self.commit())
        self.assert_blocked(self.commit(author="ZZTEST-42 Smith"), "private pattern")

    def test_clean_commit_allowed(self):
        self.assert_allowed(self.commit())


if __name__ == "__main__":
    unittest.main()
