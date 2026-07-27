"""Tests for fingerprint and lyrics caches."""

from __future__ import annotations

from pathlib import Path

from audio_matcher.core.cache import FingerprintCache, LyricsCache
from audio_matcher.core.models import (
    Fingerprint,
    FingerprintMethod,
    LyricLine,
    LyricsSource,
    SyncedLyrics,
)


class TestFingerprintCache:
    def test_set_and_get(self, temp_dir: Path) -> None:
        cache = FingerprintCache(temp_dir / "fp_cache.json")
        fp = Fingerprint(hash="abc123", duration_s=30.0, method=FingerprintMethod.SHAZAMIO)
        cache.set("/music/song.flac", fp)
        cached = cache.get("/music/song.flac")
        assert cached is not None
        assert cached.hash == "abc123"
        assert cached.duration_s == 30.0
        assert cached.method == FingerprintMethod.SHAZAMIO

    def test_miss_returns_none(self, temp_dir: Path) -> None:
        cache = FingerprintCache(temp_dir / "fp_miss.json")
        assert cache.get("/nonexistent.flac") is None

    def test_path_change_invalidates_cache(self, temp_dir: Path) -> None:
        cache = FingerprintCache(temp_dir / "fp_inval.json")
        fp = Fingerprint(hash="xyz", duration_s=10.0)
        cache.set("/old/path.flac", fp)
        # Different path → different SHA-256 → miss
        assert cache.get("/new/path.flac") is None


class TestLyricsCache:
    def test_set_and_get(self, temp_dir: Path) -> None:
        cache = LyricsCache(temp_dir / "ly_cache.json")
        lyrics = SyncedLyrics(
            lines=[LyricLine(timestamp_ms=1000, text="Hello")],
            source=LyricsSource.LRCLIB,
            raw_lrc="[00:01.00]Hello",
        )
        cache.set("Artist", "Song", lyrics)
        cached = cache.get("Artist", "Song")
        assert cached is not None
        assert cached.source == LyricsSource.LRCLIB
        assert len(cached.lines) == 1
        assert cached.lines[0].text == "Hello"

    def test_normalised_keys(self, temp_dir: Path) -> None:
        cache = LyricsCache(temp_dir / "ly_norm.json")
        lyrics = SyncedLyrics(lines=[], raw_lrc="test")
        cache.set("  ARTIST  ", "  song title  ", lyrics)
        # Same key after normalisation.
        assert cache.get("artist", "song title") is not None
        assert cache.get("ARTIST", "SONG  TITLE") is not None

    def test_miss_returns_none(self, temp_dir: Path) -> None:
        cache = LyricsCache(temp_dir / "ly_miss.json")
        assert cache.get("Nobody", "Nothing") is None
