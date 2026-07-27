"""Metadata tagger — writes tags to audio files via mutagen."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from audio_matcher.core.config import Config
from audio_matcher.core.models import (
    AudioFile,
    SyncedLyrics,
    TrackMatch,
)

logger = logging.getLogger("audio_matcher.tagger")


class TagError(Exception):
    """Raised when tag writing fails."""


class AudioTagger:
    """Write metadata tags to audio files."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()

    def write(
        self,
        file: AudioFile,
        match: TrackMatch,
        lyrics: Optional[SyncedLyrics] = None,
        dry_run: bool = False,
    ) -> bool:
        """Write track metadata + lyrics to *file*.

        Returns:
            True on success.
        """
        if dry_run:
            logger.info("[DRY RUN] Would tag: %s → %s - %s", file.path.name, match.artist, match.title)
            return True

        # Backup if configured.
        if self.config.backup_original:
            self._backup(file.path)

        try:
            mf = self._open_mutagen(file.path)
            if mf is None:
                raise TagError(f"Unsupported format: {file.format.value}")

            self._write_tags(mf, match)
            if lyrics and lyrics.raw_lrc:
                self._write_lyrics(mf, lyrics.raw_lrc)
            mf.save()

            # Write LRC sidecar.
            if self.config.write_lrc_sidecar and lyrics and lyrics.raw_lrc:
                self._write_lrc_sidecar(file.path, lyrics.raw_lrc)

            logger.info("Tagged: %s → %s - %s", file.path.name, match.artist, match.title)
            return True
        except Exception as exc:
            logger.error("Failed to tag %s: %s", file.path.name, exc)
            raise TagError(str(exc)) from exc

    # ── Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _open_mutagen(path: Path):
        """Open a file with mutagen (auto-detect format)."""
        import mutagen
        return mutagen.File(str(path))

    @staticmethod
    def _write_tags(mf, match: TrackMatch) -> None:
        """Write the six standard fields."""
        if match.title:
            mf["title"] = match.title
        if match.artist:
            mf["artist"] = match.artist
        if match.album:
            mf["album"] = match.album
        if match.year:
            mf["date"] = str(match.year)
        if match.track_number:
            mf["tracknumber"] = str(match.track_number)

    @staticmethod
    def _write_lyrics(mf, raw_lrc: str) -> None:
        """Embed lyrics text in the file."""
        mf["lyrics"] = raw_lrc

    @staticmethod
    def _write_lrc_sidecar(audio_path: Path, raw_lrc: str) -> None:
        """Write a .lrc sidecar file next to the audio file."""
        lrc_path = audio_path.with_suffix(".lrc")
        lrc_path.write_text(raw_lrc, encoding="utf-8")
        logger.debug("LRC sidecar written: %s", lrc_path.name)

    @staticmethod
    def _backup(path: Path) -> None:
        """Copy file to .bak before modifying."""
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
        logger.debug("Backup created: %s", bak.name)
