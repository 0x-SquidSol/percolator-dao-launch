"""Self-tests for the leak guards: every guard must block a planted example."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.py")
TEST_PATTERNS = "# test patterns\nZZTEST-\\d{2}\ncanary-zz-0000\n"
SECRET_KEY = "[" + ", ".join(["7"] * 64) + "]"


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.git("init", "-q")
        self.git("checkout", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "dev@percolator.trade")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = TEST_PATTERNS

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.dir, capture_output=True, check=check)

    def write(self, path, text):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full) or self.dir, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        return full

    def stage(self, path, text):
        self.write(path, text)
        self.git("add", "-f", path)

    def guard(self, *args, env=None):
        return subprocess.run(
            [sys.executable, GUARD, *args],
            cwd=self.dir, capture_output=True, text=True, env=env or self.env,
        )

    def assertBlocked(self, result):
        self.assertNotEqual(result.returncode, 0, result.stderr)

    def assertAllowed(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    # --- staged changes ---

    def test_clean_change_allowed(self):
        self.stage("src/lib.rs", "pub fn add(a: u64, b: u64) -> u64 { a + b }\n")
        self.assertAllowed(self.guard("staged"))

    def test_private_file_name_blocked(self):
        self.stage("docs/notes.private.md", "hello\n")
        self.assertBlocked(self.guard("staged"))

    def test_private_folder_blocked(self):
        self.stage("private/notes.txt", "hello\n")
        self.assertBlocked(self.guard("staged"))

    def test_keypair_file_blocked(self):
        self.stage("keys/deploy-keypair.json", "[]\n")
        self.assertBlocked(self.guard("staged"))

    def test_wallet_file_blocked(self):
        self.stage("id.json", "[]\n")
        self.assertBlocked(self.guard("staged"))

    def test_env_file_blocked(self):
        self.stage(".env.local", "RPC=x\n")
        self.assertBlocked(self.guard("staged"))

    def test_env_example_allowed(self):
        self.stage(".env.example", "RPC_URL=\n")
        self.assertAllowed(self.guard("staged"))

    def test_secret_key_content_blocked(self):
        self.stage("config/settings.json", '{"key": ' + SECRET_KEY + "}\n")
        self.assertBlocked(self.guard("staged"))

    def test_private_pattern_in_content_blocked(self):
        self.stage("src/lib.rs", "// see ZZTEST-12\n")
        self.assertBlocked(self.guard("staged"))

    def test_canary_in_copied_text_blocked(self):
        self.stage("docs/copy.md", "text canary-zz-0000 text\n")
        self.assertBlocked(self.guard("staged"))

    def test_private_pattern_in_file_name_blocked(self):
        self.stage("docs/ZZTEST-12.md", "hello\n")
        self.assertBlocked(self.guard("staged"))

    def test_personal_email_blocked(self):
        self.git("config", "user.email", "someone@example.com")
        self.stage("src/lib.rs", "fn f() {}\n")
        self.assertBlocked(self.guard("staged"))

    def test_noreply_email_allowed(self):
        self.git("config", "user.email", "1+someone@users.noreply.github.com")
        self.stage("src/lib.rs", "fn f() {}\n")
        self.assertAllowed(self.guard("staged"))

    def test_missing_patterns_blocked(self):
        env = {k: v for k, v in self.env.items() if k != "GUARD_PATTERNS"}
        self.stage("src/lib.rs", "fn f() {}\n")
        self.assertBlocked(self.guard("staged", env=env))

    def test_output_never_echoes_matched_text(self):
        self.stage("src/lib.rs", "// see ZZTEST-12 and canary-zz-0000\n")
        result = self.guard("staged")
        self.assertBlocked(result)
        self.assertNotIn("ZZTEST", result.stderr)
        self.assertNotIn("canary", result.stderr)

    # --- commit message and branch ---

    def test_clean_message_allowed(self):
        path = self.write("msg.txt", "feat: add thing\n")
        self.assertAllowed(self.guard("message", path))

    def test_private_pattern_in_message_blocked(self):
        path = self.write("msg.txt", "feat: add thing (ZZTEST-04)\n")
        self.assertBlocked(self.guard("message", path))

    def test_message_read_in_configured_encoding(self):
        # git stores the message bytes as written and declares
        # i18n.commitEncoding for them; in EBCDIC no usual view reads them.
        path = os.path.join(self.dir, "msg.txt")
        with open(path, "wb") as handle:
            handle.write("feat: add thing (ZZTEST-04)\n".encode("cp500"))
        self.assertAllowed(self.guard("message", path))
        self.git("config", "i18n.commitEncoding", "cp500")
        result = self.guard("message", path)
        self.assertBlocked(result)
        self.assertIn("declared encoding", result.stderr)
        self.git("config", "i18n.commitEncoding", "no-such-codec")
        result = self.guard("message", self.write("ok.txt", "feat: add thing\n"))
        self.assertBlocked(result)
        self.assertIn("unknown text encoding", result.stderr)

    def test_identity_read_in_configured_encoding(self):
        # Written as raw bytes, so the name is exactly what git stores.
        with open(os.path.join(self.dir, ".git", "config"), "ab") as handle:
            handle.write(b"[user]\n\tname = " + "Dev ZZTEST-04".encode("cp500") + b"\n")
        self.stage("src/lib.rs", "pub fn hello() {}\n")
        self.assertAllowed(self.guard("staged"))
        self.git("config", "i18n.commitEncoding", "cp500")
        result = self.guard("staged")
        self.assertBlocked(result)
        self.assertIn("declared encoding", result.stderr)

    def test_private_pattern_in_branch_blocked(self):
        self.git("checkout", "-q", "-b", "work-zztest-07")
        path = self.write("msg.txt", "feat: add thing\n")
        self.assertBlocked(self.guard("message", path))

    # --- whole tree and history (CI) ---

    def test_tree_scan_blocks_tracked_leak(self):
        self.stage("README.md", "canary-zz-0000\n")
        self.assertBlocked(self.guard("tree"))

    def test_commits_scan_blocks_personal_email(self):
        self.git("config", "user.email", "someone@example.com")
        self.stage("README.md", "hello\n")
        self.git("commit", "-q", "-m", "docs: readme")
        self.assertBlocked(self.guard("commits", "HEAD"))

    def test_commits_scan_allows_clean_history(self):
        self.stage("README.md", "hello\n")
        self.git("commit", "-q", "-m", "docs: readme")
        self.assertAllowed(self.guard("commits", "HEAD"))

    # --- the git filter that refuses even forced adds ---

    def test_filter_refuses_forced_add_of_private_file(self):
        self.write(".gitattributes", "*.private.* filter=blockprivate\n")
        self.git("config", "filter.blockprivate.clean", "false")
        self.git("config", "filter.blockprivate.smudge", "cat")
        self.git("config", "filter.blockprivate.required", "true")
        self.write("notes.private.md", "secret\n")
        result = self.git("add", "-f", "notes.private.md", check=False)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
