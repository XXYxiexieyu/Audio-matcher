"""Tests for fingerprinter (mock external services)."""

from __future__ import annotations

import pytest

from audio_matcher.core.config import Config
from audio_matcher.core.fingerprinter import FingerprintError, Fingerprinter
from audio_matcher.core.models import (
    AudioFile,
    AudioFormat,
    Fingerprint,
    FingerprintMethod,
)


class TestFingerprinter:
    async def test_shazamio_primary(self, temp_dir, mocker) -> None:
        """fingerprint() should prefer ShazamIO."""
        f = temp_dir / "test.flac"
        f.write_bytes(b"dummy audio data")
        af = AudioFile(path=f, format=AudioFormat.FLAC, duration_s=10.0)

        expected_fp = Fingerprint(hash="fake_hash", method=FingerprintMethod.SHAZAMIO)
        mocker.patch.object(Fingerprinter, "_shazamio_fingerprint", return_value=expected_fp)

        fingerprinter = Fingerprinter()
        fp = await fingerprinter.fingerprint(af)
        assert fp.method == FingerprintMethod.SHAZAMIO
        assert fp.hash == "fake_hash"

    async def test_fallback_to_acoustid(self, temp_dir, mocker) -> None:
        """When ShazamIO fails and AcoustID key is set, fall back."""
        f = temp_dir / "test.flac"
        f.write_bytes(b"dummy audio data")
        af = AudioFile(path=f, format=AudioFormat.FLAC, duration_s=10.0)

        # ShazamIO fails.
        mocker.patch.object(
            Fingerprinter, "_shazamio_fingerprint",
            side_effect=Exception("shazam failed"),
        )
        expected_fp = Fingerprint(hash="acoustid_hash", method=FingerprintMethod.ACOUSTID)
        mocker.patch.object(
            Fingerprinter, "_acoustid_fingerprint",
            return_value=expected_fp,
        )

        config = Config(acoustid_api_key="test-key")
        fingerprinter = Fingerprinter(config=config)
        fp = await fingerprinter.fingerprint(af)
        assert fp.method == FingerprintMethod.ACOUSTID
        assert fp.hash == "acoustid_hash"

    async def test_both_fail_raises_error(self, temp_dir, mocker) -> None:
        """Both methods fail → FingerprintError."""
        f = temp_dir / "test.flac"
        f.write_bytes(b"dummy")
        af = AudioFile(path=f, format=AudioFormat.FLAC)

        mocker.patch.object(
            Fingerprinter, "_shazamio_fingerprint",
            side_effect=Exception("fail1"),
        )
        mocker.patch.object(
            Fingerprinter, "_acoustid_fingerprint",
            side_effect=Exception("fail2"),
        )

        config = Config(acoustid_api_key="test-key")
        fingerprinter = Fingerprinter(config=config)
        with pytest.raises(FingerprintError):
            await fingerprinter.fingerprint(af)

    async def test_cache_hit_skips_fingerprinting(self, temp_dir) -> None:
        """A cached fingerprint should be returned without calling backends."""
        from audio_matcher.core.cache import FingerprintCache

        f = temp_dir / "cached.flac"
        f.write_bytes(b"dummy")
        af = AudioFile(path=f, format=AudioFormat.FLAC, duration_s=5.0)

        cache = FingerprintCache(temp_dir / "fp.json")
        cached_fp = Fingerprint(hash="cached_hash", method=FingerprintMethod.SHAZAMIO, duration_s=5.0)
        cache.set(str(af.path), cached_fp)

        fingerprinter = Fingerprinter(cache=cache)
        fp = await fingerprinter.fingerprint(af)
        assert fp.hash == "cached_hash"

    async def test_no_acoustid_fallback_without_key(self, temp_dir, mocker) -> None:
        """When AcoustID key is not set, don't try AcoustID fallback."""
        f = temp_dir / "test.flac"
        f.write_bytes(b"dummy")
        af = AudioFile(path=f, format=AudioFormat.FLAC)

        mocker.patch.object(
            Fingerprinter, "_shazamio_fingerprint",
            side_effect=Exception("fail"),
        )
        # AcoustID should NOT be called because no API key.
        acoustid_spy = mocker.patch.object(Fingerprinter, "_acoustid_fingerprint")

        fingerprinter = Fingerprinter()  # no API key
        with pytest.raises(FingerprintError):
            await fingerprinter.fingerprint(af)
        acoustid_spy.assert_not_called()
