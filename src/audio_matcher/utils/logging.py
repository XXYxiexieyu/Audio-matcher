"""Structured logging setup."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str | Path] = None,
    verbose: bool = False,
) -> None:
    """Configure logging for the application.

    Args:
        level: Base logging level (default INFO).
        log_file: Optional path for file output.
        verbose: If True, set console to DEBUG as well.
    """
    console_level = logging.DEBUG if verbose else level

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    # Root logger.
    root = logging.getLogger("audio_matcher")
    root.setLevel(logging.DEBUG)  # Let handlers filter.

    # Console.
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(console_level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File (optional).
    if log_file:
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)
