"""Core data models for Audio Matcher.

All dataclasses and enumerations used across the application live here
so every other module can import from a single stable source.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Optional


# ── Enums ────────────────────────────────────────────────────────────────


class AudioFormat(StrEnum):
    """Supported audio file formats."""
    FLAC = "flac"
    WAV = "wav"
    DSF = "dsf"
    DFF = "dff"
    MP3 = "mp3"
    M4A = "m4a"
    AAC = "aac"
    OGG = "ogg"
    WMA = "wma"
    AIFF = "aiff"
    UNKNOWN = "unknown"


class FingerprintMethod(StrEnum):
    """Method used to generate an audio fingerprint."""
    SHAZAMIO = "shazamio"
    ACOUSTID = "acoustid"


class MatchSource(StrEnum):
    """Source database that provided the track match."""
    SHAZAM = "shazam"
    ACOUSTID = "acoustid"
    MUSICBRAINZ = "musicbrainz"


class LyricsSource(StrEnum):
    """Source service that provided the lyrics."""
    LRCLIB = "lrclib"
    NETEASE = "netease"
    QQMUSIC = "qqmusic"


class ProcessingStatus(StrEnum):
    """Processing status for a single audio file in the pipeline."""
    PENDING = "pending"
    SCANNED = "scanned"
    FINGERPRINTED = "fingerprinted"
    RECOGNIZED = "recognized"
    LYRICS_FETCHED = "lyrics_fetched"
    TAGGED = "tagged"
    ERROR = "error"
    SKIPPED = "skipped"


class LyricsLanguage(StrEnum):
    """Controls which lyrics variants to embed in the output file."""
    ORIGINAL_ONLY = "original_only"          # 仅外语
    BILINGUAL = "bilingual"                  # 双语（原文+翻译）
    JAPANESE_ROMAJI = "japanese_romaji"      # 日语+罗马音
    BILINGUAL_ROMAJI = "bilingual_romaji"    # 双语+罗马音


# ── Data Models ──────────────────────────────────────────────────────────


@dataclass
class AudioFile:
    """Metadata about a scanned audio file."""
    path: Path
    format: AudioFormat = AudioFormat.UNKNOWN
    duration_s: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    file_size_bytes: int = 0

    @property
    def id(self) -> str:
        """Stable identifier derived from the absolute path."""
        return str(self.path.resolve())


@dataclass
class Fingerprint:
    """Result of fingerprinting an audio file."""
    hash: str
    duration_s: float = 0.0
    method: FingerprintMethod = FingerprintMethod.SHAZAMIO
    raw_data: Optional[bytes] = None


@dataclass
class LyricLine:
    """A single line of synced lyrics."""
    timestamp_ms: int
    text: str


@dataclass
class SyncedLyrics:
    """Synced LRC lyrics from an online source.

    Carries original, translated, and romanised variants so the
    language-mode decision can be deferred to the pipeline / tagger.
    """
    lines: list[LyricLine] = field(default_factory=list)
    source: LyricsSource = LyricsSource.LRCLIB
    raw_lrc: str = ""
    # v0.0.5: multi-language support.
    translated_lrc: str = ""
    translated_lines: list[LyricLine] = field(default_factory=list)
    romanized_lrc: str = ""
    romanized_lines: list[LyricLine] = field(default_factory=list)

    @property
    def has_translation(self) -> bool:
        return bool(self.translated_lrc)

    @property
    def has_romanized(self) -> bool:
        return bool(self.romanized_lrc)


@dataclass
class TrackMatch:
    """A matched track from a recognition service."""
    title: str = ""
    artist: str = ""
    album: str = ""
    year: Optional[int] = None
    track_number: Optional[int] = None
    confidence: float = 0.0
    source: MatchSource = MatchSource.SHAZAM
    source_id: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass
class TrackResult:
    """Combined result for a single audio file through the full pipeline."""
    audio_file: AudioFile
    fingerprint: Optional[Fingerprint] = None
    match: Optional[TrackMatch] = None
    lyrics: Optional[SyncedLyrics] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error: Optional[str] = None
    edited: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def is_successful(self) -> bool:
        """True if a match was found (regardless of lyrics/tagging)."""
        return self.match is not None


@dataclass
class BatchState:
    """Serialisable state for resume support."""
    total_files: int = 0
    completed: int = 0
    results: dict[str, TrackResult] = field(default_factory=dict)
    started_at: str = ""
    updated_at: str = ""
    root_directory: str = ""
    version: str = "0.0.1"
