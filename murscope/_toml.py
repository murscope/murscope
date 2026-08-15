"""A deliberately small TOML reader for Python 3.9 and 3.10.

tomllib arrived in 3.11. DP2 forbids a dependency and DP3 pins the floor
at 3.9 - macOS full-disk access can only be granted to a concrete
interpreter and the system one is 3.9 - so the two together mean the
fallback has to be written here or the floor has to move.

It is small on purpose. murscope's config file is flat tables holding
strings, integers, booleans and arrays of strings, and that is exactly
what this reads. Everything else - floats, dates, inline tables, nested
arrays, dotted keys, multi-line strings - is refused by name and line
number rather than guessed at. A parser that quietly half-understands a
value is worse than one that says it cannot read it: the first produces
a board built on a misreading, the second produces a message.

The one shape allowed to span lines is an array, because a list of
markers is the config entry most likely to grow past a comfortable line
length and wrapping it must not change what a 3.9 user is allowed to
write versus a 3.12 one.
"""
from __future__ import annotations

BARE_KEY_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                     "abcdefghijklmnopqrstuvwxyz0123456789_-")
ESCAPES = {
    '"': '"', "\\": "\\", "b": "\b", "f": "\f",
    "n": "\n", "r": "\r", "t": "\t",
}


class TomlError(ValueError):
    """A config file this parser refuses to guess at."""


def _fail(lineno, message):
    raise TomlError("config.toml, line %d: %s" % (lineno, message))


def _read_basic_string(text, i, lineno):
    """Parse a "..." string starting at text[i] == '"'. Returns (value, i)."""
    if text.startswith('"""', i):
        _fail(lineno, "multi-line strings are not supported by the 3.9 "
                      "fallback parser; keep the value on one line.")
    out = []
    i += 1
    while i < len(text):
        ch = text[i]
        if ch == '"':
            return "".join(out), i + 1
        if ch == "\\":
            i += 1
            if i >= len(text):
                break
            esc = text[i]
            if esc in ESCAPES:
                out.append(ESCAPES[esc])
                i += 1
                continue
            if esc in ("u", "U"):
                width = 4 if esc == "u" else 8
                digits = text[i + 1:i + 1 + width]
                if len(digits) != width:
                    _fail(lineno, "truncated \\%s escape." % esc)
                try:
                    out.append(chr(int(digits, 16)))
                except ValueError:
                    _fail(lineno, "\\%s escape is not hexadecimal: %r" % (esc, digits))
                i += 1 + width
                continue
            _fail(lineno, "unknown escape sequence \\%s" % esc)
        else:
            out.append(ch)
            i += 1
    _fail(lineno, "unterminated string.")


def _read_literal_string(text, i, lineno):
    """Parse a '...' string starting at text[i] == \"'\". Returns (value, i)."""
    if text.startswith("'''", i):
        _fail(lineno, "multi-line strings are not supported by the 3.9 "
                      "fallback parser; keep the value on one line.")
    end = text.find("'", i + 1)
    if end < 0:
        _fail(lineno, "unterminated literal string.")
    return text[i + 1:end], end + 1


def _read_scalar(text, i, lineno):
    """Parse a bare scalar - integer or boolean - ending at , ] or #."""
    start = i
    while i < len(text) and text[i] not in ",]#":
        i += 1
    raw = text[start:i].strip()
    if raw == "true":
        return True, i
    if raw == "false":
        return False, i
    if not raw:
        _fail(lineno, "expected a value.")
    cleaned = raw.replace("_", "")
    if cleaned and (cleaned[0] in "+-" and cleaned[1:].isdigit() or cleaned.isdigit()):
        return int(cleaned, 10), i
    if raw.replace(".", "", 1).lstrip("+-").isdigit():
        _fail(lineno, "floating point values are not supported; murscope's "
                      "config has no use for one, so %r is more likely a typo "
                      "than an intention." % raw)
    _fail(lineno, "cannot read the value %r. This parser understands quoted "
                  "strings, integers, true/false, and arrays of strings." % raw)


def _read_array(text, i, lineno):
    """Parse [ ... ] starting at text[i] == '['. Returns (list, i)."""
    i += 1
    items = []
    expect_value = True
    while i < len(text):
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "#":
            i = len(text)
            break
        if ch == "]":
            return items, i + 1
        if ch == ",":
            if expect_value:
                _fail(lineno, "empty array element.")
            expect_value = True
            i += 1
            continue
        if not expect_value:
            _fail(lineno, "array elements must be separated by a comma.")
        if ch == '"':
            value, i = _read_basic_string(text, i, lineno)
        elif ch == "'":
            value, i = _read_literal_string(text, i, lineno)
        elif ch == "[":
            _fail(lineno, "nested arrays are not supported; murscope's config "
                          "uses flat arrays of strings.")
        elif ch == "{":
            _fail(lineno, "inline tables are not supported; use a [table] "
                          "header instead.")
        else:
            value, i = _read_scalar(text, i, lineno)
        items.append(value)
        expect_value = False
    _fail(lineno, "unterminated array.")


def _read_value(text, lineno):
    """Parse one complete value, then insist the rest of the line is empty."""
    i = 0
    while i < len(text) and text[i] in " \t":
        i += 1
    if i >= len(text):
        _fail(lineno, "key with no value.")
    ch = text[i]
    if ch == '"':
        value, i = _read_basic_string(text, i, lineno)
    elif ch == "'":
        value, i = _read_literal_string(text, i, lineno)
    elif ch == "[":
        value, i = _read_array(text, i, lineno)
    elif ch == "{":
        _fail(lineno, "inline tables are not supported; use a [table] header.")
    else:
        value, i = _read_scalar(text, i, lineno)
    rest = text[i:].strip()
    if rest and not rest.startswith("#"):
        _fail(lineno, "trailing text after the value: %r" % rest[:40])
    return value


def _join_array_lines(lines, index):
    """Collect a value that continues across lines until its array closes."""
    text = lines[index]
    depth = text.count("[") - text.count("]")
    consumed = 0
    while depth > 0 and index + consumed + 1 < len(lines):
        consumed += 1
        nxt = lines[index + consumed]
        text = text + "\n" + nxt
        depth += nxt.count("[") - nxt.count("]")
    return text, consumed


def loads(text):
    """Parse a TOML subset into a dict of dicts. Raises TomlError."""
    document = {}
    table = document
    table_name = ""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        lineno = index + 1
        line = lines[index]
        stripped = line.strip()
        index += 1
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            if stripped.startswith("[["):
                _fail(lineno, "arrays of tables are not supported.")
            if not stripped.endswith("]"):
                _fail(lineno, "unterminated table header.")
            name = stripped[1:-1].strip().strip('"').strip("'")
            if not name or any(c not in BARE_KEY_CHARS for c in name):
                _fail(lineno, "table names must be a single bare word; %r is "
                              "not one, and nested tables are not supported."
                              % name)
            if name in document and isinstance(document[name], dict):
                _fail(lineno, "table [%s] is defined twice." % name)
            document[name] = {}
            table = document[name]
            table_name = name
            continue
        if "=" not in stripped:
            _fail(lineno, "expected `key = value`.")
        key, _, raw = stripped.partition("=")
        key = key.strip().strip('"').strip("'")
        if not key or any(c not in BARE_KEY_CHARS for c in key):
            _fail(lineno, "%r is not a bare key. Dotted keys are not "
                          "supported; use a [table] header." % key)
        if key in table:
            _fail(lineno, "key %r is defined twice in %s."
                  % (key, "[%s]" % table_name if table_name else "the top level"))
        if raw.strip().startswith("["):
            joined, consumed = _join_array_lines([raw] + lines[index:], 0)
            index += consumed
        else:
            joined = raw
        table[key] = _read_value(joined, lineno)
    return document
