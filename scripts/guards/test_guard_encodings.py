"""Leak-guard tests for text in other encodings and inside binary files.

Regression tests: a file with NUL bytes used to skip every content check,
so a private pattern in UTF-16 text (common from Windows tools) or in a
binary file was never caught.
"""
import sys
import unittest

import test_guard as base

PATTERN_TEXT = "meeting notes: ZZTEST-42 launch\r\n"


class EncodingTest(unittest.TestCase):
    setUp = base.GuardTest.setUp
    tearDown = base.GuardTest.tearDown
    git = base.GuardTest.git
    guard = base.GuardTest.guard
    assertBlocked = base.GuardTest.assertBlocked
    assertAllowed = base.GuardTest.assertAllowed

    def stage_bytes(self, path, data):
        import os
        with open(os.path.join(self.dir, path), "wb") as handle:
            handle.write(data)
        self.git("add", "-f", path)

    def assert_blocked_everywhere(self, path, data):
        self.stage_bytes(path, data)
        self.assertBlocked(self.guard("staged"))
        self.git("commit", "-q", "--no-verify", "-m", "docs: notes")
        self.assertBlocked(self.guard("tree"))
        self.assertBlocked(self.guard("commits", "HEAD"))

    def test_utf16_le_with_bom_blocked(self):
        self.assert_blocked_everywhere("notes.txt", PATTERN_TEXT.encode("utf-16"))

    def test_utf16_be_with_bom_blocked(self):
        data = b"\xfe\xff" + PATTERN_TEXT.encode("utf-16-be")
        self.assert_blocked_everywhere("notes.txt", data)

    def test_utf16_le_without_bom_blocked(self):
        self.assert_blocked_everywhere("notes.txt", PATTERN_TEXT.encode("utf-16-le"))

    def test_utf32_blocked(self):
        self.assert_blocked_everywhere("notes.txt", PATTERN_TEXT.encode("utf-32"))

    def test_pattern_inside_binary_blocked(self):
        data = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + PATTERN_TEXT.encode() + b"\0\x01\x02"
        self.assert_blocked_everywhere("image.png", data)

    def test_secret_key_array_in_utf16_blocked(self):
        self.assert_blocked_everywhere("key.txt", base.SECRET_KEY.encode("utf-16"))

    def use_patterns(self, *patterns):
        self.env["GUARD_PATTERNS"] = "\n".join(patterns) + "\n"

    def test_non_ascii_pattern_in_utf16_blocked(self):
        self.use_patterns("ZZcafé")
        self.assert_blocked_everywhere("notes.txt", "notes ZZcafé\r\n".encode("utf-16"))

    def test_cjk_utf16_without_any_nul_blocked(self):
        # CJK-only UTF-16 can contain no NUL bytes at all.
        self.use_patterns("秘密計画")
        data = "秘密計画".encode("utf-16-le")
        self.assertNotIn(b"\0", data)
        self.assert_blocked_everywhere("notes.txt", data)

    def test_utf16_at_odd_offset_inside_binary_blocked(self):
        self.use_patterns("秘密計画")
        data = b"\x07" + "秘密計画".encode("utf-16-le") + b"\0\0\x01"
        self.assert_blocked_everywhere("blob.bin", data)

    def test_cp1252_text_blocked(self):
        self.use_patterns("ZZ’s plan")
        self.assert_blocked_everywhere("notes.txt", "the ZZ’s plan\r\n".encode("cp1252"))

    def test_nul_after_first_8000_bytes_blocked(self):
        data = b"x" * 9000 + PATTERN_TEXT.encode("utf-16-le")
        self.assert_blocked_everywhere("notes.txt", data)

    def test_utf8_bom_with_anchored_pattern_blocked(self):
        self.use_patterns("^ZZBOM")
        self.assert_blocked_everywhere("notes.txt", "ZZBOM first line\n".encode("utf-8-sig"))

    def test_oversized_file_refused(self):
        import textscan
        data = b"a" * (textscan.MAX_SCAN_BYTES + 1)
        self.stage_bytes("big.txt", data)
        result = self.guard("staged")
        self.assertBlocked(result)
        self.assertIn("too large to inspect", result.stderr)

    def test_one_report_per_pattern_outside_utf8(self):
        self.stage_bytes("notes.txt", PATTERN_TEXT.encode("utf-16"))
        result = self.guard("staged")
        self.assertEqual(result.stderr.count("private pattern #1"), 1, result.stderr)

    def test_report_never_shows_matched_text(self):
        self.stage_bytes("notes.txt", PATTERN_TEXT.encode("utf-16"))
        result = self.guard("staged")
        self.assertNotIn("ZZTEST-42", result.stderr + result.stdout)

    def test_cp1252_commit_message_blocked(self):
        # Commit messages are checked from their original bytes too.
        import os
        self.use_patterns("ZZcafé")
        message = os.path.join(self.dir, "msg.txt")
        with open(message, "wb") as handle:
            handle.write("docs: ZZcafé notes\n".encode("cp1252"))
        self.assertBlocked(self.guard("message", message))
        self.stage_bytes("a.txt", b"ok\n")
        self.git("commit", "-q", "--no-verify", "-F", message)
        self.assertBlocked(self.guard("commits", "HEAD"))

    def test_hash_line_in_commit_message_checked(self):
        # git keeps "#" lines with -m, --cleanup=verbatim/whitespace, so the
        # commit-msg hook must not drop them.
        import os
        message = os.path.join(self.dir, "msg.txt")
        with open(message, "wb") as handle:
            handle.write(b"docs: notes\n# ZZTEST-42\n")
        self.assertBlocked(self.guard("message", message))

    def test_guard_runs_in_isolated_python_mode(self):
        # -I leaves the script's folder off the import path; the guard must
        # still find textscan rather than fail to start.
        import subprocess
        import sys
        self.stage_bytes("notes.txt", PATTERN_TEXT.encode("utf-16"))
        result = subprocess.run(
            [sys.executable, "-I", base.GUARD, "staged"],
            cwd=self.dir, capture_output=True, text=True, env=self.env,
        )
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertIn("private pattern #1", result.stderr)

    def test_clean_utf16_allowed(self):
        self.stage_bytes("notes.txt", "ordinary meeting notes\r\n".encode("utf-16"))
        self.assertAllowed(self.guard("staged"))

    def test_clean_binary_allowed(self):
        self.stage_bytes("image.png", b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR\0\x01\x02\xff\xfe")
        self.assertAllowed(self.guard("staged"))


class LineEquivalenceTest(unittest.TestCase):
    """The guard must find every pattern that matches some single line (its
    definition of a match), whatever the line breaks, encoding or regex
    constructs used."""

    PATTERNS = [
        r"secret", r"secret$", r"^secret", r"^secret$", r"\Asecret", r"secret\Z",
        r"(?<!x)secret", r"(?<=\s)secret", r"secret(?=\s)", r"secret(?!y)",
        r"se.ret", r"secret\s*$", r"\bsecret\b", r"s[e]+cret", r"^\s*secret",
        r"(?>secret\s*)$", r"(?s)secret.*$", r"secret[^x]*$",
    ] + ([r"secret\s*+$"] if sys.version_info >= (3, 11) else [])  # possessive: 3.11+
    BREAKS = ["\n", "\r\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " "]

    def per_line(self, pattern, text):
        import re
        p = re.compile(pattern, re.IGNORECASE)
        return any(p.search(line) for line in text.splitlines())

    def test_never_finds_less_than_line_by_line(self):
        import re
        import guard
        texts = []
        for br in self.BREAKS:
            texts += [
                f"a secret{br}b{br}", f"x{br}secret{br}", f"secret{br}", f"{br}secret",
                f"xsecret{br}ysecret", f"a{br} secret {br}z", f"﻿secret{br}tail",
                f"secrety{br}secret{br}", f"x secret{br}", f"secret {br}b{br}",
            ]
        for pattern in self.PATTERNS:
            compiled = [re.compile(pattern, re.IGNORECASE)]
            for text in texts:
                for encoding in ("utf-8", "utf-16", "utf-32"):
                    data = text.encode(encoding)
                    expected = self.per_line(pattern, data.decode(encoding))
                    problems = []
                    guard.check_text("t", data, compiled, problems)
                    found = any("private pattern" in p for p in problems)
                    if expected:
                        self.assertTrue(found, f"{pattern!r} missed in {encoding} {text!r}")


if __name__ == "__main__":
    unittest.main()
