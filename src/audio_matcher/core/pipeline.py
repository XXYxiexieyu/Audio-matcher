"""Pipeline orchestrator — ties together scanner, fingerprinter, recognizer, lyrics, tagger.

Processes audio files in parallel with progress tracking and resume support.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from audio_matcher.core.cache import FingerprintCache, LyricsCache
from audio_matcher.core.config import Config
from audio_matcher.core.fingerprinter import FingerprintError, Fingerprinter
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


class Pipeline:
    """Orchestrates the full audio matching pipeline."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.scanner = AudioScanner(self.config)
        self.state_mgr = StateManager()
        self._fp_cache: Optional[FingerprintCache] = None
        self._ly_cache: Optional[LyricsCache] = None

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
    ) -> list[TrackResult]:
        """Run the full pipeline on all audio files under *root*.

        Args:
            root: Directory to scan.
            resume_path: Path to a state file for resuming.
            interactive: If True, return results without writing tags.
            dry_run: If True, don't write tags (but still log what would happen).
            no_lyrics: Skip lyrics fetching.

        Returns:
            List of TrackResult for every file processed.
        """
        root = Path(root).resolve()

        # Resume or scan.
        if resume_path and Path(resume_path).exists():
            state = self.state_mgr.load(resume_path)
            files = self.state_mgr.pending_files(state)
            logger.info("Resuming: %d files pending out of %d", len(files), state.total_files)
        else:
            files = self.scanner.scan(root)
            if not files:
                logger.warning("No audio files found in %s", root)
                return []

        # Build or reuse state.
        if resume_path and Path(resume_path).exists():
            state = self.state_mgr.load(resume_path)
        else:
            state = self.state_mgr.create(files, root)
            state_path = self._default_state_path(root)
            self.state_mgr.save(state, state_path)

        state_path = resume_path or self._default_state_path(root)

        # Process with concurrency limit.
        semaphore = asyncio.Semaphore(self.config.max_workers)
        results: list[TrackResult] = []

        async def _process_one(file: AudioFile) -> TrackResult:
            async with semaphore:
                result = await self._process_file(file, no_lyrics=no_lyrics)
                # Write tags unless interactive or dry-run.
                if not interactive and not dry_run and result.match:
                    tagger = AudioTagger(self.config)
                    try:
                        tagger.write(file, result.match, result.lyrics, dry_run=False)
                        result.status = ProcessingStatus.TAGGED
                    except Exception as exc:
                        result.error = str(exc)
                        result.status = ProcessingStatus.ERROR
                elif dry_run and result.match:
                    logger.info("[DRY RUN] Would tag: %s", file.path.name)
                    result.status = ProcessingStatus.TAGGED

                self.state_mgr.update_result(state, result)
                self.state_mgr.save(state, state_path)
                results.append(result)
                return result

        # Use tqdm for progress.
        try:
            from tqdm.asyncio import tqdm_asyncio
            await tqdm_asyncio.gather(
                *[_process_one(f) for f in files],
                desc="Processing",
                total=len(files),
            )
        except ImportError:
            tasks = [_process_one(f) for f in files]
            await asyncio.gather(*tasks)

        # Summary.
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
            if match:
                result.match = match
                result.status = ProcessingStatus.RECOGNIZED
            else:
                result.status = ProcessingStatus.ERROR
                result.error = "No match found"
                return result

            # 3. Lyrics (optional).
            if not no_lyrics and result.match:
                fetcher = LyricsFetcher(self.config, cache=self.lyrics_cache)
                lyrics = await fetcher.fetch(result.match)
                if lyrics:
                    result.lyrics = lyrics
                    result.status = ProcessingStatus.LYRICS_FETCHED

        except Exception as exc:
            result.error = str(exc)
            result.status = ProcessingStatus.ERROR
            logger.exception("Unexpected error processing %s", file.path.name)

        return result

    # ── Helpers ──────────────────────────────────────────────────────────

    def _default_state_path(self, root: Path) -> Path:
        return Path(self.config.state_dir) / f"batch_{root.name}.json"
