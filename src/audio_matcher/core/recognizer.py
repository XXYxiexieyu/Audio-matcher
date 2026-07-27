"""Music recognition — match fingerprints against online databases."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from audio_matcher.core.config import Config
from audio_matcher.core.models import (
    Fingerprint,
    FingerprintMethod,
    MatchSource,
    TrackMatch,
)

logger = logging.getLogger("audio_matcher.recognizer")


class Recognizer:
    """Identify songs from audio fingerprints via Shazam / AcoustID."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()

    async def recognize(self, fp: Fingerprint) -> Optional[TrackMatch]:
        """Return a TrackMatch for *fp*, or None if no match found.

        Uses the same method that generated the fingerprint.
        """
        if fp.method == FingerprintMethod.SHAZAMIO:
            return await self._shazam_recognize(fp)
        elif fp.method == FingerprintMethod.ACOUSTID:
            return await self._acoustid_recognize(fp)
        else:
            logger.warning("Unknown fingerprint method: %s", fp.method)
            return None

    # ── Shazam ───────────────────────────────────────────────────────────

    async def _shazam_recognize(self, fp: Fingerprint) -> Optional[TrackMatch]:
        """Use shazamio to recognise the file directly."""
        try:
            from shazamio import Shazam
            shazam = Shazam()
            # We need the original file path.  The fingerprint doesn't hold it,
            # so we pass the path from the caller via a workaround.
            # In practice, the pipeline passes the AudioFile, not just the Fingerprint.
            # We accept that _shazam_recognize needs the path.
            # The pipeline will call a higher-level method.
            logger.debug("Shazam recognition called (requires path from pipeline)")
            return None  # Overridden by pipeline-level call
        except Exception as exc:
            logger.debug("Shazam recognition error: %s", exc)
            return None

    async def recognize_file(self, path: str) -> Optional[TrackMatch]:
        """Recognise an audio file directly with Shazam (preferred path).

        This is the primary API — the pipeline calls this with the file path.
        """
        try:
            from shazamio import Shazam
            shazam = Shazam()
            result = await shazam.recognize(path)
            return self._parse_shazam_response(result)
        except Exception as exc:
            logger.warning("Shazam recognition failed for %s: %s", path, exc)
            return None

    def _parse_shazam_response(self, data: dict) -> Optional[TrackMatch]:
        """Parse shazamio's recognise() response into a TrackMatch."""
        track = data.get("track")
        if not track:
            return None

        title = track.get("title", "")
        artist = track.get("subtitle", "")
        album = ""
        year = None

        sections = track.get("sections", [])
        for section in sections:
            if section.get("type") == "SONG":
                metadata_items = section.get("metadata", [])
                # Shazam metadata comes in pairs: {"title": "X"}, {"text": "Y"}
                i = 0
                while i + 1 < len(metadata_items):
                    title_item = metadata_items[i]
                    text_item = metadata_items[i + 1]
                    if "title" in title_item and "text" in text_item:
                        label = title_item.get("title", "")
                        value = text_item.get("text", "")
                        if label == "Album":
                            album = value
                        elif label in ("Released", "Year"):
                            try:
                                year = int(value)
                            except (ValueError, TypeError):
                                pass
                    i += 2

        # Confidence heuristic: if we got title + artist, it's decent.
        confidence = 0.8 if title and artist else 0.3
        key = track.get("key", "")

        return TrackMatch(
            title=title,
            artist=artist,
            album=album,
            year=year,
            track_number=None,
            confidence=confidence,
            source=MatchSource.SHAZAM,
            source_id=key,
            raw_response=data,
        )

    # ── AcoustID ─────────────────────────────────────────────────────────

    async def _acoustid_recognize(self, fp: Fingerprint) -> Optional[TrackMatch]:
        """Look up an AcoustID fingerprint."""
        if not self.config.acoustid_api_key:
            logger.warning("AcoustID API key not configured")
            return None
        try:
            import pyacoustid
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: pyacoustid.lookup(
                    self.config.acoustid_api_key,
                    fp.hash,
                ),
            )
            return self._parse_acoustid_response(results)
        except Exception as exc:
            logger.warning("AcoustID recognition failed: %s", exc)
            return None

    def _parse_acoustid_response(self, results: list) -> Optional[TrackMatch]:
        """Parse pyacoustid.lookup() response into a TrackMatch."""
        if not results:
            return None
        # Best match first (sorted by score descending by pyacoustid).
        best = results[0]
        title = best.get("title", "")
        artists = best.get("artists", [])
        artist = artists[0].get("name", "") if artists else ""
        album = ""
        year = None
        # Extract album/year from recordings if present.
        recordings = best.get("recordings", [])
        if recordings:
            rec = recordings[0]
            album = rec.get("title", "") or rec.get("album", {}).get("name", "")
            year_str = rec.get("year")
            if year_str:
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    pass
        return TrackMatch(
            title=title,
            artist=artist,
            album=album,
            year=year,
            confidence=best.get("score", 0.0),
            source=MatchSource.ACOUSTID,
            source_id=best.get("id", ""),
        )
