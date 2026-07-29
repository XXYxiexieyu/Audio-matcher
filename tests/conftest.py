"""Shared test fixtures for Audio Matcher."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

from audio_matcher.core.config import Config
from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    BatchState,
    ProcessingStatus,
    TrackMatch,
    TrackResult,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_audio_file(temp_dir: Path) -> AudioFile:
    """A basic AudioFile for tests."""
    p = temp_dir / "test.flac"
    p.touch()
    return AudioFile(
        path=p,
        format=AudioFormat.FLAC,
        duration_s=120.0,
        sample_rate=44100,
        channels=2,
        file_size_bytes=1024,
    )


@pytest.fixture
def sample_track_match() -> TrackMatch:
    """A fully-populated TrackMatch."""
    return TrackMatch(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        year=2024,
        track_number=3,
        confidence=0.95,
    )


@pytest.fixture
def sample_track_result(sample_audio_file: AudioFile, sample_track_match: TrackMatch) -> TrackResult:
    """A TrackResult with a successful match."""
    return TrackResult(
        audio_file=sample_audio_file,
        match=sample_track_match,
        status=ProcessingStatus.RECOGNIZED,
    )


@pytest.fixture
def temp_config_path(temp_dir: Path) -> Path:
    """Path to a temporary config file."""
    return temp_dir / "config.json"


@pytest.fixture
def mock_shazam_response() -> dict[str, Any]:
    """A realistic Shazam recognition response."""
    return {
        "track": {
            "key": "12345",
            "title": "Mock Song",
            "subtitle": "Mock Artist",
            "sections": [
                {
                    "type": "SONG",
                    "metadata": [
                        {"title": "Album", "text": "Mock Album"},
                    ],
                }
            ],
            "genres": {"primary": "Pop"},
        }
    }
