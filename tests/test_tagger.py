"""Tests for the metadata tagger."""

from __future__ import annotations

from pathlib import Path

import pytest

from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    LyricLine,
    LyricsSource,
    MatchSource,
    SyncedLyrics,
    TrackMatch,
    TrackResult,
)
from audio_matcher.core.tagger import AudioTagger, TagError


class TestAudioTagger:
    def test_dry_run_no_write(self, temp_dir: Path) -> None:
        f = temp_dir / "test.flac"
        f.write_bytes(b"dummy")
        af = AudioFile(path=f, format=AudioFormat.FLAC)
        match = TrackMatch(title="Test", artist="Artist", source=MatchSource.SHAZAM)
        tagger = AudioTagger()
        result = tagger.write(af, match, dry_run=True)
        assert result is True
        # File should be unchanged.
        assert f.read_bytes() == b"dummy"

    def test_unsupported_format_raises(self, temp_dir: Path) -> None:
        f = temp_dir / "test.flac"
        f.write_bytes(b"not valid audio")
        af = AudioFile(path=f, format=AudioFormat.FLAC)
        match = TrackMatch(title="X", artist="Y")
        tagger = AudioTagger()
        with pytest.raises(TagError):
            tagger.write(af, match)

    def test_lrc_sidecar_written(self, temp_dir: Path) -> None:
        """When config has write_lrc_sidecar=True, a .lrc file is created."""
        from audio_matcher.core.config import Config

        f = temp_dir / "test.flac"
        f.write_bytes(b"dummy")
        af = AudioFile(path=f, format=AudioFormat.FLAC)
        match = TrackMatch(title="Song", artist="Artist")
        lyrics = SyncedLyrics(
            lines=[LyricLine(timestamp_ms=1000, text="Hello")],
            source=LyricsSource.LRCLIB,
            raw_lrc="[00:01.00]Hello",
        )

        # Skip the real mutagen write by testing only the sidecar.
        config = Config(write_lrc_sidecar=True)
        tagger = AudioTagger(config=config)
        tagger._write_lrc_sidecar(f, "[00:01.00]Hello")
        lrc_path = f.with_suffix(".lrc")
        assert lrc_path.exists()
        assert lrc_path.read_text() == "[00:01.00]Hello"

    def test_backup_created_when_configured(self, temp_dir: Path) -> None:
        from audio_matcher.core.config import Config

        f = temp_dir / "song.flac"
        f.write_bytes(b"original content")
        af = AudioFile(path=f, format=AudioFormat.FLAC)
        config = Config(backup_original=True)
        tagger = AudioTagger(config=config)
        tagger._backup(f)
        bak = f.with_suffix(".flac.bak")
        assert bak.exists()
        assert bak.read_bytes() == b"original content"
