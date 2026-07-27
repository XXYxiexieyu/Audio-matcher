"""Tests for core data models."""

from __future__ import annotations

from pathlib import Path

from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    BatchState,
    FingerprintMethod,
    LyricLine,
    LyricsSource,
    MatchSource,
    ProcessingStatus,
    SyncedLyrics,
    TrackMatch,
    TrackResult,
)


class TestAudioFormat:
    def test_common_formats(self) -> None:
        assert AudioFormat.FLAC == "flac"
        assert AudioFormat.WAV == "wav"
        assert AudioFormat.MP3 == "mp3"

    def test_from_string(self) -> None:
        assert AudioFormat("flac") == AudioFormat.FLAC


class TestAudioFile:
    def test_defaults(self) -> None:
        af = AudioFile(path=Path("/tmp/test.flac"))
        assert af.format == AudioFormat.UNKNOWN
        assert af.duration_s == 0.0

    def test_id_is_absolute_path(self, tmp_path: Path) -> None:
        af = AudioFile(path=tmp_path / "song.wav")
        assert af.id == str(af.path.resolve())


class TestTrackMatch:
    def test_defaults(self) -> None:
        tm = TrackMatch()
        assert tm.title == ""
        assert tm.confidence == 0.0

    def test_full_match(self) -> None:
        tm = TrackMatch(
            title="Song", artist="Artist", album="Album",
            year=2024, track_number=5, confidence=0.9,
            source=MatchSource.SHAZAM,
        )
        assert tm.title == "Song"
        assert tm.year == 2024
        assert tm.confidence == 0.9


class TestTrackResult:
    def test_is_successful_with_match(self, sample_audio_file: AudioFile, sample_track_match: TrackMatch) -> None:
        tr = TrackResult(audio_file=sample_audio_file, match=sample_track_match)
        assert tr.is_successful is True

    def test_is_successful_without_match(self, sample_audio_file: AudioFile) -> None:
        tr = TrackResult(audio_file=sample_audio_file)
        assert tr.is_successful is False

    def test_edited_flag(self, sample_audio_file: AudioFile) -> None:
        tr = TrackResult(audio_file=sample_audio_file)
        assert tr.edited is False
        tr.edited = True
        assert tr.edited is True


class TestSyncedLyrics:
    def test_defaults(self) -> None:
        sl = SyncedLyrics()
        assert sl.lines == []
        assert sl.source == LyricsSource.LRCLIB

    def test_with_lines(self) -> None:
        lines = [LyricLine(timestamp_ms=1000, text="Hello")]
        sl = SyncedLyrics(lines=lines, source=LyricsSource.NETEASE, raw_lrc="[00:01.00]Hello")
        assert len(sl.lines) == 1
        assert sl.source == LyricsSource.NETEASE


class TestBatchState:
    def test_defaults(self) -> None:
        bs = BatchState()
        assert bs.total_files == 0
        assert bs.completed == 0
        assert bs.results == {}

    def test_tracks_progress(self) -> None:
        bs = BatchState(total_files=10, completed=5)
        assert bs.total_files == 10
        assert bs.completed == 5
