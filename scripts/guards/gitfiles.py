"""Which files the guards must check, and their content, read from git.

Both guards use this module, so they always check the same entries:
  - staged changes:  `git diff --cached`
  - each commit:     `git diff-tree` against every parent
  - every file:      the index (`git ls-files -s`), which is what the next
                     commit publishes (in CI it equals HEAD)

Changes are listed with --diff-filter=d (everything except deletions), so
type changes (symlink <-> file) and any status git adds later are included,
and with --no-renames, so each entry has exactly one path. Content is read
by blob id through `git cat-file --batch`: the raw stored bytes, never the
working tree, so a symlink is checked as the link text git stores.

Fail closed: submodules (their content is in another repository), unmerged
entries and any unknown mode or status are returned as refusals, never
skipped, and any git error stops the guard.

Git stand-ins (`git replace`) change what git shows but not what a push
sends, so they are switched off for every git process the guards start.
"""
import base64
import os
import re
import subprocess
import sys
import tempfile
from typing import List, NamedTuple, Optional, Tuple

import textscan

# Set at import, before any git runs: guard.py and provenance.py import this
# module, so all their git processes (including cat-file --batch) inherit it.
os.environ["GIT_NO_REPLACE_OBJECTS"] = "1"
# Windows also starts programs from the current folder (the repository, in
# hooks); this stops that for every process the guards start.
os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"


def in_current_folder(path, folder="."):
    """Whether `path`, links resolved, is `folder` (by default the current
    folder) or inside it."""
    top = os.stat(folder)
    top_path = os.path.normcase(os.path.realpath(folder))
    place = os.path.realpath(path)
    while True:
        here = os.stat(place)
        if top.st_ino and here.st_ino:
            same = os.path.samestat(here, top)
        else:  # a file system without file IDs: compare paths
            same = os.path.normcase(place) == top_path
        if same:
            return True
        parent = os.path.dirname(place)
        if parent == place:
            return False
        place = parent


def program(name):
    """`name` from an absolute PATH folder, or None. Searched by hand:
    relative PATH folders point into the repository when hooks run, and
    before Python 3.12 shutil.which also searches the current folder on
    Windows. Only .exe on Windows, the form git and gitleaks ship in."""
    filename = name + ".exe" if os.name == "nt" else name
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if folder and os.path.isabs(folder):
            candidate = os.path.join(folder, filename)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return os.path.abspath(candidate)
    return None


def _enclosing_repository():
    """The nearest folder, from the current one up, holding a .git entry
    (found without git, which isn't trusted yet); else the current folder."""
    folder = os.path.realpath(".")
    while not os.path.lexists(os.path.join(folder, ".git")):
        parent = os.path.dirname(folder)
        if parent == folder:
            return "."
        folder = parent
    return folder


def _find_git():
    """The real git, never one from the repository being checked."""
    git = program("git")
    if git is None:
        sys.exit("guard: refusing, git was not found in an absolute PATH folder")
    try:
        top = _enclosing_repository()
        planted = (in_current_folder(os.path.dirname(git), top)
                   or in_current_folder(git, top))
    except OSError:
        sys.exit("guard: refusing, could not check where git is installed")
    if planted:
        sys.exit("guard: refusing, git must not come from inside the repository")
    return git


_git_path = None


def git_exe():
    """The real git, found on first use (after a caller's own checks)."""
    global _git_path
    if _git_path is None:
        _git_path = _find_git()
    return _git_path


CHECKABLE_MODES = {"100644", "100755", "120000"}  # file, executable, symlink
CHECKABLE_STATUSES = set("ACMRT")
ZERO_SHA = "0" * 40


class Entry(NamedTuple):
    path: str
    mode: str
    sha: str


class Refusal(NamedTuple):
    path: str
    reason: str


def _git(*args):
    result = subprocess.run([git_exe(), *args], capture_output=True)
    if result.returncode != 0:
        # Name only the git subcommand: its arguments may contain file names.
        sys.exit(f"guard: refusing, 'git {args[0]}' failed (fetch or check the repository)")
    return result.stdout


def _path(raw):
    """A file name from git, and whether it is valid UTF-8. Invalid names
    are refused, shown with escapes rather than crashing the guard."""
    try:
        return raw.decode("utf-8"), True
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="backslashreplace"), False


def _classify(path, mode, sha, status="A"):
    if mode == "160000":
        return Refusal(path, "submodule (its content cannot be checked)")
    if status not in CHECKABLE_STATUSES:
        return Refusal(path, f"unsupported change type {status}")
    if mode not in CHECKABLE_MODES or sha == ZERO_SHA:
        return Refusal(path, f"unsupported file mode {mode}")
    return Entry(path, mode, sha)


def _parse_raw(out) -> Tuple[List[Entry], List[Refusal]]:
    """Parses `--raw -z` output: ":old new oldsha newsha status\\0path\\0"."""
    fields = out.split(b"\0")
    entries, refusals, seen = [], [], set()
    i = 0
    while i < len(fields) - 1:
        meta = fields[i].decode("ascii")
        if not meta.startswith(":"):
            sys.exit("guard: refusing, unexpected 'git diff' output")
        path, valid = _path(fields[i + 1])
        i += 2
        _, new_mode, _, new_sha, status = meta[1:].split(" ")
        if len(new_sha) != 40:
            sys.exit("guard: refusing, unexpected 'git diff' output (abbreviated id)")
        if valid:
            item = _classify(path, new_mode, new_sha, status[0])
        else:
            item = Refusal(path, "file name is not valid UTF-8")
        key = (item.path, item.sha if isinstance(item, Entry) else item.reason)
        if key in seen:  # merges list a file once per parent
            continue
        seen.add(key)
        (entries if isinstance(item, Entry) else refusals).append(item)
    return entries, refusals


def staged():
    return _parse_raw(_git(
        "diff", "--cached", "--raw", "-z", "--no-abbrev", "--no-renames", "--diff-filter=d",
    ))


def in_commit(sha):
    """Entries a commit adds or changes, against each of its parents."""
    return _parse_raw(_git(
        "diff-tree", "-r", "-m", "--root", "--no-commit-id", "--raw", "-z", "--no-abbrev",
        "--no-renames", "--diff-filter=d", sha,
    ))


def in_index():
    """Every entry in the index: "mode sha stage\\tpath\\0"."""
    entries, refusals, refused = [], [], set()
    for record in filter(None, _git("ls-files", "-s", "-z").split(b"\0")):
        meta, raw_path = record.split(b"\t", 1)
        mode, sha, stage = meta.decode("ascii").split(" ")
        path, valid = _path(raw_path)
        if not valid or stage != "0":
            if path not in refused:  # an unmerged file has up to 3 stages
                refused.add(path)
                reason = "file name is not valid UTF-8" if not valid else "unmerged entry"
                refusals.append(Refusal(path, reason))
            continue
        item = _classify(path, mode, sha)
        (entries if isinstance(item, Entry) else refusals).append(item)
    return entries, refusals


def require_commits(rev_args):
    """Refuses unless every revision named in rev_args is a commit, or a tag
    (or chain of tags) of one. git log and rev-list list nothing for a blob
    or tree, so without this a pushed ref pointing at one would look clean.
    git itself parses the arguments (ranges, --not, --remotes, ...).
    Also refuses while a graft file exists: grafts rewrite parent links, so
    the guard and a push could walk different commits. (Grafts are
    deprecated; --git-path follows GIT_GRAFT_FILE.)"""
    # fsdecode, not a lossy decode: the path must stay exactly as git gave it.
    grafts = os.fsdecode(_git("rev-parse", "--git-path", "info/grafts").rstrip(b"\r\n"))
    if os.path.lexists(grafts):
        sys.exit("guard: refusing, a git graft file exists (grafts are deprecated; remove it)")
    resolved = _git("rev-parse", "--revs-only", *rev_args).decode("ascii").split()
    if not any(not sha.startswith("^") for sha in resolved):
        # Nothing being pushed was named (e.g. an unknown name git dropped).
        sys.exit("guard: refusing, found no commit to check")
    for sha in resolved:
        excluded = sha.startswith("^")
        # Excluded revisions (already on the remote) only have to exist;
        # everything being pushed must peel to a commit.
        target = sha[1:] if excluded else sha + "^{commit}"
        check = ["cat-file", "-e", target] if excluded else ["rev-parse", "--verify", "-q", target]
        if subprocess.run([git_exe(), *check], capture_output=True).returncode != 0:
            # No ref name or id: either could match a private pattern.
            sys.exit("guard: refusing, a pushed object is not a commit (or a tag of one)")
    return resolved


class Tag(NamedTuple):
    sha: str
    raw: bytes                    # the whole tag object, headers included
    taggers: List[Optional[str]]  # email of each tagger line (None: no <...>)


MAX_TAG_CHAIN = 32
_OBJECT_LINE = re.compile(rb"object ([0-9a-f]{40}|[0-9a-f]{64})")


def tag_chain(sha) -> List[Tag]:
    """The annotated tag objects from sha down to the first object that is
    not a tag (a tag of a tag yields both). Empty if sha is not a tag.
    Refuses (exits) on a malformed tag or a chain deeper than
    MAX_TAG_CHAIN. git log and rev-list peel straight past tag objects, so
    this is the only place their own text is read."""
    tags = []
    for _ in range(MAX_TAG_CHAIN + 1):
        if _git("cat-file", "-t", sha).strip() != b"tag":
            return tags
        tag, target = parse_tag(sha, _git("cat-file", "tag", sha))
        tags.append(tag)
        sha = target
    sys.exit("guard: refusing, tag chain too deep")


def parse_tag(sha, raw) -> Tuple[Tag, str]:
    """A tag object and the id it points at. Used for pushed tags and for
    tags embedded in merge commits (mergetag), so both get the same checks.
    Refuses (exits) on a malformed tag."""
    head, separator, _ = raw.partition(b"\n\n")
    lines = head.split(b"\n")
    objects = [line for line in lines if line.startswith(b"object ")]
    types = [line for line in lines if line.startswith(b"type ")]
    target = _OBJECT_LINE.fullmatch(objects[0]) if len(objects) == 1 else None
    if not separator or target is None or len(types) != 1:
        sys.exit("guard: refusing, could not read a tag object")
    taggers = []
    for line in lines:
        if line.startswith(b"tagger "):
            email = re.search(rb"<([^>]*)>", line)
            taggers.append(email.group(1).decode("utf-8", errors="replace") if email else None)
    return Tag(sha, raw, taggers), target.group(1).decode("ascii")


# Signatures are checked like any other text. Their data is random, so a
# short private pattern could match it by chance. Such a match is excused
# only for a genuine signature by one of these keys (see genuine_signature):
# only the key holder can make one, and its data can't be chosen. Public by nature: an SSH signature embeds its
# key, so each key is already in every commit it signed. A new signing key
# goes here before (or in) the first commit it signs; never remove a key
# that signed published history.
SIGNING_KEYS = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDjtA7WaoM8MF+HWm6+cLPaRCfgnIxVdEC8UlU3N2Wuz",
)
SIGNATURE_NAMESPACE = "git"  # what git signs commits and tags under
_ED25519_ORDER = 2**252 + 27742317777372353535851937790883648493  # L
_SSH_BEGIN = b"-----BEGIN SSH SIGNATURE-----"
_SSH_END = b"-----END SSH SIGNATURE-----"
# Lines git takes as the start of a tag's signature (gpg-interface.c).
_SIGNATURE_STARTS = (b"-----BEGIN PGP SIGNATURE-----", b"-----BEGIN PGP MESSAGE-----",
                     b"-----BEGIN SIGNED MESSAGE-----", _SSH_BEGIN)


def _ssh_strings(data, pos, count):
    """`count` length-prefixed SSH wire strings from data[pos:], and the
    position after them; (None, pos) if they don't fit."""
    out = []
    for _ in range(count):
        size = int.from_bytes(data[pos:pos + 4], "big")
        if pos + 4 > len(data) or pos + 4 + size > len(data):
            return None, pos
        out.append(data[pos + 4:pos + 4 + size])
        pos += 4 + size
    return out, pos


def _pinned_ssh_signature(armored):
    """Whether armored is byte for byte what ssh-keygen writes for an
    ed25519 signature by a pinned key under the git namespace. ssh-keygen
    itself accepts more (rewrapped lines, text after the end line, any
    reserved field), and none of that is signed, so it could hide text."""
    lines = armored.split(b"\n")
    if len(lines) < 4 or lines[0] != _SSH_BEGIN or lines[-2:] != [_SSH_END, b""]:
        return False
    try:
        blob = base64.b64decode(b"".join(lines[1:-2]), validate=True)
    except ValueError:
        return False
    encoded = base64.b64encode(blob)
    if lines[1:-2] != [encoded[i:i + 70] for i in range(0, len(encoded), 70)]:
        return False
    fields, end = _ssh_strings(blob, 10, 5)
    if blob[:10] != b"SSHSIG\0\0\0\1" or fields is None or end != len(blob):
        return False
    key, namespace, reserved, hash_name, signature = fields
    inner, inner_end = _ssh_strings(signature, 0, 2)
    pinned = {base64.b64decode(k.split()[1]) for k in SIGNING_KEYS}
    return (key in pinned and namespace == SIGNATURE_NAMESPACE.encode()
            and reserved == b"" and hash_name in (b"sha256", b"sha512")
            and inner is not None and inner_end == len(signature)
            and inner[0] == b"ssh-ed25519" and len(inner[1]) == 64
            # Canonical: verifiers also accept S + L, a second encoding of
            # the same signature that ssh-keygen never writes.
            and int.from_bytes(inner[1][32:], "little") < _ED25519_ORDER)


def genuine_signature(payload, armored):
    """Whether armored is a pinned key's signature of payload, in the exact
    form ssh-keygen writes, checked by `ssh-keygen -Y verify` against the
    pinned keys only. Any doubt (no ssh-keygen, one inside the repository,
    an error or a timeout) is False, so the signature is checked in full."""
    if not SIGNING_KEYS or not _pinned_ssh_signature(armored):
        return False
    keygen = program("ssh-keygen")
    if keygen is None:
        return False
    try:
        top = _enclosing_repository()
        if in_current_folder(os.path.dirname(keygen), top) or in_current_folder(keygen, top):
            return False
        with tempfile.TemporaryDirectory() as folder:
            signers = os.path.join(folder, "signers")
            signature = os.path.join(folder, "signature")
            with open(signers, "wb") as handle:
                for key in SIGNING_KEYS:
                    handle.write(f'guard namespaces="{SIGNATURE_NAMESPACE}" {key}\n'.encode("ascii"))
            with open(signature, "wb") as handle:
                handle.write(armored)
            result = subprocess.run(
                [keygen, "-Y", "verify", "-f", signers, "-I", "guard",
                 "-n", SIGNATURE_NAMESPACE, "-s", signature],
                input=payload, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def commit_payload(raw):
    """What a commit's signature signs: the object without its gpgsig and
    gpgsig-sha256 headers (and their continuation lines), as git builds it."""
    head, separator, message = raw.partition(b"\n\n")
    kept, dropping = [], False
    for line in head.split(b"\n"):
        if not line.startswith(b" "):
            dropping = line.startswith(b"gpgsig")
        if not dropping:
            kept.append(line)
    return b"\n".join(kept) + separator + message


def split_signed_tag(raw):
    """A tag object split as git splits it: (payload, signature), the
    signature running from the last line that starts one to the end (empty
    if there is none). Earlier blocks are part of the message."""
    start, pos = len(raw), 0
    while pos < len(raw):
        if raw.startswith(_SIGNATURE_STARTS, pos):
            start = pos
        newline = raw.find(b"\n", pos)
        pos = len(raw) if newline < 0 else newline + 1
    return raw[:start], raw[start:]


def unfold(head) -> List[Tuple[bytes, bytes]]:
    """Header fields of a git object, as (key, value). A line starting with
    one space continues the previous field; that space is removed and the
    lines are joined with newlines. Refuses (exits) on anything else."""
    fields: List[Tuple[bytes, bytes]] = []
    for line in head.split(b"\n"):
        if line.startswith(b" "):
            if not fields:
                sys.exit("guard: refusing, could not read a git object header")
            key, value = fields[-1]
            fields[-1] = (key, value + b"\n" + line[1:])
            continue
        key, space, value = line.partition(b" ")
        if not space or not key:
            sys.exit("guard: refusing, could not read a git object header")
        fields.append((key, value))
    return fields


class Commit(NamedTuple):
    text: bytes                         # header text to check (see parse_commit)
    idents: List[Tuple[str, bytes, bytes]]  # (role, name, email) as stored
    mergetags: List[bytes]              # embedded tag objects
    message: bytes
    encoding: Optional[str]             # declared by an `encoding` header
    # Each gpgsig / gpgsig-sha256 value, with what it signs, or None where a
    # chance match can't be excused (see parse_commit).
    signatures: List[Tuple[Optional[bytes], bytes]]


_HEX_ID = re.compile(rb"[0-9a-f]{40}|[0-9a-f]{64}")
# "Name <email> seconds +zone". The name may be empty (old or imported
# commits); the email is always checked.
IDENT = re.compile(rb"(?:([^<>\n]*) )?<([^<>\n]*)> \d+ [+-]\d{4}")


def parse_commit(raw) -> Commit:
    """Splits a raw commit object into what the leak guard checks:
      - every header as text, except well-formed tree/parent ids (pure hex)
        and signatures, which are returned on their own;
      - each author/committer name and email (exactly one of each; git log
        only shows the first, so a second could hide an address);
      - each embedded tag (mergetag);
      - the message, and its declared text encoding (at most one).
    A signature gets its signed payload only when it is the commit's one
    signature header and the SHA-1 kind (`gpgsig`) that git verifies here;
    git joins repeated headers, so none of several is ever excused.
    Refuses (exits) on anything that doesn't have the expected shape."""
    head, separator, message = raw.partition(b"\n\n")
    if not separator:
        sys.exit("guard: refusing, could not read a commit object")
    text, idents, mergetags, encoding, signatures = [], [], [], None, []
    sha1 = False
    for key, value in unfold(head):
        if key == b"tree":
            sha1 = len(value) == 40
        if key in (b"tree", b"parent") and _HEX_ID.fullmatch(value):
            continue
        if key in (b"author", b"committer"):
            ident = IDENT.fullmatch(value)
            if ident is None:
                sys.exit("guard: refusing, could not read a commit's author or committer")
            idents.append((key.decode("ascii"), ident.group(1) or b"", ident.group(2)))
            continue
        if key in (b"gpgsig", b"gpgsig-sha256"):
            signatures.append((key, value + b"\n"))
            continue
        if key == b"mergetag":
            mergetags.append(value + b"\n")
            continue
        if key == b"encoding":
            # git reads the first; refuse a second rather than pick one.
            if encoding is not None:
                sys.exit("guard: refusing, a commit has more than one encoding header")
            encoding = value.decode("ascii", errors="replace")
        text.append(key + b" " + value)
    roles = sorted(role for role, _, _ in idents)
    if roles != ["author", "committer"]:
        sys.exit("guard: refusing, a commit needs exactly one author and one committer")
    excusable = sha1 and len(signatures) == 1 and signatures[0][0] == b"gpgsig"
    payload = commit_payload(raw) if excusable else None
    return Commit(b"\n".join(text), idents, mergetags, message, encoding,
                  [(payload, armored) for _, armored in signatures])


class Blobs:
    """Reads blobs through one long-lived `git cat-file --batch`, one request
    at a time (no --buffer, so git answers each request immediately and the
    two sides can't block each other). Use as a context manager."""

    def __enter__(self):
        self.proc = subprocess.Popen(
            [git_exe(), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
        return self

    def read(self, sha) -> Optional[bytes]:
        """The blob's bytes, or None if it is over textscan.MAX_SCAN_BYTES."""
        self.proc.stdin.write(sha.encode("ascii") + b"\n")
        self.proc.stdin.flush()
        header = self.proc.stdout.readline().split()
        if len(header) != 3 or header[0].decode("ascii") != sha or header[1] != b"blob":
            sys.exit("guard: refusing, could not read a file from git")
        size = int(header[2])
        if size > textscan.MAX_SCAN_BYTES:
            remaining = size + 1
            while remaining:
                chunk = self.proc.stdout.read(min(remaining, 1 << 20))
                if not chunk:
                    sys.exit("guard: refusing, could not read a file from git")
                remaining -= len(chunk)
            return None
        data = self.proc.stdout.read(size + 1)
        if len(data) != size + 1 or data[-1:] != b"\n":
            sys.exit("guard: refusing, could not read a file from git")
        return data[:-1]

    def __exit__(self, *exc):
        self.proc.stdin.close()
        self.proc.stdout.read()
        if self.proc.wait() != 0 and exc[0] is None:
            sys.exit("guard: refusing, 'git cat-file' failed")
        return False
