"""Tests for reparatio_cli.api — HTTP layer, mocked at httpx.Client."""
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from reparatio_cli.api import (
    _filename_from_response,
    api_append,
    api_batch_convert,
    api_convert,
    api_formats,
    api_inspect,
    api_me,
    api_merge,
    api_query,
)

from .conftest import make_response


CSV_BYTES = b"id,name\n1,Alice\n2,Bob\n"
PARQUET_BYTES = b"PAR1" + b"\x00" * 20
_FAKE_KEY = "rp_test_xxxxxxxxxxxxxxxxxxxx"

_FORMATS_JSON = {"input": ["csv", "parquet"], "output": ["csv", "parquet"]}

_ME_JSON = {
    "email": "user@example.com",
    "plan": "pro",
    "active": True,
    "api_access": True,
}

_INSPECT_JSON = {
    "filename": "data.csv",
    "detected_encoding": "utf-8",
    "rows": 100,
    "columns": [{"name": "id", "dtype": "Int64", "null_count": 0, "unique_count": 100}],
    "preview": [{"id": "1"}],
}


def _patch_client_get(response):
    """Context manager that patches httpx.Client.get to return *response*."""
    return patch("reparatio_cli.api.httpx.Client.get", return_value=response)


def _patch_client_post(response):
    """Context manager that patches httpx.Client.post to return *response*."""
    return patch("reparatio_cli.api.httpx.Client.post", return_value=response)


# ---------------------------------------------------------------------------
# _filename_from_response
# ---------------------------------------------------------------------------

class TestFilenameFromResponse:
    def test_extracts_from_content_disposition(self):
        resp = make_response(200, headers={"content-disposition": 'attachment; filename="out.parquet"'})
        assert _filename_from_response(resp, "fallback.csv") == "out.parquet"

    def test_falls_back_when_header_absent(self):
        resp = make_response(200)
        assert _filename_from_response(resp, "fallback.csv") == "fallback.csv"

    def test_falls_back_when_filename_not_in_header(self):
        resp = make_response(200, headers={"content-disposition": "attachment"})
        assert _filename_from_response(resp, "fallback.csv") == "fallback.csv"


# ---------------------------------------------------------------------------
# api_formats
# ---------------------------------------------------------------------------

class TestApiFormats:
    def test_success(self):
        resp = make_response(200, json_data=_FORMATS_JSON)
        with _patch_client_get(resp):
            data = api_formats(_FAKE_KEY)
        assert data == _FORMATS_JSON

    def test_no_key_still_works(self):
        resp = make_response(200, json_data=_FORMATS_JSON)
        with _patch_client_get(resp):
            data = api_formats(None)
        assert "input" in data

    def test_error_exits(self):
        resp = make_response(500, json_data={"detail": "Server error"})
        with _patch_client_get(resp):
            with pytest.raises(SystemExit):
                api_formats(_FAKE_KEY)


# ---------------------------------------------------------------------------
# api_me
# ---------------------------------------------------------------------------

class TestApiMe:
    def test_success(self):
        resp = make_response(200, json_data=_ME_JSON)
        with _patch_client_get(resp):
            data = api_me(_FAKE_KEY)
        assert data["email"] == "user@example.com"
        assert data["plan"] == "pro"

    def test_401_exits(self):
        resp = make_response(401, json_data={"detail": "Invalid key"})
        with _patch_client_get(resp):
            with pytest.raises(SystemExit):
                api_me(_FAKE_KEY)

    def test_403_exits(self):
        resp = make_response(403, json_data={"detail": "Forbidden"})
        with _patch_client_get(resp):
            with pytest.raises(SystemExit):
                api_me(_FAKE_KEY)


# ---------------------------------------------------------------------------
# api_inspect
# ---------------------------------------------------------------------------

class TestApiInspect:
    def test_success(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        resp = make_response(200, json_data=_INSPECT_JSON)
        with _patch_client_post(resp) as mock_post:
            data = api_inspect(_FAKE_KEY, f)
        assert data["filename"] == "data.csv"
        # Verify correct endpoint
        mock_post.assert_called_once()
        assert "/api/v1/inspect" in str(mock_post.call_args)

    def test_no_header_sent_as_true(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        resp = make_response(200, json_data=_INSPECT_JSON)
        with _patch_client_post(resp) as mock_post:
            api_inspect(_FAKE_KEY, f, no_header=True)
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["no_header"] == "true"

    def test_fix_encoding_default_true(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        resp = make_response(200, json_data=_INSPECT_JSON)
        with _patch_client_post(resp) as mock_post:
            api_inspect(_FAKE_KEY, f)
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["fix_encoding"] == "true"

    def test_custom_preview_rows(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        resp = make_response(200, json_data=_INSPECT_JSON)
        with _patch_client_post(resp) as mock_post:
            api_inspect(_FAKE_KEY, f, preview_rows=20)
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["preview_rows"] == "20"

    def test_422_exits(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02")
        resp = make_response(422, json_data={"detail": "Cannot parse"})
        with _patch_client_post(resp):
            with pytest.raises(SystemExit):
                api_inspect(_FAKE_KEY, f)


# ---------------------------------------------------------------------------
# api_convert
# ---------------------------------------------------------------------------

class TestApiConvert:
    def test_success_writes_file(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "data.parquet"
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp):
            written, warning = api_convert(_FAKE_KEY, f, "parquet", out)
        assert written == out
        assert out.read_bytes() == PARQUET_BYTES
        assert warning is None

    def test_content_disposition_renames_output(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        resp = make_response(200, content=PARQUET_BYTES,
                             headers={"content-disposition": 'attachment; filename="server_name.parquet"'})
        with _patch_client_post(resp):
            written, _ = api_convert(_FAKE_KEY, f, "parquet", out_dir)
        assert written.name == "server_name.parquet"
        assert written.parent == out_dir

    def test_warning_header_returned(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "data.parquet"
        resp = make_response(200, content=PARQUET_BYTES,
                             headers={"x-reparatio-warning": "Row limit hit"})
        with _patch_client_post(resp):
            _, warning = api_convert(_FAKE_KEY, f, "parquet", out)
        assert warning == "Row limit hit"

    def test_encoding_override_sent(self, tmp_path):
        f = tmp_path / "mainframe.dat"
        f.write_bytes(b"\xc1\xc2\xc3")
        out = tmp_path / "mainframe.csv"
        resp = make_response(200, content=CSV_BYTES)
        with _patch_client_post(resp) as mock_post:
            api_convert(_FAKE_KEY, f, "csv", out, encoding_override="cp037")
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data.get("encoding_override") == "cp037"

    def test_null_values_sent(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "data.parquet"
        null_json = '["N/A","NULL"]'
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp) as mock_post:
            api_convert(_FAKE_KEY, f, "parquet", out, null_values=null_json)
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["null_values"] == null_json

    def test_select_columns_sent(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "data.parquet"
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp) as mock_post:
            api_convert(_FAKE_KEY, f, "parquet", out, select_columns='["id","name"]')
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["select_columns"] == '["id","name"]'

    def test_deduplicate_flag_sent(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "data.parquet"
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp) as mock_post:
            api_convert(_FAKE_KEY, f, "parquet", out, deduplicate=True)
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["deduplicate"] == "true"

    def test_402_exits(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "data.parquet"
        resp = make_response(402, json_data={"detail": "Requires Professional plan"})
        with _patch_client_post(resp):
            with pytest.raises(SystemExit):
                api_convert(_FAKE_KEY, f, "parquet", out)

    def test_413_exits(self, tmp_path):
        f = tmp_path / "big.csv"
        f.write_bytes(CSV_BYTES)
        out = tmp_path / "big.parquet"
        resp = make_response(413, json_data={"detail": "File too large"})
        with _patch_client_post(resp):
            with pytest.raises(SystemExit):
                api_convert(_FAKE_KEY, f, "parquet", out)


# ---------------------------------------------------------------------------
# api_batch_convert
# ---------------------------------------------------------------------------

class TestApiBatchConvert:
    def test_success_no_errors(self, tmp_path):
        z = tmp_path / "data.zip"
        z.write_bytes(b"PK\x03\x04")
        out = tmp_path / "converted.zip"
        resp = make_response(200, content=b"PK\x03\x04converted")
        with _patch_client_post(resp):
            written, errors = api_batch_convert(_FAKE_KEY, z, "parquet", out)
        assert written == out
        assert errors is None

    def test_errors_header_url_decoded(self, tmp_path):
        z = tmp_path / "data.zip"
        z.write_bytes(b"PK\x03\x04")
        out = tmp_path / "converted.zip"
        errors_json = json.dumps([{"file": "bad.bin", "error": "cannot parse"}])
        resp = make_response(200, content=b"PK\x03\x04",
                             headers={"x-reparatio-errors": urllib.parse.quote(errors_json)})
        with _patch_client_post(resp):
            _, errors = api_batch_convert(_FAKE_KEY, z, "parquet", out)
        assert errors is not None
        parsed = json.loads(errors)
        assert parsed[0]["file"] == "bad.bin"


# ---------------------------------------------------------------------------
# api_merge
# ---------------------------------------------------------------------------

class TestApiMerge:
    def test_success_left_join(self, tmp_path):
        f1 = tmp_path / "orders.csv"
        f2 = tmp_path / "customers.csv"
        f1.write_bytes(b"id,amount\n1,100\n")
        f2.write_bytes(b"id,name\n1,Alice\n")
        out = tmp_path / "merged.parquet"
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp) as mock_post:
            written, warning = api_merge(_FAKE_KEY, f1, f2, "left", "parquet", out,
                                         join_on="id")
        assert warning is None
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["operation"] == "left"
        assert sent_data["join_on"] == "id"

    def test_fallback_filename_built_from_stems(self, tmp_path):
        f1 = tmp_path / "orders.csv"
        f2 = tmp_path / "customers.csv"
        f1.write_bytes(b"id\n1\n")
        f2.write_bytes(b"id\n1\n")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp):
            written, _ = api_merge(_FAKE_KEY, f1, f2, "inner", "parquet", out_dir)
        assert written.name == "orders_inner_customers.parquet"


# ---------------------------------------------------------------------------
# api_append
# ---------------------------------------------------------------------------

class TestApiAppend:
    def test_success_two_files(self, tmp_path):
        f1 = tmp_path / "jan.csv"
        f2 = tmp_path / "feb.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        out = tmp_path / "appended.parquet"
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp) as mock_post:
            written, warning = api_append(_FAKE_KEY, [f1, f2], "parquet", out)
        assert written == out
        assert warning is None
        # Verify files sent as multipart
        sent_files = mock_post.call_args.kwargs.get("files") or mock_post.call_args[1].get("files")
        assert len(sent_files) == 2

    def test_three_files_sent(self, tmp_path):
        files = []
        for name in ("a.csv", "b.csv", "c.csv"):
            f = tmp_path / name
            f.write_bytes(CSV_BYTES)
            files.append(f)
        out = tmp_path / "appended.parquet"
        resp = make_response(200, content=PARQUET_BYTES)
        with _patch_client_post(resp) as mock_post:
            api_append(_FAKE_KEY, files, "parquet", out)
        sent_files = mock_post.call_args.kwargs.get("files") or mock_post.call_args[1].get("files")
        assert len(sent_files) == 3

    def test_warning_returned(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        out = tmp_path / "appended.parquet"
        resp = make_response(200, content=PARQUET_BYTES,
                             headers={"x-reparatio-warning": "Column mismatch in b.csv"})
        with _patch_client_post(resp):
            _, warning = api_append(_FAKE_KEY, [f1, f2], "parquet", out)
        assert warning == "Column mismatch in b.csv"


# ---------------------------------------------------------------------------
# api_query
# ---------------------------------------------------------------------------

class TestApiQuery:
    def test_success(self, tmp_path):
        f = tmp_path / "events.parquet"
        f.write_bytes(PARQUET_BYTES)
        out = tmp_path / "events_query.csv"
        resp = make_response(200, content=CSV_BYTES)
        with _patch_client_post(resp) as mock_post:
            written = api_query(_FAKE_KEY, f, "SELECT * FROM data LIMIT 5", "csv", out)
        assert written == out
        assert out.read_bytes() == CSV_BYTES
        sent_data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data")
        assert sent_data["sql"] == "SELECT * FROM data LIMIT 5"
        assert sent_data["target_format"] == "csv"

    def test_content_disposition_renames_in_directory(self, tmp_path):
        f = tmp_path / "events.parquet"
        f.write_bytes(PARQUET_BYTES)
        out_dir = tmp_path / "results"
        out_dir.mkdir()
        resp = make_response(200, content=CSV_BYTES,
                             headers={"content-disposition": 'attachment; filename="server_query.csv"'})
        with _patch_client_post(resp):
            written = api_query(_FAKE_KEY, f, "SELECT 1", "csv", out_dir)
        assert written.name == "server_query.csv"
        assert written.parent == out_dir
