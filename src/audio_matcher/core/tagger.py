"""Metadata tagger — writes tags to audio files via mutagen.

Supported formats: FLAC (.flac), WAV (.wav), DSD (.dsf/.dff), MP3 (.mp3),
M4A (.m4a), AAC (.aac), OGG (.ogg), WMA (.wma), AIFF (.aiff)
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from audio_matcher.core.config import Config
from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    LyricsLanguage,
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

        if self.config.backup_original:
            self._backup(file.path)

        try:
            mf = self._open_mutagen(file.path)
            if mf is None:
                raise TagError(f"Unsupported format: {file.format.value}")

            # Clear all existing tags first to avoid stale metadata.
            self._clear_tags(mf)

            self._write_tags(mf, file.format, match)
            if lyrics and lyrics.raw_lrc:
                self._write_lyrics(mf, file.format, lyrics, self.config.lyrics_language)
            mf.save()

            if self.config.write_lrc_sidecar and lyrics and lyrics.raw_lrc:
                self._write_lrc_sidecar(file.path, lyrics.raw_lrc, suffix=".lrc")
                if lyrics.has_translation:
                    self._write_lrc_sidecar(file.path, lyrics.translated_lrc, suffix=".translation.lrc")
                if lyrics.has_romanized:
                    self._write_lrc_sidecar(file.path, lyrics.romanized_lrc, suffix=".romaji.lrc")

            logger.info("Tagged: %s → %s - %s", file.path.name, match.artist, match.title)
            return True
        except Exception as exc:
            logger.error("Failed to tag %s: %s", file.path.name, exc)
            raise TagError(str(exc)) from exc

    # ── Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _clear_tags(mf) -> None:
        """Remove all existing tags from the file."""
        try:
            mf.delete()
        except Exception:
            # Fallback: clear keys individually.
            keys = list(mf.keys()) if hasattr(mf, "keys") else []
            for k in keys:
                try:
                    del mf[k]
                except Exception:
                    pass

    @staticmethod
    def _open_mutagen(path: Path):
        """Open a file with mutagen (auto-detect format)."""
        import mutagen
        return mutagen.File(str(path))

    @classmethod
    def _write_tags(cls, mf, fmt: AudioFormat, match: TrackMatch) -> None:
        """Write the six standard fields, format-aware."""
        # Most formats work with generic mutagen key assignment.
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

    @classmethod
    def _write_lyrics(cls, mf, fmt: AudioFormat, lyrics: SyncedLyrics, language_mode: str) -> None:
        """Embed lyrics text(s), using format-appropriate frames.

        The number and type of lyrics fields written depends on
        *language_mode*.  For ID3 formats multiple USLT frames are
        distinguished by their ``desc`` field; for Vorbis formats
        custom tag keys are used.
        """
        language = LyricsLanguage(language_mode)
        entries: list[tuple[str, str, str]] = []  # (desc, lang_code, text)

        # Always write original.
        if lyrics.raw_lrc:
            entries.append(("", "eng", lyrics.raw_lrc))

        # Translation — for bilingual modes only.
        if language in (LyricsLanguage.BILINGUAL, LyricsLanguage.BILINGUAL_ROMAJI):
            if lyrics.translated_lrc:
                entries.append(("Translation", "chi", lyrics.translated_lrc))

        # Romaji — for romaji modes only.
        if language in (LyricsLanguage.JAPANESE_ROMAJI, LyricsLanguage.BILINGUAL_ROMAJI):
            if lyrics.romanized_lrc:
                entries.append(("Romanized", "eng", lyrics.romanized_lrc))

        # Route to format-specific writer.
        _ID3_FORMATS = (
            AudioFormat.MP3, AudioFormat.WAV, AudioFormat.DSF,
            AudioFormat.DFF, AudioFormat.AIFF,
        )
        _VORBIS_FORMATS = (AudioFormat.FLAC, AudioFormat.OGG)

        if fmt in _ID3_FORMATS:
            cls._write_lyrics_id3(mf, entries)
        elif fmt in _VORBIS_FORMATS:
            cls._write_lyrics_vorbis(mf, entries)
        else:
            # Fallback: write only original as plain key.
            if lyrics.raw_lrc:
                try:
                    mf["lyrics"] = lyrics.raw_lrc
                except Exception:
                    logger.debug("Could not embed lyrics for format %s", fmt.value)

    @classmethod
    def _write_lyrics_id3(cls, mf, entries: list[tuple[str, str, str]]) -> None:
        """Write multiple USLT frames to an ID3 tag object."""
        import mutagen.id3

        if not hasattr(mf, "tags") or mf.tags is None:
            return

        # Remove all existing USLT frames first.
        for key in list(mf.tags.keys()):
            if key.startswith("USLT"):
                del mf.tags[key]

        for desc, lang, text in entries:
            mf.tags.add(
                mutagen.id3.USLT(
                    encoding=3,  # UTF-8
                    lang=lang[:3],
                    desc=desc,
                    text=text,
                )
            )

    @classmethod
    def _write_lyrics_vorbis(cls, mf, entries: list[tuple[str, str, str]]) -> None:
        """Write Vorbis comment tags for lyrics.

        Original → LYRICS (standard key).
        Translation → LYRICS_TRANSLATION.
        Romanized → LYRICS_ROMANIZED.
        """
        _TAG_KEY = {
            "": "LYRICS",
            "Translation": "LYRICS_TRANSLATION",
            "Romanized": "LYRICS_ROMANIZED",
        }
        for desc, _lang, text in entries:
            key = _TAG_KEY.get(desc, f"LYRICS_{desc.upper()}")
            mf[key] = text

    @staticmethod
    def _write_lrc_sidecar(audio_path: Path, raw_lrc: str, suffix: str = ".lrc") -> None:
        """Write an LRC sidecar file next to the audio file."""
        lrc_path = audio_path.with_suffix(suffix)
        lrc_path.write_text(raw_lrc, encoding="utf-8")
        logger.debug("LRC sidecar written: %s", lrc_path.name)

    @staticmethod
    def _backup(path: Path) -> None:
        """Copy file to .bak before modifying."""
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
        logger.debug("Backup created: %s", bak.name)
