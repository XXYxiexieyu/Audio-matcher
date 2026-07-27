"""Tests for configuration management."""

from __future__ import annotations

import json
from pathlib import Path

from audio_matcher.core.config import Config, create_default_config


class TestConfigDefaults:
    def test_default_values(self) -> None:
        cfg = Config()
        assert cfg.acoustid_api_key == ""
        assert cfg.max_workers == 4
        assert ".flac" in cfg.audio_extensions
        assert cfg.min_confidence == 0.3
        assert "lrclib" in cfg.lyrics_providers

    def test_derived_paths(self) -> None:
        cfg = Config()
        assert cfg.cache_dir != ""
        assert cfg.state_dir != ""


class TestConfigLoadSave:
    def test_save_and_load_roundtrip(self, temp_dir: Path) -> None:
        cfg = Config(
            acoustid_api_key="test-key",
            max_workers=8,
            overwrite_tags=True,
        )
        path = temp_dir / "config.json"
        cfg.save(path)

        loaded = Config.load(path)
        assert loaded.acoustid_api_key == "test-key"
        assert loaded.max_workers == 8
        assert loaded.overwrite_tags is True

    def test_load_nonexistent_returns_default(self, temp_dir: Path) -> None:
        path = temp_dir / "nonexistent.json"
        cfg = Config.load(path)
        assert cfg.acoustid_api_key == ""
        assert cfg.max_workers == 4

    def test_load_unknown_keys_ignored(self, temp_dir: Path) -> None:
        path = temp_dir / "extra.json"
        path.write_text(json.dumps({
            "max_workers": 16,
            "extra_field": "should be ignored",
            "another_unknown": 42,
        }))
        cfg = Config.load(path)
        assert cfg.max_workers == 16
        # Unknown fields should not appear
        assert not hasattr(cfg, "extra_field")


class TestCreateDefaultConfig:
    def test_creates_file(self, temp_dir: Path) -> None:
        path = temp_dir / "default_config.json"
        cfg = create_default_config(path)
        assert path.exists()
        assert cfg.max_workers == 4

    def test_roundtrip(self, temp_dir: Path) -> None:
        path = temp_dir / "roundtrip.json"
        create_default_config(path)
        loaded = Config.load(path)
        assert loaded.max_workers == 4
        assert ".flac" in loaded.audio_extensions
