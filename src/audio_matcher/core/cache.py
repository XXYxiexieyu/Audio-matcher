"""File-based caches for fingerprints and lyrics.

Lightweight JSON-file caches to avoid redundant API calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from audio_matcher.core.models import Fingerprint, SyncedLyrics

logger = logging.getLogger("audio_matcher.cache")


class _JSONCache:
    """Base class for JSON-file caches."""

    def __init__(self, file_path: str | Path) -> None:
        self.path = Path(file_path)
        self._data: dict[str, dict] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt cache file %s, starting fresh", self.path)
                self._data = {}
        self._loaded = True

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)


class FingerprintCache(_JSONCache):
    """Cache for audio fingerprints, keyed by SHA-256 of file path."""

    def get(self, path: str | Path) -> Optional[Fingerprint]:
        """Return a cached fingerprint, or None."""
        self._ensure_loaded()
        key = self._hash_path(path)
        entry = self._data.get(key)
        if entry is None:
            return None
        logger.debug("Fingerprint cache hit: %s", Path(path).name)
        return Fingerprint(
            hash=entry["hash"],
            duration_s=entry.get("duration_s", 0.0),
            method=entry.get("method", "shazamio"),
        )

    def set(self, path: str | Path, fp: Fingerprint) -> None:
        """Store a fingerprint."""
        self._ensure_loaded()
        key = self._hash_path(path)
        self._data[key] = {
            "hash": fp.hash,
            "duration_s": fp.duration_s,
            "method": fp.method.value,
        }
        self._persist()

    @staticmethod
    def _hash_path(path: str | Path) -> str:
        return hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()


class LyricsCache(_JSONCache):
    """Cache for synced lyrics, keyed by normalised artist||title."""

    def get(self, artist: str, title: str) -> Optional[SyncedLyrics]:
        """Return cached lyrics, or None."""
        self._ensure_loaded()
        key = self._make_key(artist, title)
        entry = self._data.get(key)
        if entry is None:
            return None
        logger.debug("Lyrics cache hit: %s - %s", artist, title)
        from audio_matcher.core.models import LyricLine, LyricsSource
        translated_lines_data = entry.get("translated_lines", [])
        return SyncedLyrics(
            lines=[LyricLine(timestamp_ms=l["ts"], text=l["text"]) for l in entry.get("lines", [])],
            source=LyricsSource(entry.get("source", "lrclib")),
            raw_lrc=entry.get("raw_lrc", ""),
            translated_lrc=entry.get("translated_lrc", ""),
            translated_lines=[
                LyricLine(timestamp_ms=l["ts"], text=l["text"]) for l in translated_lines_data
            ],
        )

    def set(self, artist: str, title: str, lyrics: SyncedLyrics) -> None:
        """Store lyrics."""
        self._ensure_loaded()
        key = self._make_key(artist, title)
        self._data[key] = {
            "lines": [{"ts": l.timestamp_ms, "text": l.text} for l in lyrics.lines],
            "source": lyrics.source.value,
            "raw_lrc": lyrics.raw_lrc,
            "translated_lrc": lyrics.translated_lrc,
            "translated_lines": [
                {"ts": l.timestamp_ms, "text": l.text} for l in lyrics.translated_lines
            ],
        }
        self._persist()

    @staticmethod
    def _make_key(artist: str, title: str) -> str:
        return f"{_normalise(artist)}||{_normalise(title)}"


def _normalise(s: str) -> str:
    """Normalise a string for cache-key comparison."""
    return " ".join(s.lower().split())
