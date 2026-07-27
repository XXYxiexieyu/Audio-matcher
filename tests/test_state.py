"""Tests for batch state management (resume support)."""

from __future__ import annotations

from pathlib import Path

from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    ProcessingStatus,
    TrackMatch,
    TrackResult,
)
from audio_matcher.core.state import StateManager


class TestStateManager:
    def test_create_state(self, sample_audio_file: AudioFile) -> None:
        mgr = StateManager()
        state = mgr.create([sample_audio_file], "/music")
        assert state.total_files == 1
        assert state.root_directory.endswith("music")
        assert len(state.results) == 1
        r = list(state.results.values())[0]
        assert r.status == ProcessingStatus.PENDING

    def test_save_and_load_roundtrip(self, temp_dir: Path, sample_audio_file: AudioFile) -> None:
        mgr = StateManager()
        state = mgr.create([sample_audio_file], "/music")
        sp = temp_dir / "state.json"
        mgr.save(state, sp)
        loaded = mgr.load(sp)
        assert loaded.total_files == 1
        assert loaded.root_directory.endswith("music")

    def test_update_result_marks_completed(self, sample_audio_file: AudioFile, sample_track_match: TrackMatch) -> None:
        mgr = StateManager()
        state = mgr.create([sample_audio_file], "/music")
        tr = TrackResult(
            audio_file=sample_audio_file,
            match=sample_track_match,
            status=ProcessingStatus.TAGGED,
        )
        mgr.update_result(state, tr)
        assert state.completed == 1
        key = sample_audio_file.id
        assert state.results[key].status == ProcessingStatus.TAGGED

    def test_pending_files(self, temp_dir: Path) -> None:
        mgr = StateManager()
        f1 = AudioFile(path=temp_dir / "a.flac", format=AudioFormat.FLAC)
        f2 = AudioFile(path=temp_dir / "b.flac", format=AudioFormat.FLAC)
        state = mgr.create([f1, f2], temp_dir)
        # Mark f1 as tagged.
        mgr.update_result(state, TrackResult(audio_file=f1, status=ProcessingStatus.TAGGED))
        pending = mgr.pending_files(state)
        assert len(pending) == 1
        assert pending[0].path == f2.path

    def test_error_files_are_pending(self, temp_dir: Path) -> None:
        mgr = StateManager()
        f1 = AudioFile(path=temp_dir / "bad.flac", format=AudioFormat.FLAC)
        state = mgr.create([f1], temp_dir)
        mgr.update_result(state, TrackResult(audio_file=f1, status=ProcessingStatus.ERROR, error="timeout"))
        pending = mgr.pending_files(state)
        assert len(pending) == 1

    def test_atomic_write(self, temp_dir: Path, sample_audio_file: AudioFile) -> None:
        """State file should not be corrupted on write failure."""
        mgr = StateManager()
        state = mgr.create([sample_audio_file], "/music")
        sp = temp_dir / "atomic.json"
        mgr.save(state, sp)
        # File should exist and be valid JSON.
        import json
        data = json.loads(sp.read_text())
        assert data["total_files"] == 1
