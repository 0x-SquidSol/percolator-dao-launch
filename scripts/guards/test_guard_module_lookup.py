"""Regression tests: files in the repository must never stand in for the
guards' own code. Python looks for a module in the script's folder first, and
there it prefers a package folder, a compiled extension or cached bytecode
over the reviewed source; a pull can bring any of them, even into an ignored
folder such as __pycache__.
"""
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GOOD = "dev@percolator.trade"
# Built from parts so this file doesn't trip the licence check itself.
MARKER = "BUSL" + "-1.1"
# A textscan that reads nothing, so no content check can match.
BLIND_TEXTSCAN = "MAX_SCAN_BYTES = 25 * 1024 * 1024\n\ndef text_views(data):\n    return []\n"
# A standard library module that ends the guard before it checks anything.
QUIT = "import sys\nsys.exit(0)\n"


class PlantedModuleTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_") and not k.startswith("PYTHON")}
        self.env["GUARD_PATTERNS"] = "ZZTEST-\\d{2}\n"
        self.real_git = shutil.which("git")
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", GOOD)
        self.guards = os.path.join(self.dir, "scripts", "guards")
        shutil.copytree(HERE, self.guards, ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        self.git("add", ".")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        return subprocess.run([self.real_git, *args], cwd=self.dir, capture_output=True,
                              check=True, env=self.env).stdout.decode().strip()

    def write(self, relative, text):
        path = os.path.join(self.guards, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def pulled(self, *relative):
        """Commit planted files, as a pull from someone else would bring them."""
        self.git("add", "-f", *[os.path.join("scripts", "guards", name) for name in relative])
        self.git("commit", "-q", "-m", "update")

    def assert_guards_block(self):
        notes = os.path.join(self.dir, "notes.txt")
        for guard, text, why in (("guard.py", "ZZTEST-42\n", "matches private pattern"),
                                 ("provenance.py", f'license = "{MARKER}"\n', "PROVENANCE.md")):
            with open(notes, "w") as handle:
                handle.write(text)
            self.git("add", "notes.txt")
            result = subprocess.run([sys.executable, "-B", os.path.join("scripts", "guards", guard), "staged"],
                                    cwd=self.dir, capture_output=True, text=True, env=self.env)
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, guard + ": " + output)
            self.assertIn(why, output, guard)
            self.assertNotIn("Traceback", output, guard)
        self.git("rm", "-q", "--cached", "notes.txt")  # never committed by a later step

    def test_cached_bytecode_not_used(self):
        # Bytecode marked "don't check the source" is used even with -B.
        source = os.path.join(tempfile.mkdtemp(), "textscan.py")
        self.addCleanup(shutil.rmtree, os.path.dirname(source), ignore_errors=True)
        with open(source, "w") as handle:
            handle.write(BLIND_TEXTSCAN)
        cached = os.path.join("__pycache__", f"textscan.{sys.implementation.cache_tag}.pyc")
        py_compile.compile(source, cfile=os.path.join(self.guards, cached), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        self.pulled(cached)
        self.assert_guards_block()

    def test_package_folder_not_used(self):
        self.write(os.path.join("textscan", "__init__.py"), BLIND_TEXTSCAN)
        self.pulled("textscan")
        self.assert_guards_block()

    def test_extension_module_not_used(self):
        # Not a real extension: loading it at all would fail the guard.
        name = "textscan.pyd" if os.name == "nt" else "textscan.so"
        self.write(name, "not a library\n")
        self.pulled(name)
        self.assert_guards_block()

    def test_standard_library_not_replaced(self):
        for name in ("subprocess.py", "typing.py"):
            with self.subTest(name):
                self.write(name, QUIT)
                self.pulled(name)
                self.assert_guards_block()
                self.git("rm", "-q", os.path.join("scripts", "guards", name))
                self.git("commit", "-q", "-m", "remove")

    def assert_staged_refused(self, relative, why):
        """A commit adding `relative` (with harmless content) is refused."""
        path = os.path.join(self.dir, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write("x\n")
        self.git("add", "-f", relative)
        try:
            result = subprocess.run([sys.executable, "-I", os.path.join("scripts", "guards", "guard.py"),
                                     "staged"], cwd=self.dir, capture_output=True, text=True,
                                    env=self.env)
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn(why, output)
            self.assertNotIn("Traceback", output)
        finally:
            self.git("rm", "-q", "-f", relative)  # from the index and the disk

    def test_planted_files_refused(self):
        # Also refused outright, so a reviewer never has to spot them.
        rule = "only .py source files and setup.sh belong in scripts/guards"
        for name in ("textscan.pyd", "textscan.so", os.path.join("textscan", "__init__.py"),
                     "notes.txt"):
            with self.subTest(name):
                self.assert_staged_refused(os.path.join("scripts", "guards", name), rule)

    def test_compiled_python_refused(self):
        for name in (os.path.join("tools", "__pycache__", "x.cpython-312.pyc"), "x.pyc",
                     os.path.join("scripts", "spec", "json.cpython-312-x86_64-linux-gnu.so")):
            with self.subTest(name):
                self.assert_staged_refused(name, "compiled Python file")

    def test_start_up_blocks_identical(self):
        # The block can't be shared: importing it would come before it runs.
        blocks = set()
        for name in ("guard.py", "provenance.py", "secretscan.py", "js_audit.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                text = handle.read()
            start = text.index("# --- start-up block")
            blocks.add(text[start:text.index("# --- end of start-up block ---", start)])
        self.assertEqual(len(blocks), 1)


if __name__ == "__main__":
    unittest.main()
