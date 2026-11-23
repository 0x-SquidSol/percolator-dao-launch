"""Regression tests: git settings must not hide secrets from the secret
scan. gitleaks used to read git's patch output, so a `-diff` attribute
(committed in .gitattributes or local), a textconv driver, colour codes,
merge or root-commit display, or git's binary detection could hide a secret.
The scan (secretscan.py) now reads the stored bytes instead.

Runs the real hooks and CI's scan with the real gitleaks, so it is skipped
where gitleaks isn't installed, except in CI (REQUIRE_GITLEAKS=1).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GITLEAKS = shutil.which("gitleaks")
REQUIRED = os.environ.get("REQUIRE_GITLEAKS") == "1"
# A fake GitHub token, built from parts so this file doesn't trip the scan.
TOKEN = "ghp_" + "1234567890abcdefghijABCDEFGHIJ123456"
SECRET = 'github_pat = "' + TOKEN + '"\n'
GOOD = "dev@percolator.trade"


sys.path.insert(0, HERE)
import secretscan  # noqa: E402


class LogCheckTest(unittest.TestCase):
    """secretscan.check_log on gitleaks log lines in both platforms' forms
    (Linux logs a plain path unless it has spaces; Windows always quotes)."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def check(self, line):
        try:
            secretscan.check_log(line.encode(), self.root)
            return None
        except SystemExit as stop:
            return str(stop)

    @staticmethod
    def quoted(path):
        return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def skip_line(self, path):
        return f"6:46PM DBG skipping file: global allowlist path={path}"

    def test_skipped_marker_allowed(self):
        marker = os.path.join(self.root, "names", "ab12", "1", "yarn.lock")
        self.assertIsNone(self.check(self.skip_line(marker)))
        self.assertIsNone(self.check(self.skip_line(self.quoted(marker))))

    def test_skipped_content_copy_refused(self):
        content = os.path.join(self.root, "a" * 40)
        for path in (content, self.quoted(content)):
            self.assertIn("skipped a file instead of scanning it", self.check(self.skip_line(path)))

    def test_skipped_file_without_readable_path_refused(self):
        self.assertIn("did not name", self.check("6:46PM DBG skipping binary file"))
        self.assertIn("did not name", self.check(self.skip_line('"' + self.root + '\\x41"')))

    def test_warnings_and_errors_refused(self):
        self.assertIsNone(self.check("6:17PM WRN leaks found: 1"))
        for line in ("6:17PM WRN something odd", "6:17PM ERR could not read file path=/x"):
            self.assertIn("reported a problem", self.check(line))

    def test_colour_codes_ignored(self):
        self.assertIn("reported a problem", self.check("\x1b[90m6:17PM\x1b[0m \x1b[31mERR\x1b[0m x"))


class CleanRefusalTest(unittest.TestCase):
    """Odd input must end in a clean refusal, never a traceback."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def outcome(self, call):
        try:
            call()
            return "passed"
        except SystemExit as stop:
            return str(stop)

    def test_undecodable_patterns_file(self):
        os.makedirs(os.path.join(self.root, "private"))
        with open(os.path.join(self.root, "private", "guard-patterns.txt"), "wb") as handle:
            handle.write(b"\xff\xfe\x00not text")
        cwd, saved = os.getcwd(), os.environ.pop("GUARD_PATTERNS", None)
        os.chdir(self.root)
        try:
            # Paths are then hidden, as when no patterns are available.
            self.assertIsNone(secretscan.private_patterns())
        finally:
            os.chdir(cwd)
            if saved is not None:
                os.environ["GUARD_PATTERNS"] = saved

    def test_pattern_too_large_to_compile(self):
        saved = os.environ.get("GUARD_PATTERNS")
        os.environ["GUARD_PATTERNS"] = "a{99999999999}\n"
        try:
            self.assertIsNone(secretscan.private_patterns())
        finally:
            if saved is None:
                del os.environ["GUARD_PATTERNS"]
            else:
                os.environ["GUARD_PATTERNS"] = saved

    @unittest.skipUnless(os.name == "nt", "only Windows has drives")
    def test_skipped_path_on_another_drive(self):
        drive = "D:" if not self.root.upper().startswith("D:") else "E:"
        line = ("6:46PM DBG skipping file: global allowlist path="
                + json.dumps(drive + "\\x\\y")).encode()
        self.assertIn("refusing", self.outcome(lambda: secretscan.check_log(line, self.root)))

    def test_skipped_path_with_nul(self):
        line = b'6:46PM DBG skipping file: global allowlist path="/x\\u0000y"'
        self.assertIn("refusing", self.outcome(lambda: secretscan.check_log(line, self.root)))

    def test_unusable_line_numbers(self):
        content = os.path.join(self.root, "a" * 40)
        for line in (float("inf"), float("nan"), 1.5, True, "3"):
            with self.subTest(line=line):
                finding = {"File": content, "RuleID": "r", "StartLine": line}
                self.assertIn("unreadable finding", self.outcome(lambda: secretscan.report_lines(
                    [finding], {content: [("x", "p")]}, self.root,
                    os.path.join(self.root, "canary"))))


class GitleaksPresentTest(unittest.TestCase):
    def test_gitleaks_installed_where_required(self):
        if REQUIRED:
            self.assertIsNotNone(GITLEAKS)


@unittest.skipUnless(GITLEAKS or REQUIRED, "gitleaks not installed")
class SecretScanAttributesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD)
        shutil.copytree(os.path.join(REPO, "scripts", "guards"),
                        os.path.join(self.dir, "scripts", "guards"),
                        ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        shutil.copy(os.path.join(REPO, ".gitleaks.toml"), self.dir)
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "init")
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.base)  # reviewed main

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, data=None):
        return subprocess.run(["git", *args], cwd=self.dir, input=data, capture_output=True,
                              check=True, env=self.env).stdout.decode().strip()

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data.encode() if isinstance(data, str) else data)

    def stage_secret(self, attributes=None, name="notes.txt", data=SECRET):
        if attributes is not None:
            self.write(".gitattributes", attributes)
        self.write(name, data)
        self.git("add", "-A")

    def commit_secret(self, attributes=None, name="notes.txt", data=SECRET):
        self.stage_secret(attributes, name, data)
        self.git("commit", "-q", "--no-verify", "-m", "docs: notes")
        return self.git("rev-parse", "HEAD")

    def run_cmd(self, *command, stdin=None):
        return subprocess.run(list(command), cwd=self.dir, input=stdin, capture_output=True,
                              text=True, env=self.env)

    def pre_commit(self):
        return self.run_cmd("sh", os.path.join(REPO, ".githooks", "pre-commit"))

    def pre_push(self, sha, remote_sha="0" * 40, remote_ref="refs/heads/x"):
        return self.run_cmd("sh", os.path.join(REPO, ".githooks", "pre-push"), "origin",
                            "https://example.invalid/r.git",
                            stdin=f"refs/heads/x {sha} {remote_ref} {remote_sha}\n")

    def ci_scan(self, trusted=None):
        # The command secrets.yml runs over the full history (with the PR's
        # base or main before the push as the trusted revision, if any).
        with open(os.path.join(REPO, ".github", "workflows", "secrets.yml")) as handle:
            self.assertIn("python3 scripts/guards/secretscan.py commits $trusted --change HEAD --all",
                      handle.read())
        return self.run_cmd(sys.executable, "scripts/guards/secretscan.py", "commits",
                            "--trusted", trusted or self.base, "--change", "HEAD", "--all")

    def assert_found(self, result, rule="github-pat"):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(rule, output)
        self.assertNotIn(TOKEN, output)
        self.assertNotIn("Traceback", output)

    def assert_refused(self, result, why):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(why, output)
        self.assertNotIn("Traceback", output)

    def assert_all_find(self, sha):
        self.assert_found(self.ci_scan())
        self.assert_found(self.pre_push(sha))

    # Controls.

    def test_control_plain_secret_found(self):
        self.assert_all_find(self.commit_secret())

    def test_clean_history_passes(self):
        self.write("notes.txt", "ok\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "docs: ok")
        for result in (self.ci_scan(), self.pre_push(self.git("rev-parse", "HEAD"))):
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # Ways git's display used to hide a secret.

    def test_committed_no_diff_attribute_does_not_hide_secret(self):
        for attributes in ("notes.txt -diff\n", "* binary\n", "*.txt diff=hidden\n"):
            with self.subTest(attributes=attributes):
                self.tearDown()  # a fresh repository per case
                self.setUp()
                self.assert_all_find(self.commit_secret(attributes))

    def test_staged_no_diff_attribute_does_not_hide_secret(self):
        self.stage_secret("notes.txt -diff\n")
        self.assert_found(self.pre_commit())

    def test_local_attributes_do_not_hide_secret(self):
        self.write(".git/info/attributes", "*.txt -diff\n")
        self.stage_secret()
        self.assert_found(self.pre_commit())
        self.assert_all_find(self.commit_secret())

    def test_textconv_does_not_hide_secret(self):
        self.write(".git/info/attributes", "*.txt diff=blank\n")
        self.git("config", "diff.blank.textconv", "sed s/ghp_/xxx_/")
        self.stage_secret()
        self.assert_found(self.pre_commit())
        self.assert_all_find(self.commit_secret())

    def test_diff_colour_does_not_hide_secret(self):
        self.git("config", "color.diff", "always")
        self.git("config", "color.ui", "always")
        self.stage_secret()
        self.assert_found(self.pre_commit())
        self.assert_all_find(self.commit_secret())

    def test_nul_byte_file_does_not_hide_secret(self):
        self.stage_secret(data="x\0y\n" + SECRET)
        self.assert_found(self.pre_commit())
        self.assert_all_find(self.commit_secret(data="x\0y\n" + SECRET))

    def test_big_file_threshold_does_not_hide_secret(self):
        self.git("config", "core.bigFileThreshold", "10")
        self.assert_all_find(self.commit_secret())

    def test_secret_added_only_in_a_merge_found(self):
        self.git("checkout", "-q", "-b", "side")
        self.write("side.txt", "side\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "side")
        self.git("checkout", "-q", "-")
        self.write("main.txt", "main\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "main")
        self.git("merge", "-q", "--no-commit", "--no-ff", "side")
        self.write("merged.txt", SECRET)
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "merge")
        self.git("config", "log.diffMerges", "combined")
        self.assert_all_find(self.git("rev-parse", "HEAD"))

    def test_root_commit_not_hidden(self):
        self.tearDown()  # a repository whose first commit holds the secret
        self.dir = tempfile.mkdtemp()
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD)
        self.git("config", "log.showRoot", "false")
        shutil.copytree(os.path.join(REPO, "scripts", "guards"),
                        os.path.join(self.dir, "scripts", "guards"),
                        ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        shutil.copy(os.path.join(REPO, ".gitleaks.toml"), self.dir)
        self.write("notes.txt", SECRET)
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "init")
        self.base = self.git("rev-parse", "HEAD")  # only its settings matter
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.assert_all_find(self.base)

    def test_type_change_found(self):
        blob = self.git("hash-object", "-w", "--stdin", data=b"elsewhere")
        self.git("update-index", "--add", "--cacheinfo", f"120000,{blob},link")
        self.git("commit", "-q", "--no-verify", "-m", "link")
        secret = self.git("hash-object", "-w", "--stdin", data=SECRET.encode())
        self.git("update-index", "--cacheinfo", f"100644,{secret},link")
        self.git("commit", "-q", "--no-verify", "-m", "file")
        self.assert_all_find(self.git("rev-parse", "HEAD"))

    # Which commits and objects are scanned.

    def test_secret_already_on_another_remote_scanned(self):
        # A new branch's whole history is scanned, even commits that local
        # refs of another remote already contain.
        sha = self.commit_secret()
        self.git("update-ref", "refs/remotes/other/main", sha)
        self.assert_found(self.pre_push(sha))

    def test_replace_stand_in_does_not_hide_secret(self):
        real = self.commit_secret()
        self.git("reset", "-q", "--hard", self.base)
        self.write("notes.txt", "ok\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "docs: notes")
        self.git("replace", real, self.git("rev-parse", "HEAD"))
        self.assert_found(self.pre_push(real))

    # gitleaks' own path handling.

    def test_secret_in_image_or_lockfile_found(self):
        for name in ("logo.png", "icon.svg", "package-lock.json", "go.sum"):
            with self.subTest(name=name):
                self.tearDown()
                self.setUp()
                self.assert_all_find(self.commit_secret(name=name))

    def test_key_file_flagged_by_name(self):
        sha = self.commit_secret(name="certs/client.p12", data=b"\x30\x82\x01\x00binary")
        self.assert_found(self.ci_scan(), rule="pkcs12-file")
        self.assert_found(self.pre_push(sha), rule="pkcs12-file")

    def test_binary_looking_start_does_not_hide_secret(self):
        # gitleaks sniffs a file's type from its first bytes and skips
        # "binary" types even when the rest is plain text.
        starts = {"pdf": b"%PDF-1.4\n", "elf": b"\x7fELF\n", "zip": b"PK\x03\x04\n",
                  "gzip": b"\x1f\x8b\x08\0\0\0\0\0\n", "wasm": b"\0asm\x01\0\0\0\n",
                  "tar": b"a" * 257 + b"ustar\n"}
        for kind, start in starts.items():
            with self.subTest(kind=kind):
                self.tearDown()
                self.setUp()
                data = start + SECRET.encode()
                self.stage_secret(data=data)
                self.assert_found(self.pre_commit())
                self.assert_all_find(self.commit_secret(data=data))

    def test_signature_deep_in_file_does_not_hide_secret(self):
        # ISO 9660 images are recognised by "CD001" at byte 32769, so a large
        # text file with those bytes there was skipped as binary.
        for offset in (32769, 32769 - 10240):  # bare, and after the old 10 KB header
            with self.subTest(offset=offset):
                self.tearDown()
                self.setUp()
                filler = bytearray(b"b\n" * 25000)
                filler[offset:offset + 5] = b"CD001"
                self.assert_all_find(self.commit_secret(data=bytes(filler) + SECRET.encode()))

    def test_any_skipped_file_refused(self):
        # Whatever makes gitleaks skip a content copy, the scan refuses
        # rather than pass it: here, gitleaks' own size limit.
        self.commit_secret(data="x" * (2 * 1024 * 1024) + "\n")
        script = os.path.join(self.dir, "scripts", "guards", "secretscan.py")
        with open(script) as handle:
            text = handle.read()
        with open(script, "w") as handle:  # this test's copy only
            handle.write(text.replace('"--log-level", "debug",',
                                      '"--log-level", "debug", "--max-target-megabytes", "1",'))
        self.assert_refused(self.ci_scan(), "skipped a file")

    def test_reported_line_is_the_files_own(self):
        self.commit_secret(data="one\ntwo\n" + SECRET)
        self.assertIn("notes.txt:3: github-pat", self.ci_scan().stderr)

    def test_long_key_file_name_flagged(self):
        sha = self.commit_secret(name="certs/" + "a" * 70 + ".p12", data=b"\x30\x82binary")
        self.assert_found(self.ci_scan(), rule="pkcs12-file")
        self.assert_found(self.pre_push(sha), rule="pkcs12-file")

    def test_names_windows_cannot_create_scanned(self):
        # Names a commit made elsewhere can hold, which Windows can't create.
        blob = self.git("hash-object", "-w", "--stdin", data=SECRET.encode())
        tree = self.git("mktree", data=(f"100644 blob {blob}\t...\n100644 blob {blob}\tx. \n"
                                        f"100644 blob {blob}\tNUL.txt\n").encode())
        sha = self.git("commit-tree", tree, "-p", self.base, "-m", "docs: odd names")
        self.git("update-ref", "refs/heads/odd", sha)
        self.assert_found(self.run_cmd(sys.executable, "scripts/guards/secretscan.py",
                                       "commits", "--trusted", self.base, f"{self.base}..{sha}"))

    def test_committed_gitleaksignore_not_used(self):
        self.commit_secret()
        first = self.ci_scan().stderr
        fingerprints = [line for line in first.splitlines() if "github-pat" in line]
        self.assertTrue(fingerprints)
        # Ignore everything gitleaks could fingerprint for this file.
        sha = self.git("rev-parse", "HEAD")
        self.write(".gitleaksignore", f"{sha}:notes.txt:github-pat:1\nnotes.txt:github-pat:1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: ignore")
        self.assert_all_find(self.git("rev-parse", "HEAD"))

    # Failing closed.

    def test_config_that_allows_everything_refused(self):
        with open(os.path.join(self.dir, ".gitleaks.toml"), "a") as handle:
            handle.write('\n[allowlist]\nregexes = [\'\'\'.*\'\'\']\n')
        self.commit_secret()
        self.assert_refused(self.ci_scan(), "self-check failed")

    def weaken_config(self):
        # An allowlist that spares this one token but not the scan's canary.
        with open(os.path.join(self.dir, ".gitleaks.toml"), "a") as handle:
            handle.write("\n[[allowlists]]\nregexes = ['''" + TOKEN[:14] + "''']\n")

    def test_commit_cannot_weaken_its_own_scan(self):
        # The config a commit brings must not decide how that commit (or
        # the history) is scanned.
        self.weaken_config()
        sha = self.commit_secret()
        self.assert_found(self.ci_scan())
        self.assert_found(self.pre_push(sha))

    def test_staged_config_change_cannot_weaken_the_commit_scan(self):
        self.weaken_config()
        self.stage_secret()
        self.assert_found(self.pre_commit())

    def test_unstaged_config_change_cannot_weaken_the_scan(self):
        self.stage_secret()
        self.weaken_config()  # working tree only
        self.assert_found(self.pre_commit())

    def test_weakening_in_an_earlier_commit_cannot_help_a_later_one(self):
        # Commit A loosens the settings, commit B adds the secret: the
        # trusted revision's settings still apply to B.
        self.weaken_config()
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: settings")
        sha = self.commit_secret()
        self.assert_found(self.ci_scan(trusted=self.base))
        self.assert_found(self.pre_push(sha, remote_sha=self.base))
        self.assert_found(self.ci_scan())

    def test_committed_weakening_cannot_help_the_next_staged_commit(self):
        # The upstream branch's settings still apply at commit time.
        self.git("remote", "add", "origin", "https://example.invalid/r.git")
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.git("branch", "-q", "--set-upstream-to", "origin/main")
        self.weaken_config()
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: settings")
        self.stage_secret()
        self.assert_found(self.pre_commit())

    def test_feature_branch_cannot_trust_its_own_earlier_push(self):
        # Push 1 to a feature branch loosens the settings, push 2 adds the
        # secret: that branch's earlier tip is not reviewed, main is.
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.weaken_config()
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: settings")
        first_push = self.git("rev-parse", "HEAD")
        sha = self.commit_secret()
        self.assert_found(self.pre_push(sha, remote_sha=first_push, remote_ref="refs/heads/feat"))

    def test_approved_loosening_applies_to_new_branches(self):
        # Once a loosened setting is on main, a new branch is scanned with
        # main's settings (not every older, stricter version in history).
        self.weaken_config()
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: reviewed settings")
        self.git("update-ref", "refs/remotes/origin/main", self.git("rev-parse", "HEAD"))
        sha = self.commit_secret()
        result = self.pre_push(sha)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def ci_choice(self, **env):
        """Runs secrets.yml's real scan step with a stand-in python3 that
        records its arguments; returns them."""
        with open(os.path.join(REPO, ".github", "workflows", "secrets.yml")) as handle:
            lines = handle.read().splitlines()
        start = next(i for i, line in enumerate(lines) if "name: Scan full history" in line)
        run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
        body = []
        for line in lines[run + 1:]:
            if line.strip() and not line.startswith(" " * 10):
                break
            body.append(line[10:])
        bindir = os.path.join(self.dir, "fakebin")
        os.makedirs(bindir, exist_ok=True)
        recorded = os.path.join(self.dir, "args.txt")
        with open(os.path.join(bindir, "python3"), "w", newline="\n") as handle:
            handle.write(f'#!/bin/sh\necho "$@" > "{recorded}"\n')
        os.chmod(os.path.join(bindir, "python3"), 0o755)
        script = os.path.join(self.dir, "step.sh")
        with open(script, "w", newline="\n") as handle:
            handle.write("\n".join(body) + "\n")
        env = {**self.env, "PATH": bindir + os.pathsep + self.env["PATH"],
               "RUNNER_TEMP": bindir, "DEFAULT_BRANCH": "main", "BASE_SHA": "",
               "BASE_REF": "", "BEFORE_SHA": "", "GITHUB_EVENT_NAME": "push",
               "GITHUB_REF": "refs/heads/main", **env}
        subprocess.run(["sh", script], cwd=self.dir, env=env, check=True, capture_output=True)
        with open(recorded) as handle:
            return handle.read().split()

    def test_ci_trusts_only_reviewed_history(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        tip = self.commit_secret()
        cases = [
            # A PR's base is trusted only when it is main.
            (dict(GITHUB_EVENT_NAME="pull_request", BASE_REF="main", BASE_SHA=tip), tip),
            (dict(GITHUB_EVENT_NAME="pull_request", BASE_REF="feat", BASE_SHA=tip), self.base),
            # main before a push to main; current main for anything else.
            (dict(GITHUB_REF="refs/heads/main", BEFORE_SHA=self.base), self.base),
            (dict(GITHUB_REF="refs/heads/feat", BEFORE_SHA=tip), self.base),
            (dict(GITHUB_REF="refs/tags/v1", BEFORE_SHA="0" * 40), self.base),
            (dict(GITHUB_REF="refs/heads/main", BEFORE_SHA="0" * 40), None),
            # A forced push whose old tip isn't in the clone: nothing trusted.
            (dict(GITHUB_REF="refs/heads/main", BEFORE_SHA="1" * 40), None),
            (dict(GITHUB_EVENT_NAME="pull_request", BASE_REF="main", BASE_SHA="1" * 40), None),
            # Another default branch name is honoured.
            (dict(GITHUB_REF="refs/heads/trunk", DEFAULT_BRANCH="trunk", BEFORE_SHA=self.base),
             self.base),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                args = self.ci_choice(**env)
                self.assertEqual(args[-3:], ["--change", "HEAD", "--all"])
                if expected is None:
                    self.assertNotIn("--trusted", args)
                else:
                    self.assertEqual(args[args.index("--trusted") + 1], expected)

    def test_quoted_path_key_refused(self):
        with open(os.path.join(self.dir, ".gitleaks.toml"), "a") as handle:
            handle.write('\n[[rules]]\nid = "x"\n"path" = \'\'\'\\.x$\'\'\'\n')
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: settings")
        self.assert_refused(self.ci_scan(), "path-based rule")

    def test_reviewed_allowlist_applies_once_trusted(self):
        # A loosened setting takes effect once it is in the trusted revision.
        self.weaken_config()
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: reviewed settings")
        reviewed = self.git("rev-parse", "HEAD")
        sha = self.commit_secret()
        result = self.run_cmd(sys.executable, "scripts/guards/secretscan.py", "commits",
                              "--trusted", reviewed, f"{reviewed}..{sha}")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_trusted_revision_without_settings_refused(self):
        self.git("rm", "-q", ".gitleaks.toml")
        self.git("commit", "-q", "--no-verify", "-m", "chore: drop settings")
        bare = self.git("rev-parse", "HEAD")
        self.assert_refused(self.ci_scan(trusted=bare), "has no .gitleaks.toml")

    def test_no_settings_anywhere_refused(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        self.git("rm", "-q", ".gitleaks.toml")
        self.git("commit", "-q", "--no-verify", "-m", "chore: drop settings")
        self.stage_secret()
        self.assert_refused(self.run_cmd(sys.executable, "scripts/guards/secretscan.py", "staged"),
                            "found no .gitleaks.toml")

    def test_no_reviewed_revision_refused(self):
        sha = self.commit_secret()
        self.assert_refused(self.run_cmd(sys.executable, "scripts/guards/secretscan.py",
                                         "commits", sha), "no reviewed revision")
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        self.assert_refused(self.pre_push(sha, remote_ref="refs/heads/feat"), "no reviewed revision")

    def test_other_branches_settings_dont_count_in_ci(self):
        # A stale branch with older, stricter settings, and a branch with
        # unusable settings, must not affect the scan of this change.
        self.git("branch", "stale", self.base)
        self.git("checkout", "-q", "-b", "broken")
        with open(os.path.join(self.dir, ".gitleaks.toml"), "a") as handle:
            handle.write('\n[[rules]]\nid = "x"\npath = \'\'\'\\.x$\'\'\'\n')
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: broken settings")
        self.git("checkout", "-q", "-")
        self.weaken_config()
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: reviewed settings")
        reviewed = self.git("rev-parse", "HEAD")
        self.commit_secret()
        result = self.ci_scan(trusted=reviewed)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_path_rule_in_config_refused(self):
        with open(os.path.join(self.dir, ".gitleaks.toml"), "a") as handle:
            handle.write('\n[[rules]]\nid = "x"\npath = \'\'\'\\.x$\'\'\'\n')
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "chore: settings")
        self.assert_refused(self.ci_scan(), "path-based rule")

    def test_bad_revision_refused(self):
        self.assert_refused(self.run_cmd(sys.executable, "scripts/guards/secretscan.py",
                                     "commits", "no-such-ref"), "refusing")

    def test_missing_gitleaks_refused(self):
        # PATH without any folder holding gitleaks (git may share one, as
        # with Homebrew; the scan checks for gitleaks before using git).
        names = ("gitleaks", "gitleaks.exe")
        folders = [folder for folder in self.env["PATH"].split(os.pathsep)
                   if not any(os.path.exists(os.path.join(folder, name)) for name in names)]
        env = dict(self.env, PATH=os.pathsep.join(folders))
        result = subprocess.run([sys.executable, "scripts/guards/secretscan.py", "commits", "--all"],
                                cwd=self.dir, capture_output=True, text=True, env=env)
        self.assert_refused(result, "gitleaks is required")

    def scan_with_tools_on_path(self, entry, cwd):
        # A copy of gitleaks in <repo>/sub/tools, found only through `entry`.
        self.commit_secret()
        tools = os.path.join(self.dir, "sub", "tools")
        os.makedirs(tools)
        shutil.copy(GITLEAKS, tools)
        names = ("gitleaks", "gitleaks.exe")
        folders = [folder for folder in self.env["PATH"].split(os.pathsep)
                   if not any(os.path.exists(os.path.join(folder, name)) for name in names)]
        env = dict(self.env, PATH=os.pathsep.join([entry, *folders]))
        script = os.path.relpath(os.path.join(self.dir, "scripts", "guards", "secretscan.py"), cwd)
        return subprocess.run([sys.executable, script, "commits", "--trusted", self.base,
                               "--change", "HEAD", "--all"],
                              cwd=cwd, capture_output=True, text=True, env=env)

    def test_relative_path_entry_ignored(self):
        # From a subfolder, as from the top folder in hooks, a relative PATH
        # entry points into the repository.
        result = self.scan_with_tools_on_path("tools", os.path.join(self.dir, "sub"))
        self.assert_refused(result, "gitleaks is required")

    def test_gitleaks_inside_repo_refused(self):
        tools = os.path.join(self.dir, "sub", "tools")
        self.assert_refused(self.scan_with_tools_on_path(tools, self.dir),
                            "must not come from inside the repository")

    @unittest.skipUnless(os.name == "nt", "only Windows searches the current folder")
    def test_gitleaks_planted_in_repo_not_run(self):
        # Windows looks in the current folder before PATH, for .exe, .cmd and
        # the like. A stand-in that hides every file but the canary and then
        # runs the real gitleaks would report a clean scan.
        self.write("fake.py",
                   "import os, subprocess, sys\n"
                   "for top, _, names in os.walk(sys.argv[-1]):\n"
                   "    for name in names:\n"
                   "        if name != 'canary':\n"
                   "            os.remove(os.path.join(top, name))\n"
                   f"sys.exit(subprocess.run([{os.path.abspath(GITLEAKS)!r}, *sys.argv[1:]]).returncode)\n")
        self.write("gitleaks.cmd", f'@"{sys.executable}" "%~dp0fake.py" %*\r\n')
        self.commit_secret()
        env = {k: v for k, v in self.env.items() if k.lower() != "nodefaultcurrentdirectoryinexepath"}
        result = subprocess.run([sys.executable, "scripts/guards/secretscan.py", "commits",
                                 "--trusted", self.base, "--change", "HEAD", "--all"],
                                cwd=self.dir, capture_output=True, text=True, env=env)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertNotIn("Traceback", output)
        self.assertIn("possible secrets found", output)  # the real gitleaks ran

    def test_gitleaks_that_cannot_start_refused(self):
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            configs = secretscan.config_blobs([self.base])
            with self.assertRaises(SystemExit) as stop:
                secretscan.scan([], configs, os.path.join(self.dir, "no-such-gitleaks"))
        finally:
            os.chdir(cwd)
        self.assertIn("could not run gitleaks", str(stop.exception))

    def test_report_hides_private_paths(self):
        self.commit_secret(name="ZZTEST-42/notes.txt")
        output = self.ci_scan().stderr
        self.assertIn("<path hidden>", output)
        self.assertNotIn("ZZTEST-42", output)

    def test_paths_hidden_without_patterns(self):
        # CI's secret scan job has no private patterns, so it shows no paths.
        self.commit_secret(name="docs/notes.txt")
        del self.env["GUARD_PATTERNS"]
        output = self.ci_scan().stderr
        self.assertIn("<path hidden>", output)
        self.assertNotIn("docs/notes.txt", output)

    def test_report_is_valid_json_for_gitleaks_version(self):
        # The parser relies on these report fields.
        self.write("notes.txt", SECRET)
        report = os.path.join(self.dir, "r.json")
        subprocess.run([GITLEAKS, "dir", "--no-banner", "--report-format", "json",
                        "--report-path", report, os.path.join(self.dir, "notes.txt")],
                       capture_output=True)
        with open(report) as handle:
            finding = json.load(handle)[0]
        for field in ("File", "RuleID", "StartLine"):
            self.assertIn(field, finding)


if __name__ == "__main__":
    unittest.main()
