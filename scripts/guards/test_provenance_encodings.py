"""Provenance-guard regression tests: text in other encodings, files with
NUL bytes, Markdown license files and different capitalisation must not
slip through."""
import os
import unittest

import test_provenance as base

BSL_HEADER = "Business Source License 1.1\nLicensor: MetaDAO LLC\n"
BSL_ADDRESS = 'declare_id!("FUTARELBfJfQ8RDGhg1wdhddq1odMAJUePHFuBYfUxKq");\n'


class ProvenanceEncodingTest(unittest.TestCase):
    setUp = base.ProvenanceTest.setUp
    tearDown = base.ProvenanceTest.tearDown
    git = base.ProvenanceTest.git
    run_guard = base.ProvenanceTest.run_guard

    def stage_bytes(self, path, data):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full) or self.dir, exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)
        self.git("add", "-f", path)

    def assert_blocked_everywhere(self, path, data):
        self.stage_bytes(path, data)
        for mode in ("staged", "tree"):
            result = self.run_guard(mode)
            self.assertNotEqual(result.returncode, 0, f"{mode}: {path}")
        self.git("commit", "-q", "-m", "x")
        result = base.subprocess.run(
            [base.sys.executable, base.GUARD, "commits", "HEAD"],
            cwd=self.dir, capture_output=True, text=True, env=self.env,
        )
        self.assertNotEqual(result.returncode, 0, f"commits: {path}")

    def test_nul_byte_in_code_file_blocked(self):
        self.assert_blocked_everywhere("programs/x/src/lib.rs", ("// " + BSL_HEADER).encode() + b"\0")

    def test_bsl_text_in_utf16_blocked(self):
        self.assert_blocked_everywhere("LICENSE", BSL_HEADER.encode("utf-16"))

    def test_bsl_address_in_utf16_blocked(self):
        self.assert_blocked_everywhere("programs/x/src/lib.rs", BSL_ADDRESS.encode("utf-16"))

    def test_bsl_address_inside_binary_blocked(self):
        self.assert_blocked_everywhere("fixture.bin", b"\0\x01\x02" + BSL_ADDRESS.encode() + b"\0")

    def test_license_md_blocked(self):
        self.assert_blocked_everywhere("LICENSE.md", BSL_HEADER.encode())

    def test_notice_md_blocked(self):
        self.assert_blocked_everywhere("NOTICE.md", BSL_HEADER.encode())

    def test_nested_license_md_blocked(self):
        self.assert_blocked_everywhere("programs/x/LICENSE.md", BSL_HEADER.encode())

    def test_lower_case_bsl_header_blocked(self):
        self.assert_blocked_everywhere("LICENSE", BSL_HEADER.lower().encode())

    def test_lower_case_spdx_id_blocked(self):
        self.assert_blocked_everywhere("programs/x/Cargo.toml", b'license = "busl-1.1"\n')

    def test_upper_case_additional_use_grant_blocked(self):
        self.assert_blocked_everywhere("programs/x/src/lib.rs", b"// ADDITIONAL USE GRANT: none\n")

    # --- docs that discuss the license (docs/research.md only) ---

    def test_research_doc_loose_mentions_allowed(self):
        self.stage_bytes("docs/research.md", (
            "### 5.1 Current MetaDAO code: Business Source License 1.1\n"
            "- **Production use requires:** an Additional Use Grant from MetaDAO LLC (made\n"
        ).encode())
        for mode in ("staged", "tree"):
            self.assertEqual(self.run_guard(mode).returncode, 0, mode)

    def test_research_doc_license_title_line_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", b"notes\n\nBusiness Source License 1.1\n")

    def test_research_doc_parameter_line_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", b"**Licensed Work:** MetaDAO Programs\n")

    def test_research_doc_table_parameter_line_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", b"| Change License | LGPL |\n")

    def test_ordinary_changelog_lines_allowed(self):
        self.stage_bytes("CHANGELOG.md", (
            "| Version | Change Date |\n|---|---|\n| 0.1 | 2026 |\n"
            "- Change date: 2026-01-01\n"
            "Licensor: Acme Corp (see the MIT license)\n"
            "## Change Date: v0.2\n"
        ).encode())
        for mode in ("staged", "tree"):
            result = self.run_guard(mode)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_bsl_header_still_blocked(self):
        header = (
            "Business Source License 1.1\n\n"
            "License text copyright (c) 2017 MariaDB Corporation Ab, All Rights Reserved.\n\n"
            "Licensor:             MetaDAO LLC\n"
            "Licensed Work:        MetaDAO Programs\n"
            "Additional Use Grant: Any uses approved by MetaDAO LLC\n"
            "Change Date:          4200-06-09\n"
            "Change License:       GNU Lesser General Public License v2.0 or later\n"
        )
        self.stage_bytes("docs/research.md", header.encode())
        result = self.run_guard("staged")
        self.assertNotEqual(result.returncode, 0)
        # Title, copyright, licensor, licensed work, grant and change license lines.
        for line in (1, 3, 5, 6, 7, 9):
            self.assertIn(f"docs/research.md:{line}:", result.stderr)

    def test_research_doc_mariadb_line_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", b"License text copyright (c) 2017 MariaDB Corporation Ab\n")

    def test_research_doc_licensor_metadao_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", b"The text names Licensor: MetaDAO LLC.\n")

    def test_research_doc_full_address_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", BSL_ADDRESS.encode())

    def test_research_doc_npm_package_blocked(self):
        self.assert_blocked_everywhere("docs/research.md", b"yarn add @metadaoproject/programs\n")

    def test_research_doc_in_utf16_blocked(self):
        # The exception only applies to the plain UTF-8 reading.
        data = "MetaDAO moved to the Business Source License 1.1.\n".encode("utf-16")
        self.assert_blocked_everywhere("docs/research.md", data)

    def test_body_only_notice_md_blocked(self):
        body = ("Terms\n\nThe Licensor hereby grants you the right to copy, modify, create\n"
                "derivative works. The Licensor may make an Additional Use Grant, above.\n")
        self.assert_blocked_everywhere("NOTICE.md", body.encode())

    def test_license_named_exception_refused(self):
        import provenance
        for bad in ("docs/LICENSE.md", "docs/notice.txt", "README.md", "programs/x/notes.md"):
            with self.assertRaises(SystemExit):
                provenance.check_exemptions({bad})
        provenance.check_exemptions({"docs/research.md"})

    def test_oversized_file_refused(self):
        import textscan
        self.stage_bytes("big.txt", b"a" * (textscan.MAX_SCAN_BYTES + 1))
        result = self.run_guard("staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("too large to inspect", result.stderr)

    def test_report_never_shows_matched_text(self):
        self.stage_bytes("LICENSE", BSL_HEADER.encode("utf-16"))
        result = self.run_guard("staged")
        self.assertNotIn("Business Source", result.stderr + result.stdout)
        self.assertNotIn("MetaDAO LLC", result.stderr + result.stdout)

    def test_clean_utf16_code_allowed(self):
        self.stage_bytes("programs/x/src/lib.rs", "pub fn hello() {}\n".encode("utf-16"))
        for mode in ("staged", "tree"):
            self.assertEqual(self.run_guard(mode).returncode, 0, mode)


if __name__ == "__main__":
    unittest.main()
