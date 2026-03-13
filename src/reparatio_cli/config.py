"""Configuration management for the Reparatio CLI.

The API key is stored in ~/.config/reparatio/config.json.
The REPARATIO_API_KEY environment variable overrides the stored key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_CONFIG_DIR = Path.home() / ".config" / "reparatio"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_config(data: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_api_key() -> Optional[str]:
    """Return the API key, preferring the environment variable."""
    return os.environ.get("REPARATIO_API_KEY") or _load_config().get("api_key")


def set_api_key(key: str) -> None:
    """Persist the API key to disk."""
    data = _load_config()
    data["api_key"] = key
    _save_config(data)


def clear_api_key() -> None:
    """Remove the stored API key."""
    data = _load_config()
    data.pop("api_key", None)
    _save_config(data)
