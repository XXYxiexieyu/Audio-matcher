"""Configuration management — defaults, file loading, env vars."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Default config location
DEFAULT_CONFIG_DIR = Path.home() / ".audio_matcher"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_CACHE_DIR = DEFAULT_CONFIG_DIR / "cache"


@dataclass
class Config:
    """Application configuration.

    Loaded from ~/.audio_matcher/config.json (JSON).  All fields are
    optional and fall back to the defaults declared below.
    """

    # ── API keys ─────────────────────────────────────────────────────────

    acoustid_api_key: str = ""

    # ── MusicBrainz client identity ──────────────────────────────────────

    musicbrainz_app_name: str = "audio_matcher"
    musicbrainz_app_version: str = "0.0.5"

    # ── Recognition ──────────────────────────────────────────────────────

    shazamio_timeout: int = 30
    min_confidence: float = 0.3

    # ── Scanning ─────────────────────────────────────────────────────────

    audio_extensions: set[str] = field(default_factory=lambda: {
        ".flac", ".wav", ".dsf", ".dff",
        ".mp3", ".m4a", ".aac", ".ogg", ".wma", ".aiff",
    })
    exclude_patterns: list[str] = field(default_factory=list)
    min_duration_sec: float = 10.0
    max_duration_sec: float = 3600.0

    # ── Lyrics ───────────────────────────────────────────────────────────

    lyrics_providers: list[str] = field(default_factory=lambda: [
        "lrclib", "netease", "qqmusic",
    ])
    lyrics_language: str = "original_only"
    write_lrc_sidecar: bool = True

    # ── Tagging ──────────────────────────────────────────────────────────

    overwrite_tags: bool = False
    backup_original: bool = False

    # ── Performance ──────────────────────────────────────────────────────

    max_workers: int = 4
    rate_limit_rps: float = 2.0

    # ── Paths ────────────────────────────────────────────────────────────

    cache_dir: str = ""
    state_dir: str = ""

    def __post_init__(self) -> None:
        """Set derived paths after field initialisation."""
        if not self.cache_dir:
            self.cache_dir = str(DEFAULT_CACHE_DIR)
        if not self.state_dir:
            self.state_dir = str(DEFAULT_CONFIG_DIR / "state")

    # ── I/O ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> Config:
        """Load configuration from a JSON file.

        Args:
            path: Path to config JSON.  Defaults to ~/.audio_matcher/config.json.

        Returns:
            A Config instance.  Missing keys fall back to defaults.
        """
        if path is None:
            path = DEFAULT_CONFIG_PATH
        else:
            path = Path(path)

        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Only pass keys that match fields on this dataclass.
            field_names = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in field_names}
            # Convert audio_extensions list back to set.
            if "audio_extensions" in filtered and isinstance(filtered["audio_extensions"], list):
                filtered["audio_extensions"] = set(filtered["audio_extensions"])
            return cls(**filtered)

        return cls()

    def save(self, path: Optional[str | Path] = None) -> None:
        """Persist configuration as JSON.

        Args:
            path: Destination path.  Defaults to ~/.audio_matcher/config.json.
        """
        if path is None:
            path = DEFAULT_CONFIG_PATH
        else:
            path = Path(path)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "acoustid_api_key": self.acoustid_api_key,
            "musicbrainz_app_name": self.musicbrainz_app_name,
            "musicbrainz_app_version": self.musicbrainz_app_version,
            "shazamio_timeout": self.shazamio_timeout,
            "min_confidence": self.min_confidence,
            "audio_extensions": sorted(self.audio_extensions),
            "exclude_patterns": self.exclude_patterns,
            "min_duration_sec": self.min_duration_sec,
            "max_duration_sec": self.max_duration_sec,
            "lyrics_providers": self.lyrics_providers,
            "lyrics_language": self.lyrics_language,
            "write_lrc_sidecar": self.write_lrc_sidecar,
            "overwrite_tags": self.overwrite_tags,
            "backup_original": self.backup_original,
            "max_workers": self.max_workers,
            "rate_limit_rps": self.rate_limit_rps,
            "cache_dir": self.cache_dir,
            "state_dir": self.state_dir,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)


def create_default_config(path: Optional[str | Path] = None) -> Config:
    """Create and persist a default configuration file.

    Args:
        path: Where to write the file.  Defaults to ~/.audio_matcher/config.json.

    Returns:
        The default Config instance.
    """
    config = Config()
    config.save(path)
    return config
