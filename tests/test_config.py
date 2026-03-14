"""Tests for reparatio_cli.config — key storage and retrieval."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from reparatio_cli.config import clear_api_key, get_api_key, set_api_key


class TestGetApiKey:
    def test_returns_none_when_no_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = tmp_path / "config.json"
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            assert get_api_key() is None

    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", "rp_from_env")
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"api_key": "rp_from_file"}))
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            assert get_api_key() == "rp_from_env"

    def test_falls_back_to_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"api_key": "rp_from_file"}))
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            assert get_api_key() == "rp_from_file"

    def test_corrupt_config_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{{")
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            assert get_api_key() is None

    def test_missing_config_dir_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = tmp_path / "nonexistent" / "config.json"
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            assert get_api_key() is None


class TestSetApiKey:
    def test_writes_key_to_file(self, tmp_path):
        config_dir = tmp_path / "reparatio"
        config_file = config_dir / "config.json"
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            set_api_key("rp_newkey")
            saved = json.loads(config_file.read_text())
        assert saved["api_key"] == "rp_newkey"

    def test_creates_directory_if_missing(self, tmp_path):
        config_dir = tmp_path / "deep" / "nested" / "dir"
        config_file = config_dir / "config.json"
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            set_api_key("rp_test")
            assert config_file.exists()

    def test_overwrites_existing_key(self, tmp_path):
        config_dir = tmp_path / "reparatio"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"api_key": "rp_old", "other": "value"}))
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            set_api_key("rp_new")
            saved = json.loads(config_file.read_text())
        assert saved["api_key"] == "rp_new"
        assert saved["other"] == "value"  # other keys preserved


class TestClearApiKey:
    def test_removes_key_from_file(self, tmp_path):
        config_dir = tmp_path / "reparatio"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"api_key": "rp_test"}))
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            clear_api_key()
            saved = json.loads(config_file.read_text())
        assert "api_key" not in saved

    def test_clear_on_missing_file_does_not_raise(self, tmp_path):
        config_dir = tmp_path / "reparatio"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            clear_api_key()  # should not raise

    def test_preserves_other_config_keys(self, tmp_path):
        config_dir = tmp_path / "reparatio"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"api_key": "rp_test", "theme": "dark"}))
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            clear_api_key()
            saved = json.loads(config_file.read_text())
        assert saved.get("theme") == "dark"
