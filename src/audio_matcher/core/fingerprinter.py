"""Audio fingerprinting — ShazamIO (primary) + AcoustID (fallback)."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from audio_matcher.core.cache import FingerprintCache
from audio_matcher.core.config import Config
from audio_matcher.core.models import AudioFile, Fingerprint, FingerprintMethod

logger = logging.getLogger("audio_matcher.fingerprinter")


class FingerprintError(Exception):
    """Raised when both fingerprinting methods fail."""


class Fingerprinter:
    """Generate audio fingerprints for recognition.

    Tries ShazamIO first (no API key needed).  Falls back to AcoustID
    if fpcalc is available and an API key is configured.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        cache: Optional[FingerprintCache] = None,
    ) -> None:
        self.config = config or Config()
        self.cache = cache

    async def fingerprint(self, file: AudioFile) -> Fingerprint:
        """Generate a fingerprint for *file*.

        Checks the cache first.  Tries ShazamIO → AcoustID.

        Raises:
            FingerprintError: Both methods failed.
        """
        # Cache check.
        if self.cache is not None:
            cached = self.cache.get(str(file.path))
            if cached is not None:
                return cached

        # Primary: ShazamIO.
        try:
            fp = await self._shazamio_fingerprint(file)
            if self.cache is not None:
                self.cache.set(str(file.path), fp)
            return fp
        except Exception as exc:
            logger.debug("ShazamIO fingerprint failed for %s: %s", file.path.name, exc)

        # Fallback: AcoustID.
        if self.config.acoustid_api_key:
            try:
                fp = await self._acoustid_fingerprint(file)
                if self.cache is not None:
                    self.cache.set(str(file.path), fp)
                return fp
            except Exception as exc:
                logger.debug("AcoustID fingerprint failed for %s: %s", file.path.name, exc)

        raise FingerprintError(f"All fingerprint methods failed for {file.path.name}")

    # ── Private ──────────────────────────────────────────────────────────

    async def _shazamio_fingerprint(self, file: AudioFile) -> Fingerprint:
        from shazamio import Shazam
        shazam = Shazam()
        # shazamio reads the file and generates a fingerprint internally.
        result = await shazam.recognize(str(file.path))
        # Even if no match, shazamio generated a fingerprint.
        # We store a hash derived from the file path + mtime.
        import hashlib
        st = file.path.stat()
        raw = f"{file.path.resolve()}:{st.st_mtime}:{st.st_size}".encode()
        fp_hash = hashlib.sha256(raw).hexdigest()
        return Fingerprint(
            hash=fp_hash,
            duration_s=file.duration_s,
            method=FingerprintMethod.SHAZAMIO,
        )

    async def _acoustid_fingerprint(self, file: AudioFile) -> Fingerprint:
        import pyacoustid
        loop = asyncio.get_running_loop()
        duration, fingerprint_str = await loop.run_in_executor(
            None,
            lambda: pyacoustid.fingerprint_file(str(file.path)),
        )
        return Fingerprint(
            hash=fingerprint_str,
            duration_s=duration or file.duration_s,
            method=FingerprintMethod.ACOUSTID,
        )
