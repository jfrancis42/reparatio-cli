"""Shared fixtures and helpers for reparatio-cli tests."""
import json

import httpx
import pytest
from click.testing import CliRunner


def make_response(
    status: int = 200,
    *,
    json_data: dict | list | None = None,
    content: bytes = b"",
    headers: dict | None = None,
) -> httpx.Response:
    """Build a real httpx.Response suitable for mocking."""
    h = dict(headers or {})
    if json_data is not None:
        content = json.dumps(json_data).encode()
        h.setdefault("content-type", "application/json")
    return httpx.Response(status, content=content, headers=h)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def csv_file(tmp_path):
    """A minimal CSV file on disk."""
    f = tmp_path / "data.csv"
    f.write_bytes(b"id,name\n1,Alice\n2,Bob\n")
    return f


@pytest.fixture
def zip_file(tmp_path):
    """A stub ZIP file on disk (magic bytes only)."""
    f = tmp_path / "data.zip"
    f.write_bytes(b"PK\x03\x04")
    return f
