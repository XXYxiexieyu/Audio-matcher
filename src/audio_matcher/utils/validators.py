"""Validation helpers for audio files and user inputs."""

from __future__ import annotations

from pathlib import Path


def is_audio_file(path: str | Path, extensions: set[str] | None = None) -> bool:
    """Check if *path* has a recognised audio extension."""
    if extensions is None:
        extensions = {
            ".flac", ".wav", ".dsf", ".dff",
            ".mp3", ".m4a", ".aac", ".ogg", ".wma", ".aiff",
        }
    return Path(path).suffix.lower() in extensions


def validate_directory(path: str | Path) -> Path:
    """Ensure *path* is a readable directory.

    Raises:
        NotADirectoryError, FileNotFoundError
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"Not a directory: {p}")
    return p
