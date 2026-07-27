"""Resume / batch-state management.

Writes a JSON state file so long-running batches can be interrupted and
resumed without re-processing completed files.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from audio_matcher.core.models import AudioFile, BatchState, ProcessingStatus, TrackResult

logger = logging.getLogger("audio_matcher.state")


class StateManager:
    """Manages batch-processing state for resume support."""

    def __init__(self, config_dir: Optional[str | Path] = None) -> None:
        if config_dir is None:
            from audio_matcher.core.config import DEFAULT_CONFIG_DIR
            self._state_dir = Path(DEFAULT_CONFIG_DIR) / "state"
        else:
            self._state_dir = Path(config_dir) / "state"

    # ── Public API ───────────────────────────────────────────────────────

    def create(self, files: list[AudioFile], root_directory: str | Path) -> BatchState:
        """Create a fresh BatchState for the given file list."""
        now = _utc_now()
        state = BatchState(
            total_files=len(files),
            completed=0,
            results={},
            started_at=now,
            updated_at=now,
            root_directory=str(Path(root_directory).resolve()),
        )
        # Pre-populate with PENDING entries.
        for f in files:
            tr = TrackResult(audio_file=f, status=ProcessingStatus.PENDING)
            state.results[f.id] = tr
        return state

    def save(self, state: BatchState, state_path: str | Path) -> None:
        """Persist state atomically (write temp + rename)."""
        state.updated_at = _utc_now()
        sp = Path(state_path)
        sp.parent.mkdir(parents=True, exist_ok=True)
        data = _serialise_state(state)
        # Atomic write.
        fd, tmp = tempfile.mkstemp(dir=sp.parent, prefix=".state_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, sp)
        except Exception:
            os.unlink(tmp)
            raise

    def load(self, state_path: str | Path) -> BatchState:
        """Load a previously saved state file."""
        sp = Path(state_path)
        if not sp.exists():
            raise FileNotFoundError(f"State file not found: {sp}")
        with open(sp, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return _deserialise_state(data)

    def update_result(self, state: BatchState, result: TrackResult) -> None:
        """Merge a result into the state and increment completed count."""
        key = result.audio_file.id
        old_status = state.results.get(key, TrackResult(audio_file=result.audio_file)).status
        state.results[key] = result
        if old_status != ProcessingStatus.TAGGED and result.status == ProcessingStatus.TAGGED:
            state.completed += 1

    def pending_files(self, state: BatchState) -> list[AudioFile]:
        """Return files still PENDING or in ERROR (for retry)."""
        return [
            r.audio_file for r in state.results.values()
            if r.status in (ProcessingStatus.PENDING, ProcessingStatus.ERROR)
        ]


# ── Helpers ────────────────────────────────────────────────────────────────


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialise_state(state: BatchState) -> dict:
    return {
        "total_files": state.total_files,
        "completed": state.completed,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
        "root_directory": state.root_directory,
        "version": state.version,
        "results": {
            key: _serialise_result(tr) for key, tr in state.results.items()
        },
    }


def _deserialise_state(data: dict) -> BatchState:
    state = BatchState(
        total_files=data.get("total_files", 0),
        completed=data.get("completed", 0),
        started_at=data.get("started_at", ""),
        updated_at=data.get("updated_at", ""),
        root_directory=data.get("root_directory", ""),
        version=data.get("version", "0.0.1"),
    )
    for key, rd in data.get("results", {}).items():
        state.results[key] = _deserialise_result(rd)
    return state


def _serialise_result(tr: TrackResult) -> dict:
    return {
        "path": str(tr.audio_file.path),
        "format": tr.audio_file.format.value,
        "duration_s": tr.audio_file.duration_s,
        "status": tr.status.value,
        "error": tr.error,
        "edited": tr.edited,
        "match": {
            "title": tr.match.title,
            "artist": tr.match.artist,
            "album": tr.match.album,
            "year": tr.match.year,
            "track_number": tr.match.track_number,
            "confidence": tr.match.confidence,
            "source": tr.match.source.value,
            "source_id": tr.match.source_id,
        } if tr.match else None,
        "lyrics_source": tr.lyrics.source.value if tr.lyrics else None,
        "lyrics_raw": tr.lyrics.raw_lrc if tr.lyrics else None,
    }


def _deserialise_result(data: dict) -> TrackResult:
    from audio_matcher.core.models import (
        AudioFile,
        AudioFormat,
        LyricLine,
        LyricsSource,
        MatchSource,
        SyncedLyrics,
        TrackMatch,
    )
    af = AudioFile(
        path=Path(data["path"]),
        format=AudioFormat(data.get("format", "unknown")),
        duration_s=data.get("duration_s", 0.0),
    )
    match = None
    if data.get("match"):
        md = data["match"]
        match = TrackMatch(
            title=md.get("title", ""),
            artist=md.get("artist", ""),
            album=md.get("album", ""),
            year=md.get("year"),
            track_number=md.get("track_number"),
            confidence=md.get("confidence", 0.0),
            source=MatchSource(md.get("source", "shazam")),
            source_id=md.get("source_id", ""),
        )
    lyrics = None
    if data.get("lyrics_raw"):
        lyrics = SyncedLyrics(
            lines=[],  # Lines not serialised individually in v0.0.1
            source=LyricsSource(data.get("lyrics_source", "lrclib")),
            raw_lrc=data.get("lyrics_raw", ""),
        )
    return TrackResult(
        audio_file=af,
        match=match,
        lyrics=lyrics,
        status=ProcessingStatus(data.get("status", "pending")),
        error=data.get("error"),
        edited=data.get("edited", False),
    )
