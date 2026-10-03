"""Turn a raw downloaded file (gz / zip / plain xml, any encoding) into UTF-8 XML bytes.

Israeli chains publish under the Price Transparency Law, but each one does it a
little differently:

* most files are gzip, some are actually ZIP archives with a ``.gz`` extension
* most are UTF-8, some are UTF-16 (with BOM) and some are ISO-8859-8 / cp1255
* some declare one encoding in the XML prolog and use another

Everything here is defensive so that one odd file never stops a daily run.
"""

from __future__ import annotations

import gzip
import io
import re
import zipfile
import zlib

_PROLOG_RE = re.compile(rb"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
_ENCODING_RE = re.compile(rb"encoding\s*=\s*[\"']([A-Za-z0-9_\-]+)[\"']", re.IGNORECASE)

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"


class DecodeError(ValueError):
    """Raised when a file cannot be turned into XML."""


def decompress(data: bytes) -> bytes:
    """Return the raw XML bytes from gzip, zip or plain content."""
    if data.startswith(GZIP_MAGIC):
        try:
            return gzip.decompress(data)
        except (OSError, EOFError):
            # Truncated upload on the chain's side (it happens). Keep whatever
            # decompresses cleanly; the XML parser runs in recover mode and the
            # last, cut-off item is dropped.
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
            try:
                partial = inflater.decompress(data)
            except zlib.error as exc:
                raise DecodeError(f"corrupt gzip: {exc}") from exc
            if not partial:
                raise DecodeError("corrupt gzip: nothing recoverable")
            return partial
    if data.startswith(ZIP_MAGIC):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = [m for m in zf.namelist() if not m.endswith("/")]
            if not members:
                raise DecodeError("empty zip archive")
            return zf.read(members[0])
    return data


def _strip_prolog(xml: bytes) -> bytes:
    return _PROLOG_RE.sub(b"", xml, count=1)


def to_text(xml: bytes) -> str:
    """Decode XML bytes to str, trying the most likely encodings in order."""
    if xml.startswith(b"\xff\xfe") or xml.startswith(b"\xfe\xff"):
        return xml.decode("utf-16")
    if xml.startswith(b"\xef\xbb\xbf"):
        xml = xml[3:]

    declared = None
    match = _ENCODING_RE.search(xml[:200])
    if match:
        declared = match.group(1).decode("ascii").lower()

    # UTF-8 first: several chains label UTF-8 files as ISO-8859-8.
    # A real ISO-8859-8 Hebrew file almost never decodes as valid UTF-8.
    candidates = ["utf-8"]
    if declared and declared not in candidates:
        candidates.append(declared)
    candidates += ["cp1255", "iso-8859-8"]

    for enc in candidates:
        try:
            return xml.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return xml.decode("utf-8", errors="replace")


def to_utf8_xml(data: bytes) -> bytes:
    """Full pipeline: decompress → decode → re-encode as UTF-8 without a prolog."""
    raw = decompress(data)
    if not raw.strip():
        raise DecodeError("empty file")
    text = to_text(raw)
    text = text.lstrip("﻿")
    body = _strip_prolog(text.encode("utf-8"))
    return body
