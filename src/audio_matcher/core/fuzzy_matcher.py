"""Fuzzy recognition fallback — multi-strategy audio fingerprint matching.

When primary ShazamIO recognition returns no match, this module attempts
to identify the track via alternative strategies that can return multiple
candidates for user selection.  Strategies use audio content only (no
filename heuristics), suitable for CD rips with meaningless filenames.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from typing import Optional

from audio_matcher.core.config import Config
from audio_matcher.core.models import MatchSource, TrackMatch

logger = logging.getLogger("audio_matcher.fuzzy_matcher")


class FuzzyMatcher:
    """Attempt to identify a track when primary recognition fails.

    Strategies are tried in priority order and candidates are aggregated,
    deduplicated, filtered by confidence, and capped at a configurable
    maximum.  All strategies are *soft* — a failing strategy is logged and
    skipped rather than aborting the whole search.
    """

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()

    # ── Public API ─────────────────────────────────────────────────────────

    async def find_candidates(self, file_path: str) -> list[TrackMatch]:
        """Run all fuzzy strategies and return deduplicated candidates.

        Returns a (possibly empty) list of candidate TrackMatch objects
        sorted by confidence descending.
        """
        all_candidates: list[TrackMatch] = []

        # Strategy 1: AcoustID fingerprint → MusicBrainz / AcoustID lookup.
        try:
            acoustid_candidates = await self._acoustid_lookup(file_path)
            if acoustid_candidates:
                logger.info(
                    "AcoustID strategy found %d candidates for %s",
                    len(acoustid_candidates),
                    file_path,
                )
            all_candidates.extend(acoustid_candidates)
        except Exception as exc:
            logger.debug("AcoustID fuzzy strategy failed: %s", exc)

        # Strategy 2: Multi-segment ShazamIO attempts.
        try:
            shazam_candidates = await self._multi_segment_shazam(file_path)
            if shazam_candidates:
                logger.info(
                    "Multi-segment Shazam found %d candidates for %s",
                    len(shazam_candidates),
                    file_path,
                )
            all_candidates.extend(shazam_candidates)
        except Exception as exc:
            logger.debug("Multi-segment Shazam strategy failed: %s", exc)

        if not all_candidates:
            return []

        # Post-process: deduplicate → filter → sort → limit.
        deduped = self._deduplicate(all_candidates)
        filtered = self._filter_and_limit(deduped)
        return filtered

    # ── Strategy 1: AcoustID ───────────────────────────────────────────────

    async def _acoustid_lookup(self, file_path: str) -> list[TrackMatch]:
        """Generate AcoustID fingerprint and look up all matching recordings.

        Uses pyacoustid to fingerprint the file, then queries the AcoustID
        web service and returns *all* results (not just the best match).
        """
        if not self.config.acoustid_api_key:
            logger.debug("Skipping AcoustID: no API key configured")
            return []

        try:
            import pyacoustid
        except ImportError:
            logger.debug("Skipping AcoustID: pyacoustid not installed")
            return []

        # 1. Generate Chromaprint fingerprint (runs native fpcalc, therefore sync).
        try:
            loop = asyncio.get_running_loop()
            duration, fingerprint_str = await loop.run_in_executor(
                None,
                lambda: pyacoustid.fingerprint_file(file_path),
            )
        except Exception as exc:
            logger.debug("AcoustID fingerprint generation failed: %s", exc)
            return []

        if not fingerprint_str:
            return []

        # 2. Look up the fingerprint against AcoustID.
        try:
            results = await loop.run_in_executor(
                None,
                lambda: pyacoustid.lookup(
                    self.config.acoustid_api_key,
                    fingerprint_str,
                ),
            )
        except Exception as exc:
            logger.debug("AcoustID lookup failed: %s", exc)
            return []

        if not results:
            return []

        # 3. Convert to TrackMatch (all results, not just the first).
        candidates: list[TrackMatch] = []
        for entry in results:
            match = self._parse_acoustid_entry(entry)
            if match and match.title:
                candidates.append(match)

        return candidates

    def _parse_acoustid_entry(self, entry: dict) -> Optional[TrackMatch]:
        """Convert a single AcoustID result dict to a TrackMatch.

        The AcoustID response includes a 'score' (0.0-1.0) that maps
        directly to our confidence field.
        """
        score = entry.get("score", 0.0)
        title = entry.get("title", "")
        artists = entry.get("artists", [])
        artist = artists[0].get("name", "") if artists else ""

        # Extract album / year from recordings if present.
        album = ""
        year: Optional[int] = None
        recordings = entry.get("recordings", [])
        if recordings:
            rec = recordings[0]
            album = rec.get("title", "") or ""
            # Some AcoustID responses nest album info under a sub-dict.
            if not album and "album" in rec:
                album = rec["album"].get("name", "")
            year_str = rec.get("year")
            if year_str:
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    pass

        source_id = entry.get("id", "")
        # Also capture the first MusicBrainz recording ID if available.
        if recordings and recordings[0].get("id"):
            source_id = recordings[0]["id"]

        return TrackMatch(
            title=title,
            artist=artist,
            album=album,
            year=year,
            confidence=score,
            source=MatchSource.ACOUSTID,
            source_id=source_id,
        )

    # ── Strategy 2: Multi-segment Shazam ───────────────────────────────────

    async def _multi_segment_shazam(self, file_path: str) -> list[TrackMatch]:
        """Try ShazamIO on different time segments of the audio file.

        Different segments may match different recordings, which is useful
        when the file preamble (silence / intro) prevented a match.
        """
        try:
            from pydub import AudioSegment
            from shazamio import Shazam
        except ImportError:
            logger.debug("Skipping multi-segment Shazam: missing dependency")
            return []

        # Load audio.
        try:
            audio = AudioSegment.from_file(file_path)
        except Exception as exc:
            logger.debug("Cannot load audio for segmenting: %s", exc)
            return []

        duration_ms = len(audio)
        results: list[TrackMatch] = []
        shazam = Shazam()

        # Import Recognizer for response parsing (shared logic).
        from audio_matcher.core.recognizer import Recognizer

        recognizer = Recognizer(self.config)

        for offset_s in self.config.fuzzy_segment_offsets:
            offset_ms = int(offset_s * 1000)
            if offset_ms >= duration_ms:
                break

            # Extract a 10-second window.
            end_ms = min(offset_ms + 10_000, duration_ms)
            if end_ms - offset_ms < 5_000:  # skip fragments shorter than 5 s
                break

            segment = audio[offset_ms:end_ms]

            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=True
                ) as tmp:
                    segment.export(tmp.name, format="wav")
                    shazam_result = await shazam.recognize(tmp.name)
                    match = recognizer._parse_shazam_response(shazam_result)
                    if match and match.title:
                        # Tag this as a Shazam match but note it came from
                        # the fuzzy segment strategy via the source_id.
                        match.source = MatchSource.SHAZAM
                        if match.source_id:
                            match.source_id = f"segment:{offset_s}s/{match.source_id}"
                        results.append(match)
            except Exception as exc:
                logger.debug(
                    "Segment Shazam at %.0fs failed: %s", offset_s, exc
                )
                continue

        return results

    # ── Post-processing ────────────────────────────────────────────────────

    def _deduplicate(self, candidates: list[TrackMatch]) -> list[TrackMatch]:
        """Remove duplicates, keeping the highest-confidence entry per
        (artist, title) pair (case-insensitive)."""
        seen: dict[tuple[str, str], TrackMatch] = {}
        for c in candidates:
            key = (c.artist.lower().strip(), c.title.lower().strip())
            if not key[0] and not key[1]:
                continue  # skip empty entries
            if key not in seen or c.confidence > seen[key].confidence:
                seen[key] = c
        return sorted(
            seen.values(), key=lambda m: m.confidence, reverse=True
        )

    def _filter_and_limit(
        self, candidates: list[TrackMatch]
    ) -> list[TrackMatch]:
        """Filter by fuzzy_min_confidence and cap to fuzzy_max_candidates."""
        threshold = self.config.fuzzy_min_confidence
        candidates = [c for c in candidates if c.confidence >= threshold]
        return candidates[: self.config.fuzzy_max_candidates]
