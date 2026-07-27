"""Tests for the audio file scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from audio_matcher.core.config import Config
from audio_matcher.core.models import AudioFormat
from audio_matcher.core.scanner import AudioScanner


class TestAudioScanner:
    def test_empty_directory(self, temp_dir: Path) -> None:
        scanner = AudioScanner()
        results = scanner.scan(temp_dir)
        assert results == []

    def test_finds_flac_files(self, temp_dir: Path) -> None:
        (temp_dir / "song.flac").touch()
        (temp_dir / "track.wav").touch()
        scanner = AudioScanner()
        results = scanner.scan(temp_dir, recursive=False)
        suffixes = {r.path.suffix for r in results}
        assert ".flac" in suffixes
        assert ".wav" in suffixes
        assert len(results) == 2

    def test_ignores_unsupported_extensions(self, temp_dir: Path) -> None:
        (temp_dir / "readme.txt").touch()
        (temp_dir / "cover.jpg").touch()
        (temp_dir / "song.mp3").touch()
        scanner = AudioScanner()
        results = scanner.scan(temp_dir, recursive=False)
        assert len(results) == 1
        assert results[0].path.suffix == ".mp3"

    def test_recursive_scan(self, temp_dir: Path) -> None:
        sub = temp_dir / "sub"
        sub.mkdir()
        (temp_dir / "a.flac").touch()
        (sub / "b.flac").touch()
        scanner = AudioScanner()
        results = scanner.scan(temp_dir, recursive=True)
        assert len(results) == 2

    def test_non_recursive_only_top_level(self, temp_dir: Path) -> None:
        sub = temp_dir / "sub"
        sub.mkdir()
        (temp_dir / "a.flac").touch()
        (sub / "b.flac").touch()
        scanner = AudioScanner()
        results = scanner.scan(temp_dir, recursive=False)
        assert len(results) == 1

    def test_format_detection(self, temp_dir: Path) -> None:
        (temp_dir / "song.flac").touch()
        (temp_dir / "song.wav").touch()
        (temp_dir / "song.dsf").touch()
        scanner = AudioScanner()
        results = {r.path.suffix: r.format for r in scanner.scan(temp_dir, recursive=False)}
        assert results[".flac"] == AudioFormat.FLAC
        assert results[".wav"] == AudioFormat.WAV
        assert results[".dsf"] == AudioFormat.DSF

    def test_not_a_directory(self, temp_dir: Path) -> None:
        f = temp_dir / "file.txt"
        f.touch()
        scanner = AudioScanner()
        with pytest.raises(NotADirectoryError):
            scanner.scan(f)

    def test_exclude_patterns(self, temp_dir: Path) -> None:
        (temp_dir / "song.flac").touch()
        (temp_dir / "ignore_this.flac").touch()
        config = Config(exclude_patterns=["ignore_*"])
        scanner = AudioScanner(config=config)
        results = scanner.scan(temp_dir, recursive=False)
        assert len(results) == 1
        assert results[0].path.name == "song.flac"
