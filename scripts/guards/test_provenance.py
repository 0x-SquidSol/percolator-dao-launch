"""Self-tests for the provenance guard: every marker must be caught."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "provenance.py")


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "dev@percolator.trade")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.dir, capture_output=True, check=True, env=self.env
        )

    def stage(self, path, text):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.git("add", "-f", path)

    def run_guard(self, mode):
        return subprocess.run(
            [sys.executable, GUARD, mode],
            cwd=self.dir, capture_output=True, text=True, env=self.env,
        )

    def assertBlocked(self, path, text):
        self.stage(path, text)
        for mode in ("staged", "tree"):
            result = self.run_guard(mode)
            self.assertNotEqual(result.returncode, 0, mode)
            self.assertIn(path, result.stderr)

    def assertAllowed(self, path, text):
        self.stage(path, text)
        for mode in ("staged", "tree"):
            result = self.run_guard(mode)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_clean_code_allowed(self):
        self.assertAllowed("programs/raise/src/lib.rs", "pub fn hello() {}\n")

    def test_bsl_license_header_blocked(self):
        self.assertBlocked("LICENSE", "Business Source License 1.1\n\nLicensor: MetaDAO LLC\n")

    def test_bsl_spdx_identifier_blocked(self):
        self.assertBlocked("programs/x/Cargo.toml", 'license = "BUSL-1.1"\n')

    def test_additional_use_grant_blocked(self):
        self.assertBlocked("programs/x/src/lib.rs", "// Additional Use Grant: none\n")

    def test_bsl_program_id_blocked(self):
        self.assertBlocked(
            "programs/x/src/lib.rs",
            'declare_id!("FUTARELBfJfQ8RDGhg1wdhddq1odMAJUePHFuBYfUxKq");\n',
        )

    def test_bsl_admin_key_blocked(self):
        self.assertBlocked(
            "scripts/deploy.ts",
            'const admin = "6awyHMshBGVjJ3ozdSJdyyDE1CTAXUwrpNMaRGMsb4sf";\n',
        )

    def test_metadao_npm_package_blocked(self):
        self.assertBlocked(
            "package.json", '{"dependencies": {"@metadaoproject/programs": "1.0.0"}}\n'
        )

    def test_lgpl_v01_program_id_allowed(self):
        # The LGPL v0.1 conditional vault may be used.
        self.assertAllowed(
            "programs/vault/src/lib.rs",
            'declare_id!("vaU1tVLj8RFk7mNj1BxqgAsMKKaL8UvEUHvU3tdbZPe");\n',
        )

    def test_third_party_address_allowed(self):
        # USDC is used by the BSL programs too, but is not MetaDAO's.
        self.assertAllowed(
            "programs/raise/src/constants.rs",
            'pub const USDC: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";\n',
        )

    def test_markdown_skipped(self):
        self.assertAllowed("docs/research.md", "MetaDAO moved to the Business Source License 1.1.\n")

    def test_non_markdown_docs_still_checked(self):
        self.assertBlocked("docs/notes.txt", "Business Source License 1.1\n")

    def test_binary_file_skipped(self):
        self.stage("fixtures/x.bin", "\0Business Source License 1.1")
        self.assertEqual(self.run_guard("staged").returncode, 0)

    # --- commit history (pre-push hook and CI) ---

    def commit(self, path, text, message="change"):
        self.stage(path, text)
        self.git("commit", "-q", "-m", message)

    def run_commits(self, *rev_list_args):
        return subprocess.run(
            [sys.executable, GUARD, "commits", *rev_list_args],
            cwd=self.dir, capture_output=True, text=True, env=self.env,
        )

    def test_clean_history_allowed(self):
        self.commit("src/a.rs", "pub fn a() {}\n")
        self.commit("src/b.rs", "pub fn b() {}\n")
        self.assertEqual(self.run_commits("HEAD").returncode, 0)

    def test_added_then_removed_blocked(self):
        self.commit("src/a.rs", "pub fn a() {}\n")
        self.commit("LICENSE", "Business Source License 1.1\n")
        self.git("rm", "-q", "LICENSE")
        self.git("commit", "-q", "-m", "remove")
        self.assertEqual(self.run_guard("tree").returncode, 0)  # final tree is clean
        result = self.run_commits("HEAD")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LICENSE", result.stderr)

    def test_merge_bringing_material_blocked(self):
        self.commit("src/a.rs", "pub fn a() {}\n")
        self.git("checkout", "-q", "-b", "side")
        self.commit(
            "src/b.rs", 'declare_id!("FUTARELBfJfQ8RDGhg1wdhddq1odMAJUePHFuBYfUxKq");\n'
        )
        self.git("checkout", "-q", "-")
        self.commit("src/c.rs", "pub fn c() {}\n")
        self.git("merge", "-q", "--no-ff", "--no-edit", "side")
        result = self.run_commits("HEAD~1..HEAD")  # only the merge and what it brings
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("src/b.rs", result.stderr)

    def test_range_excludes_older_commits(self):
        self.commit("LICENSE", "Business Source License 1.1\n")
        base = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.commit("src/a.rs", "pub fn a() {}\n")
        self.assertEqual(self.run_commits(f"{base}..HEAD").returncode, 0)

    def test_new_branch_form_allowed(self):
        # The pre-push hook passes "<sha> --not --remotes" for new branches.
        self.commit("src/a.rs", "pub fn a() {}\n")
        self.assertEqual(self.run_commits("HEAD", "--not", "--remotes").returncode, 0)

    def test_unknown_mode_fails(self):
        self.assertNotEqual(self.run_guard("everything").returncode, 0)


if __name__ == "__main__":
    unittest.main()
