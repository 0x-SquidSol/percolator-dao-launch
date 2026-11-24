"""Regression tests: files in the repository must never stand in for git or
python. On Windows, starting a program by name also searches the current
folder; on any system a relative PATH folder points into the repository when
hooks run; and a pull overwrites ignored files, such as a venv's python.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LEAK_GUARD = os.path.join(HERE, "guard.py")
PROVENANCE = os.path.join(HERE, "provenance.py")
COMMIT_MSG = os.path.join(REPO, ".githooks", "commit-msg")
GOOD = "dev@percolator.trade"
# Built from parts so this file doesn't trip the licence check itself.
MARKER = "BUSL" + "-1.1"
WINDOWS = os.name == "nt"
# Any program that isn't git or python will do as the stand-in on Windows.
FINDSTR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "findstr.exe")


class PlantedProgramTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_") and k.lower() != "nodefaultcurrentdirectoryinexepath"}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.real_git = shutil.which("git")
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD)
        self.git("commit", "-q", "--allow-empty", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args):
        return subprocess.run([self.real_git, *args], cwd=self.dir, capture_output=True,
                              check=True, env=self.env).stdout.decode().strip()

    def plant(self, folder, name):
        """A stand-in program called `name` that does nothing useful."""
        os.makedirs(os.path.join(self.dir, folder), exist_ok=True)
        if WINDOWS:
            shutil.copy(FINDSTR, os.path.join(self.dir, folder, name + ".exe"))
        else:
            path = os.path.join(self.dir, folder, name)
            with open(path, "w") as handle:
                handle.write("#!/bin/sh\nexit 0\n")
            os.chmod(path, 0o755)

    def stage(self, text):
        with open(os.path.join(self.dir, "notes.txt"), "w") as handle:
            handle.write(text)
        self.git("add", "notes.txt")

    def run_tool(self, tool, *args, path=None):
        env = dict(self.env, PATH=path) if path is not None else self.env
        return subprocess.run([sys.executable, tool, *args], cwd=self.dir,
                              capture_output=True, text=True, env=env)

    def assert_blocked(self, result, why):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(why, output)
        self.assertNotIn("Traceback", output)

    # The guards' own git.

    @unittest.skipUnless(WINDOWS, "only Windows searches the current folder")
    def test_git_in_current_folder_not_run(self):
        self.plant(".", "git")
        self.stage("ZZTEST-42\n")
        self.assert_blocked(self.run_tool(LEAK_GUARD, "staged"), "matches private pattern")
        self.stage(f'license = "{MARKER}"\n')
        self.assert_blocked(self.run_tool(PROVENANCE, "staged"), "PROVENANCE.md")

    def test_relative_path_folder_not_searched(self):
        self.plant(".", "git")
        self.stage("ZZTEST-42\n")
        path = os.pathsep.join([".", self.env["PATH"]])
        self.assert_blocked(self.run_tool(LEAK_GUARD, "staged", path=path), "matches private pattern")
        self.stage(f'license = "{MARKER}"\n')
        self.assert_blocked(self.run_tool(PROVENANCE, "staged", path=path), "PROVENANCE.md")

    def test_git_inside_repository_refused(self):
        self.plant("tools", "git")
        self.stage("ZZTEST-42\n")
        path = os.pathsep.join([os.path.join(self.dir, "tools"), self.env["PATH"]])
        self.assert_blocked(self.run_tool(LEAK_GUARD, "staged", path=path),
                            "git must not come from inside the repository")

    def test_no_git_started_by_name(self):
        # Every guard must start git through gitfiles.git_exe().
        for name in os.listdir(HERE):
            if name.endswith(".py") and not name.startswith("test_"):
                with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                    self.assertIsNone(re.search(r"""["']git["']\s*[,\]]""", handle.read()), name)

    # The hooks' python and git.

    def commit_msg_hook(self, path):
        # The hook runs the guards from the top folder, as in this repo.
        guards = os.path.join(self.dir, "scripts", "guards")
        if not os.path.isdir(guards):
            shutil.copytree(HERE, guards, ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        message = os.path.join(self.dir, "message.txt")
        with open(message, "w") as handle:
            handle.write("docs: ZZTEST-42\n")
        env = dict(self.env, PATH=path)
        return subprocess.run(["sh", COMMIT_MSG, message], cwd=self.dir,
                              capture_output=True, text=True, env=env)

    # A stand-in passes the hook's version check on POSIX (it exits 0), so
    # there these tests fail unless the real python runs the real guard. On
    # Windows the stand-in fails that check, so they only show nothing breaks.

    def test_hook_ignores_relative_path_folders(self):
        # Including the tools the hook could use before PATH is clean.
        for name in ("python3", "python", "py", "git", "dirname", "tr", "grep", "paste", "sed"):
            self.plant(".", name)
        result = self.commit_msg_hook(os.pathsep.join([".", self.env["PATH"]]))
        self.assert_blocked(result, "private pattern")  # the real guard ran

    def test_hook_ignores_folders_inside_repository(self):
        # Even an ignored venv: a pull overwrites ignored files.
        folder = os.path.join(self.dir, ".venv", "Scripts" if WINDOWS else "bin")
        for name in ("python3", "python", "py", "git"):
            self.plant(folder, name)
        result = self.commit_msg_hook(os.pathsep.join([folder, self.env["PATH"]]))
        self.assert_blocked(result, "private pattern")

    def test_hook_ignores_repository_folders_reached_through_a_link(self):
        link = os.path.join(tempfile.mkdtemp(), "link")
        self.addCleanup(shutil.rmtree, os.path.dirname(link), ignore_errors=True)
        try:
            if WINDOWS:
                import _winapi
                _winapi.CreateJunction(self.dir, link)
            else:
                os.symlink(self.dir, link)
        except OSError:
            self.skipTest("cannot create links here")
        self.plant("tools", "python3")
        self.plant("tools", "python")
        result = self.commit_msg_hook(os.pathsep.join([os.path.join(link, "tools"),
                                                       self.env["PATH"]]))
        self.assert_blocked(result, "private pattern")

    def test_hook_ignores_link_into_repository_folder(self):
        # The link's own parents are outside: only where it leads is inside.
        link = os.path.join(tempfile.mkdtemp(), "bin")
        self.addCleanup(shutil.rmtree, os.path.dirname(link), ignore_errors=True)
        self.plant("tools", "python3")
        self.plant("tools", "python")
        try:
            if WINDOWS:
                import _winapi
                _winapi.CreateJunction(os.path.join(self.dir, "tools"), link)
            else:
                os.symlink(os.path.join(self.dir, "tools"), link)
        except OSError:
            self.skipTest("cannot create links here")
        result = self.commit_msg_hook(os.pathsep.join([link, self.env["PATH"]]))
        self.assert_blocked(result, "private pattern")

    def test_hook_ignores_version_manager_settings(self):
        # A shim that obeys .python-version would pick the repository's python.
        shims = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, shims, ignore_errors=True)
        if WINDOWS:
            self.skipTest("the stand-in shim is a shell script")
        with open(os.path.join(self.dir, ".python-version"), "w") as handle:
            handle.write("repo\n")
        self.plant("tools", "python3")
        shim = os.path.join(shims, "python3")
        with open(shim, "w") as handle:
            handle.write('#!/bin/sh\n'
                         '[ "${PYENV_VERSION:-}" = system ] && exec "%s" "$@"\n'
                         '[ -f .python-version ] && exec ./tools/python3 "$@"\n'
                         'exec "%s" "$@"\n' % (sys.executable, sys.executable))
        os.chmod(shim, 0o755)
        result = self.commit_msg_hook(os.pathsep.join([shims, self.env["PATH"]]))
        self.assert_blocked(result, "private pattern")

    def test_guard_from_subfolder_refuses_git_in_repository(self):
        self.plant("tools", "git")
        os.makedirs(os.path.join(self.dir, "sub"))
        self.stage("ZZTEST-42\n")
        path = os.pathsep.join([os.path.join(self.dir, "tools"), self.env["PATH"]])
        result = subprocess.run([sys.executable, LEAK_GUARD, "staged"], cwd=os.path.join(self.dir, "sub"),
                                capture_output=True, text=True, env=dict(self.env, PATH=path))
        self.assert_blocked(result, "git must not come from inside the repository")

if __name__ == "__main__":
    unittest.main()
