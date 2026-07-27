"""Audio file scanner — recursive directory walk with format probing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from audio_matcher.core.config import Config
from audio_matcher.core.models import AudioFile, AudioFormat

logger = logging.getLogger("audio_matcher.scanner")

# Map lowercase extensions to AudioFormat enum members.
_EXTENSION_MAP: dict[str, AudioFormat] = {
    ".flac": AudioFormat.FLAC,
    ".wav": AudioFormat.WAV,
    ".dsf": AudioFormat.DSF,
    ".dff": AudioFormat.DFF,
    ".mp3": AudioFormat.MP3,
    ".m4a": AudioFormat.M4A,
    ".aac": AudioFormat.AAC,
    ".ogg": AudioFormat.OGG,
    ".wma": AudioFormat.WMA,
    ".aiff": AudioFormat.AIFF,
    ".aif": AudioFormat.AIFF,
}


class AudioScanner:
    """Discovers and probes audio files in a directory tree."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self._extensions = self.config.audio_extensions

    # ── Public API ───────────────────────────────────────────────────────

    def scan(self, root: str | Path, recursive: bool = True) -> list[AudioFile]:
        """Scan a directory for supported audio files.

        Args:
            root: Root directory to scan.
            recursive: If True (default), walk sub-directories.

        Returns:
            A list of AudioFile objects (unsorted, in filesystem order).
        """
        root = Path(root).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        results: list[AudioFile] = []
        for entry in self._walk(root, recursive):
            af = self._probe(entry)
            if af is not None:
                results.append(af)
                logger.debug("Found: %s [%s, %.1fs]", entry.name, af.format.value, af.duration_s)

        logger.info("Scan complete: %d audio files found in %s", len(results), root)
        return results

    # ── Internals ────────────────────────────────────────────────────────

    def _walk(self, root: Path, recursive: bool) -> list[Path]:
        """Collect candidate file paths."""
        if recursive:
            entries: list[Path] = []
            for p in root.rglob("*"):
                if p.is_file() and not self._should_exclude(p):
                    entries.append(p)
            return entries
        else:
            return [
                p for p in root.iterdir()
                if p.is_file() and not self._should_exclude(p)
            ]

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded based on patterns."""
        import fnmatch
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True
        return False

    def _is_audio_file(self, path: Path) -> bool:
        """Check extension against the configured set."""
        return path.suffix.lower() in self._extensions

    def _probe(self, path: Path) -> Optional[AudioFile]:
        """Probe a file: check extension, then extract metadata.

        Returns None if the file is not a supported audio file or cannot be read.
        """
        suffix = path.suffix.lower()
        if suffix not in self._extensions:
            return None

        fmt = _EXTENSION_MAP.get(suffix, AudioFormat.UNKNOWN)
        duration_s, sample_rate, channels = self._read_metadata(path)

        # Apply duration filters.
        if duration_s > 0:
            if duration_s < self.config.min_duration_sec:
                logger.debug("Skipping (too short): %s (%.1fs)", path.name, duration_s)
                return None
            if duration_s > self.config.max_duration_sec:
                logger.debug("Skipping (too long): %s (%.1fs)", path.name, duration_s)
                return None

        return AudioFile(
            path=path,
            format=fmt,
            duration_s=duration_s,
            sample_rate=sample_rate,
            channels=channels,
            file_size_bytes=path.stat().st_size if path.exists() else 0,
        )

    @staticmethod
    def _read_metadata(path: Path) -> tuple[float, int, int]:
        """Read duration, sample rate, and channels from an audio file.

        Uses pydub (via ffmpeg/avlib) for best accuracy, falling back
        to mutagen for tag-only metadata.

        Returns:
            (duration_s, sample_rate, channels).  All zero on failure.
        """
        try:
            from pydub.utils import mediainfo
            info = mediainfo(str(path))
            duration_s = float(info.get("duration", 0))
            sample_rate = int(info.get("sample_rate", 0))
            channels = int(info.get("channels", 0))
            return duration_s, sample_rate, channels
        except Exception:
            pass

        # Fallback: try mutagen (can't always get duration for raw formats).
        try:
            import mutagen
            mf = mutagen.File(str(path))
            if mf is not None and hasattr(mf, "info"):
                info = mf.info
                duration_s = getattr(info, "length", 0.0)
                sample_rate = getattr(info, "sample_rate", 0)
                channels = getattr(info, "channels", 0)
                return duration_s, sample_rate, channels
        except Exception:
            pass

        logger.warning("Could not read audio metadata for %s", path.name)
        return 0.0, 0, 0
