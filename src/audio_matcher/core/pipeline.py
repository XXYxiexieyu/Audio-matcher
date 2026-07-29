"""Pipeline orchestrator — ties together scanner, fingerprinter, recognizer, lyrics, tagger.

Processes audio files in parallel with progress tracking and resume support.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Callable, Optional

from audio_matcher.core.cache import FingerprintCache, LyricsCache
from audio_matcher.core.config import Config
from audio_matcher.core.fingerprinter import FingerprintError, Fingerprinter
from audio_matcher.core.fuzzy_matcher import FuzzyMatcher
from audio_matcher.core.lyrics import LyricsFetcher
from audio_matcher.core.models import (
    AudioFile,
    Fingerprint,
    MatchSource,
    ProcessingStatus,
    SyncedLyrics,
    TrackMatch,
    TrackResult,
)
from audio_matcher.core.recognizer import Recognizer
from audio_matcher.core.scanner import AudioScanner
from audio_matcher.core.state import StateManager
from audio_matcher.core.tagger import AudioTagger

logger = logging.getLogger("audio_matcher.pipeline")

# Callback type: (current: int, total: int, filename: str)
ProgressCallback = Callable[[int, int, str], None]


class Pipeline:
    """Orchestrates the full audio matching pipeline."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.scanner = AudioScanner(self.config)
        self.state_mgr = StateManager()
        self._fp_cache: Optional[FingerprintCache] = None
        self._ly_cache: Optional[LyricsCache] = None
        self._progress_cb: Optional[ProgressCallback] = None

    @property
    def fingerprint_cache(self) -> FingerprintCache:
        if self._fp_cache is None:
            self._fp_cache = FingerprintCache(
                Path(self.config.cache_dir) / "fingerprints.json"
            )
        return self._fp_cache

    @property
    def lyrics_cache(self) -> LyricsCache:
        if self._ly_cache is None:
            self._ly_cache = LyricsCache(
                Path(self.config.cache_dir) / "lyrics.json"
            )
        return self._ly_cache

    # ── Main entry ───────────────────────────────────────────────────────

    async def run(
        self,
        root: str | Path,
        *,
        resume_path: Optional[str | Path] = None,
        interactive: bool = False,
        dry_run: bool = False,
        no_lyrics: bool = False,
        rename_files: bool = False,
        files: Optional[list] = None,
        lyrics_language: str = "original_only",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> list[TrackResult]:
        """Run the full pipeline on all audio files under *root*.

        Args:
            files: Pre-filtered file list (GUI).  When provided the
                   internal scanner is skipped — only these files are
                   processed.
            lyrics_language: One of ``LyricsLanguage`` values; controls
                   which lyrics variants are embedded.
        """
        root = Path(root).resolve()
        self.config.lyrics_language = lyrics_language
        self._progress_cb = progress_callback
        completed_count = 0

        if files is not None:
            # Use pre-filtered file list from GUI / caller.
            if not files:
                logger.warning("No files selected for processing")
                return []
        elif resume_path and Path(resume_path).exists():
            state = self.state_mgr.load(resume_path)
            files = self.state_mgr.pending_files(state)
        else:
            files = self.scanner.scan(root)
            if not files:
                logger.warning("No audio files found in %s", root)
                return []

        total = len(files)

        if resume_path and Path(resume_path).exists():
            state = self.state_mgr.load(resume_path)
        else:
            state = self.state_mgr.create(files, root)
            state_path = self._default_state_path(root)
            self.state_mgr.save(state, state_path)

        state_path = resume_path or self._default_state_path(root)
        semaphore = asyncio.Semaphore(self.config.max_workers)
        results: list[TrackResult] = []

        async def _process_one(file: AudioFile) -> TrackResult:
            nonlocal completed_count
            async with semaphore:
                result = await self._process_file(file, no_lyrics=no_lyrics)

                if not interactive and not dry_run and result.match:
                    tagger = AudioTagger(self.config)
                    try:
                        tagger.write(file, result.match, result.lyrics, dry_run=False)
                        result.status = ProcessingStatus.TAGGED

                        # Rename file to "Artist - Title.ext" if requested.
                        if rename_files:
                            new_path = self._rename_file(file, result.match)
                            if new_path:
                                result.audio_file.path = new_path
                    except Exception as exc:
                        result.error = str(exc)
                        result.status = ProcessingStatus.ERROR
                elif dry_run and result.match:
                    result.status = ProcessingStatus.TAGGED

                self.state_mgr.update_result(state, result)
                self.state_mgr.save(state, state_path)
                results.append(result)

                completed_count += 1
                if self._progress_cb:
                    try:
                        fname = result.audio_file.path.name
                        self._progress_cb(completed_count, total, fname)
                    except Exception:
                        pass

                return result

        tasks = [_process_one(f) for f in files]
        await asyncio.gather(*tasks)

        tagged = sum(1 for r in results if r.status == ProcessingStatus.TAGGED)
        errors = sum(1 for r in results if r.status == ProcessingStatus.ERROR)
        logger.info("Done: %d tagged, %d errors, %d total", tagged, errors, len(results))

        return results

    # ── Per-file processing ──────────────────────────────────────────────

    async def _process_file(self, file: AudioFile, *, no_lyrics: bool = False) -> TrackResult:
        """Run the pipeline on a single file."""
        result = TrackResult(audio_file=file, status=ProcessingStatus.PENDING)

        try:
            # 1. Fingerprint.
            fingerprinter = Fingerprinter(self.config, cache=self.fingerprint_cache)
            try:
                fp = await fingerprinter.fingerprint(file)
                result.fingerprint = fp
                result.status = ProcessingStatus.FINGERPRINTED
            except FingerprintError as exc:
                result.error = str(exc)
                result.status = ProcessingStatus.ERROR
                return result

            # 2. Recognize.
            recognizer = Recognizer(self.config)
            match = await recognizer.recognize_file(str(file.path))
            # Only accept the match if it has meaningful content and meets
            # the confidence threshold; otherwise fall through to fuzzy.
            if (
                match
                and match.title
                and match.confidence >= self.config.min_confidence
            ):
                result.match = match
                result.status = ProcessingStatus.RECOGNIZED
            else:
                if match and not match.title:
                    logger.info(
                        "Shazam returned empty match for %s, falling back to fuzzy...",
                        file.path.name,
                    )
                elif match and match.confidence < self.config.min_confidence:
                    logger.info(
                        "Shazam confidence %.0f%% below threshold %.0f%% for %s, "
                        "falling back to fuzzy...",
                        match.confidence * 100,
                        self.config.min_confidence * 100,
                        file.path.name,
                    )
                # Fuzzy fallback: try alternative fingerprint strategies.
                logger.info(
                    "Primary recognition failed for %s, attempting fuzzy matching...",
                    file.path.name,
                )
                fuzzy = FuzzyMatcher(self.config)
                candidates = await fuzzy.find_candidates(str(file.path))
                if candidates:
                    result.match_alternatives = candidates
                    result.status = ProcessingStatus.AWAITING_SELECTION
                    logger.info(
                        "Fuzzy matching found %d candidate(s) for %s",
                        len(candidates),
                        file.path.name,
                    )
                    return result  # Pause — user must select before lyrics/tagging.
                else:
                    result.status = ProcessingStatus.ERROR
                    result.error = "No match found (primary and fuzzy both failed)"
                    return result

            # 3. Lyrics (always fetch unless explicitly disabled).
            if not no_lyrics and result.match and result.match.artist and result.match.title:
                fetcher = LyricsFetcher(self.config, cache=self.lyrics_cache)
                try:
                    lyrics = await fetcher.fetch(result.match)
                    if lyrics and lyrics.lines:
                        result.lyrics = lyrics
                        result.status = ProcessingStatus.LYRICS_FETCHED
                        logger.info("Lyrics found for %s - %s", result.match.artist, result.match.title)
                    else:
                        logger.info("No lyrics found for %s - %s", result.match.artist, result.match.title)
                except Exception as exc:
                    logger.debug("Lyrics fetch error: %s", exc)

        except Exception as exc:
            result.error = str(exc)
            result.status = ProcessingStatus.ERROR
            logger.exception("Unexpected error processing %s", file.path.name)

        return result

    async def resume_after_selection(
        self,
        result: TrackResult,
        selected_match: TrackMatch,
        *,
        no_lyrics: bool = False,
    ) -> TrackResult:
        """Resume pipeline for a file after the user selects a fuzzy match.

        Sets result.match, fetches lyrics (unless *no_lyrics*), and returns
        the updated result.  Tag writing is handled separately by the caller
        (GUI / CLI).
        """
        result.match = selected_match
        result.status = ProcessingStatus.RECOGNIZED

        if (
            not no_lyrics
            and result.match.artist
            and result.match.title
        ):
            fetcher = LyricsFetcher(self.config, cache=self.lyrics_cache)
            try:
                lyrics = await fetcher.fetch(result.match)
                if lyrics and lyrics.lines:
                    result.lyrics = lyrics
                    result.status = ProcessingStatus.LYRICS_FETCHED
                    logger.info(
                        "Lyrics found for %s - %s",
                        result.match.artist,
                        result.match.title,
                    )
                else:
                    logger.info(
                        "No lyrics found for %s - %s",
                        result.match.artist,
                        result.match.title,
                    )
            except Exception as exc:
                logger.debug("Lyrics fetch error: %s", exc)

        return result

    # ── File renaming ────────────────────────────────────────────────────

    def _rename_file(self, file: AudioFile, match: TrackMatch) -> Optional[Path]:
        """Rename the audio file to 'Artist - Title.ext', sanitising the name.

        Returns the new path on success, None on failure.
        """
        if not match.artist or not match.title:
            return None

        raw = f"{match.title} - {match.artist}"
        safe = _sanitise_filename(raw)
        suffix = file.path.suffix
        new_path = file.path.parent / f"{safe}{suffix}"

        # Don't rename if target already exists or is the same.
        if new_path == file.path:
            return None
        if new_path.exists():
            logger.warning("Target already exists, skipping rename: %s", new_path.name)
            return None

        try:
            file.path.rename(new_path)
            logger.info("Renamed: %s → %s", file.path.name, new_path.name)
            return new_path
        except OSError as exc:
            logger.warning("Rename failed: %s", exc)
            return None

    # ── Helpers ──────────────────────────────────────────────────────────

    def _default_state_path(self, root: Path) -> Path:
        return Path(self.config.state_dir) / f"batch_{root.name}.json"


def _sanitise_filename(name: str) -> str:
    """Replace characters unsafe for filenames."""
    # Strip path separators and other problematic chars.
    name = name.replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*]', "-", name)
    # Collapse multiple spaces/dashes.
    name = re.sub(r"[-]{2,}", "-", name)
    name = re.sub(r"[ ]{2,}", " ", name)
    return name.strip()
