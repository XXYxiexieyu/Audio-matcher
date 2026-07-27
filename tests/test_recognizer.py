"""Tests for recognizer (response parsing)."""

from __future__ import annotations

from pathlib import Path

from audio_matcher.core.models import MatchSource
from audio_matcher.core.recognizer import Recognizer


class TestShazamResponseParsing:
    def test_valid_response(self, mock_shazam_response: dict) -> None:
        recognizer = Recognizer()
        match = recognizer._parse_shazam_response(mock_shazam_response)
        assert match is not None
        assert match.title == "Mock Song"
        assert match.artist == "Mock Artist"
        assert match.album == "Mock Album"
        assert match.source == MatchSource.SHAZAM
        assert match.confidence > 0

    def test_empty_response(self) -> None:
        recognizer = Recognizer()
        match = recognizer._parse_shazam_response({})
        assert match is None

    def test_no_track_field(self) -> None:
        recognizer = Recognizer()
        match = recognizer._parse_shazam_response({"not_track": {}})
        assert match is None

    def test_minimal_response(self) -> None:
        """Response with just title gives a partial match."""
        recognizer = Recognizer()
        match = recognizer._parse_shazam_response({
            "track": {
                "key": "123",
                "title": "Minimal",
                "subtitle": "",
                "sections": [],
            }
        })
        assert match is not None
        assert match.title == "Minimal"
        assert match.artist == ""
        assert match.confidence == 0.3  # lower without artist


class TestAcoustidResponseParsing:
    def test_valid_response(self) -> None:
        recognizer = Recognizer()
        results = [{
            "id": "acoustid-123",
            "title": "Acoustid Song",
            "artists": [{"name": "Artist Name"}],
            "score": 0.95,
            "recordings": [{
                "title": "Test Album",
                "year": "2024",
            }],
        }]
        match = recognizer._parse_acoustid_response(results)
        assert match is not None
        assert match.title == "Acoustid Song"
        assert match.artist == "Artist Name"
        assert match.album == "Test Album"
        assert match.year == 2024
        assert match.source == MatchSource.ACOUSTID

    def test_empty_results(self) -> None:
        recognizer = Recognizer()
        match = recognizer._parse_acoustid_response([])
        assert match is None

    def test_minimal_acoustid(self) -> None:
        recognizer = Recognizer()
        results = [{
            "id": "min",
            "score": 0.5,
        }]
        match = recognizer._parse_acoustid_response(results)
        assert match is not None
        assert match.title == ""
        assert match.artist == ""
