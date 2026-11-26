"""Regression tests: an annotated tag object's own message, tagger email and
`tag` name must be checked. git log and rev-list peel straight past tag
objects to the commit, so the guards used to never read them.
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
GOOD_EMAIL = "dev@percolator.trade"


class TagObjectTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD_EMAIL)
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        self.head = self.git("rev-parse", "HEAD")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(
            ["git", *args], cwd=self.dir, input=data, capture_output=True,
            check=True, env=self.env,
        ).stdout.decode().strip()

    def tag(self, target, kind="commit", name="v1", email=GOOD_EMAIL, message="release"):
        body = (f"object {target}\ntype {kind}\ntag {name}\n"
                f"tagger Test <{email}> 0 +0000\n\n{message}\n")
        return self.git("hash-object", "-t", "tag", "-w", "--stdin", data=body.encode())

    def pre_push(self, sha, ref="refs/tags/v1"):
        return subprocess.run(
            [sys.executable, LEAK_GUARD, "pre-push"], cwd=self.dir,
            input=f"{ref} {sha} {ref} {ZERO}\n", capture_output=True, text=True, env=self.env,
        )

    def ci_tag_step(self, sha, ref="refs/tags/v1"):
        # The CI step runs `guard.py commits <pushed tag ref>`.
        self.git("update-ref", ref, sha)
        return subprocess.run(
            [sys.executable, LEAK_GUARD, "commits", ref], cwd=self.dir,
            capture_output=True, text=True, env=self.env,
        )

    def assert_blocked(self, sha, why):
        for result in (self.pre_push(sha), self.ci_tag_step(sha)):
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn(why, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_private_text_in_tag_message_blocked(self):
        self.assert_blocked(self.tag(self.head, message="notes ZZTEST-42"), "private pattern")

    def test_personal_tagger_email_blocked(self):
        self.assert_blocked(self.tag(self.head, email="someone@gmail.example"), "email")

    def test_private_tag_name_header_blocked(self):
        # The name inside the tag object can differ from the pushed ref name.
        self.assert_blocked(self.tag(self.head, name="ZZTEST-42"), "private pattern")

    def test_inner_tag_of_a_chain_checked(self):
        inner = self.tag(self.head, message="notes ZZTEST-42")
        outer = self.tag(inner, kind="tag", message="clean outer")
        self.assert_blocked(outer, "private pattern")

    def test_tag_message_in_utf16_blocked(self):
        body = (f"object {self.head}\ntype commit\ntag v1\n"
                f"tagger Test <{GOOD_EMAIL}> 0 +0000\n\n").encode() + "notes ZZTEST-42\n".encode("utf-16")
        sha = self.git("hash-object", "-t", "tag", "-w", "--stdin", "--literally", data=body)
        self.assert_blocked(sha, "private pattern")

    def raw_tag(self, headers):
        body = f"object {self.head}\ntype commit\ntag v1\n{headers}\nrelease\n".encode()
        return self.git("hash-object", "-t", "tag", "-w", "--stdin", "--literally", data=body)

    def test_second_tagger_line_checked(self):
        sha = self.raw_tag(f"tagger Test <{GOOD_EMAIL}> 0 +0000\ntagger Other <someone@gmail.example> 0 +0000\n")
        self.assert_blocked(sha, "email")

    def test_tagger_without_email_refused(self):
        self.assert_blocked(self.raw_tag("tagger Test 0 +0000\n"), "tagger has no email")

    def test_non_utf8_personal_tagger_email_refused(self):
        # Bad bytes must not crash the guard or hide a personal address.
        body = (f"object {self.head}\ntype commit\ntag v1\n").encode() + \
            b"tagger Test <someone\xff@gmail.example> 0 +0000\n\nrelease\n"
        sha = self.git("hash-object", "-t", "tag", "-w", "--stdin", "--literally", data=body)
        self.assert_blocked(sha, "email")

    def test_tag_without_tagger_refused(self):
        self.assert_blocked(self.raw_tag(""), "has no tagger")

    def test_several_tags_in_one_push_all_checked(self):
        clean = self.tag(self.head, name="v1")
        bad = self.tag(self.head, name="v2", message="notes ZZTEST-42")
        lines = f"refs/tags/v1 {clean} refs/tags/v1 {ZERO}\nrefs/tags/v2 {bad} refs/tags/v2 {ZERO}\n"
        result = subprocess.run(
            [sys.executable, LEAK_GUARD, "pre-push"], cwd=self.dir,
            input=lines, capture_output=True, text=True, env=self.env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("private pattern", result.stderr)

    def test_report_never_names_the_tag(self):
        result = self.pre_push(self.tag(self.head, name="zzprivatename", message="notes ZZTEST-42"))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("zzprivatename", result.stderr)

    # Only base64 characters, but containing "ZZ42", which the pattern used
    # in the chance-match test below matches.
    SIG_BASE64 = "iQEzBAABCAAdFiEE+ZZ42/aa+Qx/bb==\nZZ42+x/y\n=AbCd\n"

    def signed_tag(self, signature_body):
        body = (f"object {self.head}\ntype commit\ntag v1\n"
                f"tagger Test <{GOOD_EMAIL}> 0 +0000\n\nrelease\n"
                f"-----BEGIN PGP SIGNATURE-----\n\n{signature_body}"
                "-----END PGP SIGNATURE-----\n")
        return self.git("hash-object", "-t", "tag", "-w", "--stdin", "--literally", data=body.encode())

    def test_match_in_unverified_signature_blocked(self):
        # Signature data is checked like any text. A chance match is excused
        # only for a genuine signature by a pinned key (see
        # test_guard_signatures.py), never for a made-up one like this.
        self.env["GUARD_PATTERNS"] = "\\bZZ\\d{2}\\b\n"
        self.assert_blocked(self.signed_tag(self.SIG_BASE64), "signature")

    def test_clean_signed_tag_allowed(self):
        sha = self.signed_tag("iQEzBAABCAAdFiEE+Qx/bb==\n=AbCd\n")
        self.assertEqual(self.pre_push(sha).returncode, 0, self.pre_push(sha).stderr)

    def test_block_before_the_signature_is_message_text(self):
        # git takes only the last block as the signature, so an earlier one
        # is message text, made with a plain `git tag -a -F`.
        self.env["GUARD_PATTERNS"] = "ZZTEST\\d{2}\n"
        body = (f"object {self.head}\ntype commit\ntag v1\n"
                f"tagger Test <{GOOD_EMAIL}> 0 +0000\n\nrelease\n"
                "-----BEGIN SSH SIGNATURE-----\nU1NIU0lHAAAAAQ\nZZTEST42\n"
                "-----END SSH SIGNATURE-----\n"
                "-----BEGIN PGP SIGNATURE-----\n\niQEzBAABCAAd==\n=AbCd\n"
                "-----END PGP SIGNATURE-----\n")
        sha = self.git("hash-object", "-t", "tag", "-w", "--stdin", data=body.encode())
        result = self.pre_push(sha)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("private pattern", result.stderr)
        self.assertNotIn("signature", result.stderr)  # found in the message
        # The same word in the last block is in the signature: caught too.
        self.assert_blocked(self.signed_tag("ZZTEST42\n=AbCd\n"), "signature")

    def test_text_hidden_inside_signature_block_still_blocked(self):
        # Anything that isn't base64 inside the block keeps it from being
        # skipped, so the whole tag is checked.
        sha = self.signed_tag("iQEzBAAB\nnotes ZZTEST-42 in plain words\n=AbCd\n")
        self.assert_blocked(sha, "private pattern")

    def test_signature_comment_line_checked(self):
        # Armor header lines are free text, so they are kept and checked.
        body = (f"object {self.head}\ntype commit\ntag v1\n"
                f"tagger Test <{GOOD_EMAIL}> 0 +0000\n\nrelease\n"
                "-----BEGIN PGP SIGNATURE-----\nComment: ZZTEST-42\n\n"
                "iQEzBAABCAAd==\n=AbCd\n-----END PGP SIGNATURE-----\n")
        sha = self.git("hash-object", "-t", "tag", "-w", "--stdin", "--literally", data=body.encode())
        self.assert_blocked(sha, "private pattern")

    def test_clean_annotated_tag_allowed(self):
        sha = self.tag(self.head)
        self.assertEqual(self.pre_push(sha).returncode, 0, self.pre_push(sha).stderr)
        self.assertEqual(self.ci_tag_step(sha).returncode, 0)


if __name__ == "__main__":
    unittest.main()
