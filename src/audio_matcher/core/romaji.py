"""Japanese romaji conversion using pykakasi (optional dependency).

These functions silently fall back to returning the input unchanged when
pykakasi is not installed, so romaji mode degrades gracefully to
original-only behaviour.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("audio_matcher.romaji")

# Timestamp-prefix pattern for LRC lines: [mm:ss.xx] or [mm:ss]
_LRC_TS = re.compile(r"(\[\d{1,3}:\d{2}(?:\.\d{1,3})?\])(.*)")


def lrc_to_romaji(raw_lrc: str) -> str:
    """Convert Japanese text in LRC-formatted lyrics to romaji.

    Preserves timestamp prefixes; only the text portion is converted.
    Metadata lines (``[ti:...]``, ``[ar:...]``, etc.) and blank lines
    pass through unchanged.

    Falls back to returning *raw_lrc* unchanged when pykakasi is not
    available.
    """
    if not raw_lrc:
        return raw_lrc

    try:
        import pykakasi  # noqa: F811
    except ImportError:
        logger.debug("pykakasi not installed – romaji conversion skipped")
        return raw_lrc

    kks = pykakasi.kakasi()
    result_lines: list[str] = []
    for line in raw_lrc.splitlines():
        line = line.strip()
        if not line:
            result_lines.append("")
            continue
        m = _LRC_TS.match(line)
        if m:
            prefix, text = m.group(1), m.group(2).strip()
            if text:
                converted = kks.convert(text)
                romaji = "".join(item["hepburn"] for item in converted)
                result_lines.append(f"{prefix}{romaji}")
            else:
                result_lines.append(line)
        else:
            # Metadata / header line — keep as-is.
            result_lines.append(line)
    return "\n".join(result_lines)


def text_to_romaji(text: str) -> str:
    """Convert a plain Japanese string to romaji (no LRC metadata)."""
    if not text:
        return text

    try:
        import pykakasi  # noqa: F811
    except ImportError:
        return text

    kks = pykakasi.kakasi()
    return "".join(item["hepburn"] for item in kks.convert(text))
