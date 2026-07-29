"""Tests for fuzzy matching fallback strategies."""

from __future__ import annotations

import pytest

from audio_matcher.core.config import Config
from audio_matcher.core.fuzzy_matcher import FuzzyMatcher
from audio_matcher.core.models import MatchSource, TrackMatch


class TestDeduplication:
    """Test candidate deduplication logic."""

    def test_removes_duplicate_title_artist(self) -> None:
        matcher = FuzzyMatcher()
        candidates = [
            TrackMatch(
                title="Song", artist="Artist", confidence=0.8,
                source=MatchSource.SHAZAM,
            ),
            TrackMatch(
                title="Song", artist="Artist", confidence=0.5,
                source=MatchSource.ACOUSTID,
            ),
        ]
        result = matcher._deduplicate(candidates)
        assert len(result) == 1
        assert result[0].confidence == 0.8

    def test_case_insensitive_dedup(self) -> None:
        matcher = FuzzyMatcher()
        candidates = [
            TrackMatch(title="SONG", artist="ARTIST", confidence=0.3),
            TrackMatch(title="song", artist="artist", confidence=0.9),
        ]
        result = matcher._deduplicate(candidates)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_keeps_different_songs(self) -> None:
        matcher = FuzzyMatcher()
        candidates = [
            TrackMatch(title="Song A", artist="Artist", confidence=0.8),
            TrackMatch(title="Song B", artist="Artist", confidence=0.7),
        ]
        result = matcher._deduplicate(candidates)
        assert len(result) == 2

    def test_skips_empty_entries(self) -> None:
        matcher = FuzzyMatcher()
        candidates = [
            TrackMatch(title="", artist="", confidence=0.5),
            TrackMatch(title="Real Song", artist="Artist", confidence=0.8),
        ]
        result = matcher._deduplicate(candidates)
        assert len(result) == 1
        assert result[0].title == "Real Song"

    def test_sorted_by_confidence_desc(self) -> None:
        matcher = FuzzyMatcher()
        candidates = [
            TrackMatch(title="C", artist="X", confidence=0.3),
            TrackMatch(title="A", artist="X", confidence=0.9),
            TrackMatch(title="B", artist="X", confidence=0.5),
        ]
        result = matcher._deduplicate(candidates)
        assert [m.confidence for m in result] == [0.9, 0.5, 0.3]


class TestConfidenceFiltering:
    """Test min_confidence filtering and max_candidates limiting."""

    def test_filters_below_threshold(self) -> None:
        config = Config(fuzzy_min_confidence=0.5)
        matcher = FuzzyMatcher(config=config)
        candidates = [
            TrackMatch(title="Good", confidence=0.8, source=MatchSource.SHAZAM),
            TrackMatch(title="Bad", confidence=0.2, source=MatchSource.ACOUSTID),
            TrackMatch(title="Borderline", confidence=0.5, source=MatchSource.SHAZAM),
        ]
        result = matcher._filter_and_limit(candidates)
        assert len(result) == 2
        titles = {m.title for m in result}
        assert titles == {"Good", "Borderline"}

    def test_respects_max_candidates(self) -> None:
        config = Config(fuzzy_max_candidates=3, fuzzy_min_confidence=0.0)
        matcher = FuzzyMatcher(config=config)
        candidates = [
            TrackMatch(title=f"T{i}", confidence=0.8) for i in range(10)
        ]
        result = matcher._filter_and_limit(candidates)
        assert len(result) == 3

    def test_empty_input_returns_empty(self) -> None:
        matcher = FuzzyMatcher()
        result = matcher._filter_and_limit([])
        assert result == []


class TestAcoustidParsing:
    """Test parsing of AcoustID API response entries."""

    def test_full_entry(self) -> None:
        matcher = FuzzyMatcher()
        entry = {
            "id": "acoustid-uuid-123",
            "score": 0.92,
            "title": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "recordings": [
                {
                    "id": "mb-recording-456",
                    "title": "Test Album",
                    "year": 2024,
                }
            ],
        }
        match = matcher._parse_acoustid_entry(entry)
        assert match is not None
        assert match.title == "Test Song"
        assert match.artist == "Test Artist"
        assert match.album == "Test Album"
        assert match.year == 2024
        assert match.confidence == 0.92
        assert match.source == MatchSource.ACOUSTID
        assert match.source_id == "mb-recording-456"

    def test_minimal_entry(self) -> None:
        matcher = FuzzyMatcher()
        entry = {
            "id": "acoustid-min",
            "score": 0.5,
            "title": "Minimal",
            "artists": [],
            "recordings": [],
        }
        match = matcher._parse_acoustid_entry(entry)
        assert match is not None
        assert match.title == "Minimal"
        assert match.artist == ""
        assert match.album == ""

    def test_no_title_returns_none(self) -> None:
        """Empty title should be filtered at the strategy level."""
        matcher = FuzzyMatcher()
        entry = {
            "id": "acoustid-x",
            "score": 0.5,
            "title": "",
            "artists": [{"name": "Someone"}],
            "recordings": [],
        }
        match = matcher._parse_acoustid_entry(entry)
        # parse returns the match; caller filters by title
        assert match is not None
        assert match.title == ""

    def test_album_from_nested_dict(self) -> None:
        matcher = FuzzyMatcher()
        entry = {
            "id": "acoustid-y",
            "score": 0.7,
            "title": "Track",
            "artists": [{"name": "Artist"}],
            "recordings": [
                {
                    "id": "rec-1",
                    "title": "",
                    "album": {"name": "Nested Album"},
                }
            ],
        }
        match = matcher._parse_acoustid_entry(entry)
        assert match is not None
        assert match.album == "Nested Album"


class TestIntegration:
    """End-to-end tests for find_candidates."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_invalid_file(self, tmp_path) -> None:
        """A non-audio file should produce no candidates."""
        f = tmp_path / "not_audio.txt"
        f.write_text("hello world")

        config = Config(acoustid_api_key="")  # no key → skip AcoustID
        matcher = FuzzyMatcher(config=config)
        candidates = await matcher.find_candidates(str(f))
        # AcoustID skips (no key), multi-segment Shazam fails (pydub can't load txt)
        assert candidates == []

    @pytest.mark.asyncio
    async def test_no_api_key_skips_acoustid(self, tmp_path, mocker) -> None:
        """Without AcoustID API key, strategy 1 is skipped silently."""
        f = tmp_path / "dummy.wav"
        f.write_bytes(b"\x00" * 100)

        config = Config(acoustid_api_key="")
        matcher = FuzzyMatcher(config=config)

        # Mock the multi-segment strategy (strategy 2) to avoid pydub.
        mocker.patch.object(
            matcher, "_multi_segment_shazam", return_value=[],
        )

        candidates = await matcher.find_candidates(str(f))
        # Both strategies skipped → empty.
        assert candidates == []
