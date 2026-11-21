"""Readable views of file contents for the repository guards.

A guard must never skip a file because it doesn't look like plain UTF-8
text: UTF-16 and UTF-32 text is full of NUL bytes, and binary files can hold
readable text. Instead every file is read in several ways ("views") and a
match in any view counts. Nothing here guesses the encoding, so a wrong
guess can't let a match through.

Not inspected (yet): compressed or encoded content such as zip-based
formats, PDF streams and base64.
"""

# Files larger than this are refused rather than scanned or skipped.
MAX_SCAN_BYTES = 25 * 1024 * 1024


class TooLarge(Exception):
    """The data is over MAX_SCAN_BYTES and must be refused."""


def _strip_bom(text):
    return text[1:] if text.startswith("﻿") else text


def _is_utf8(data):
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def text_views(data):
    """Yields (name, text) pairs. The first view, named "", is the plain
    UTF-8 reading, whose line numbers match the file; the others are named
    after how they were read."""
    if len(data) > MAX_SCAN_BYTES:
        raise TooLarge()
    yield "", _strip_bom(data.decode("utf-8", errors="replace"))

    has_nul = b"\0" in data
    is_utf8 = _is_utf8(data)

    if not is_utf8:
        # Windows "ANSI" text, for non-ASCII patterns.
        yield "cp1252", _strip_bom(data.decode("cp1252", errors="replace"))
    if has_nul:
        # Removing NULs turns ASCII and Latin-1 text in UTF-16 or UTF-32 (any
        # byte order, any alignment, with or without a BOM) back into plain
        # text. Latin-1 keeps characters like "é" (E9 00 -> E9) intact.
        yield "nul-stripped", data.replace(b"\0", b"").decode("latin-1")
    if has_nul or not is_utf8:
        # Real UTF-16 readings, for non-ASCII text. Text made only of
        # non-ASCII characters (CJK, for example) may contain no NUL at all,
        # so these also run on anything that isn't valid UTF-8.
        for codec in ("utf-16-le", "utf-16-be"):
            for offset in (0, 1):
                yield codec, _strip_bom(data[offset:].decode(codec, errors="replace"))
    if has_nul:
        # Every UTF-32 code unit for an ordinary character contains NULs.
        for codec in ("utf-32-le", "utf-32-be"):
            for offset in range(4):
                yield codec, _strip_bom(data[offset:].decode(codec, errors="replace"))
