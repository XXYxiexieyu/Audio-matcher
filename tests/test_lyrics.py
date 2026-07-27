"""Tests for lyrics fetching and LRC parsing."""

from __future__ import annotations

from audio_matcher.core.lyrics import LyricsFetcher
from audio_matcher.core.models import LyricsSource, TrackMatch


class TestLrcParsing:
    def test_simple_lrc(self) -> None:
        raw = "[00:01.00]Hello world\n[00:05.50]Second line"
        lines = LyricsFetcher._parse_lrc(raw)
        assert len(lines) == 2
        assert lines[0].timestamp_ms == 1000
        assert lines[0].text == "Hello world"
        assert lines[1].timestamp_ms == 5500

    def test_mm_ss_format(self) -> None:
        """Format [mm:ss] without centiseconds."""
        raw = "[01:30]A line\n[02:00]Another"
        lines = LyricsFetcher._parse_lrc(raw)
        assert lines[0].timestamp_ms == 90000  # 1:30 = 90s
        assert lines[1].timestamp_ms == 120000  # 2:00 = 120s

    def test_mmm_ss_format(self) -> None:
        """Format [mmm:ss] for long tracks."""
        raw = "[100:00]Very long track"
        lines = LyricsFetcher._parse_lrc(raw)
        assert lines[0].timestamp_ms == 6000000  # 100 min

    def test_empty_lines_ignored(self) -> None:
        raw = "\n[00:01.00]Text\n\n"
        lines = LyricsFetcher._parse_lrc(raw)
        assert len(lines) == 1

    def test_metadata_tags_skipped(self) -> None:
        raw = "[ti:Title]\n[ar:Artist]\n[00:01.00]Actual lyric"
        lines = LyricsFetcher._parse_lrc(raw)
        # Title and Artist lines have no mm:ss pattern → they're dropped.
        assert len(lines) == 1
        assert lines[0].text == "Actual lyric"


class TestLyricsFetcher:
    async def test_no_artist_title_returns_none(self) -> None:
        fetcher = LyricsFetcher()
        match = TrackMatch(title="", artist="")
        result = await fetcher.fetch(match)
        assert result is None

    async def test_cache_hit(self, temp_dir) -> None:
        from audio_matcher.core.cache import LyricsCache
        from audio_matcher.core.models import SyncedLyrics

        cache = LyricsCache(temp_dir / "ly.json")
        lyrics = SyncedLyrics(lines=[], source=LyricsSource.LRCLIB, raw_lrc="cached")
        cache.set("Artist", "Title", lyrics)

        fetcher = LyricsFetcher(cache=cache)
        result = await fetcher.fetch(TrackMatch(title="Title", artist="Artist"))
        assert result is not None
        assert result.raw_lrc == "cached"
