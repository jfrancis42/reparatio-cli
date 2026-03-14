"""Tests for reparatio_cli.cli — CLI commands via CliRunner, api_* functions mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from reparatio_cli.cli import main


CSV_BYTES = b"id,name\n1,Alice\n2,Bob\n"
PARQUET_BYTES = b"PAR1" + b"\x00" * 20
_FAKE_KEY = "rp_test_xxxxxxxxxxxxxxxxxxxx"

_FORMATS_RESP = {"input": ["csv", "parquet", "xlsx"], "output": ["csv", "parquet"]}

_INSPECT_RESP = {
    "filename": "data.csv",
    "detected_encoding": "utf-8",
    "rows": 500,
    "columns": [
        {"name": "id", "dtype": "Int64", "null_count": 0, "unique_count": 500},
        {"name": "name", "dtype": "Utf8", "null_count": 1, "unique_count": 499},
    ],
    "preview": [{"id": "1", "name": "Alice"}],
}

_ME_RESP = {
    "email": "user@example.com",
    "plan": "pro",
    "active": True,
    "api_access": True,
    "expires_at": "2026-12-31T00:00:00Z",
}


# ---------------------------------------------------------------------------
# key sub-commands
# ---------------------------------------------------------------------------

class TestKeyCommands:
    def test_key_set_saves_and_confirms(self, runner, tmp_path, monkeypatch):
        config_dir = tmp_path / "reparatio"
        config_file = config_dir / "config.json"
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            result = runner.invoke(main, ["key", "set", "rp_testkey"])
        assert result.exit_code == 0
        assert "saved" in result.output.lower()

    def test_key_set_warns_on_wrong_prefix(self, runner, tmp_path):
        config_dir = tmp_path / "reparatio"
        config_file = config_dir / "config.json"
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            result = runner.invoke(main, ["key", "set", "wrongprefix"])
        assert "warning" in result.output.lower() or result.exit_code == 0

    def test_key_show_displays_key(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        result = runner.invoke(main, ["key", "show"])
        assert result.exit_code == 0
        assert _FAKE_KEY in result.output

    def test_key_show_exits_when_no_key(self, runner, tmp_path, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = tmp_path / "config.json"
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            result = runner.invoke(main, ["key", "show"])
        assert result.exit_code != 0

    def test_key_clear_confirms(self, runner, tmp_path, monkeypatch):
        config_dir = tmp_path / "reparatio"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"api_key": _FAKE_KEY}))
        with (
            patch("reparatio_cli.config._CONFIG_DIR", config_dir),
            patch("reparatio_cli.config._CONFIG_FILE", config_file),
        ):
            result = runner.invoke(main, ["key", "clear"])
        assert result.exit_code == 0
        assert "cleared" in result.output.lower()


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------

class TestMeCommand:
    def test_displays_subscription_info(self, runner, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        with patch("reparatio_cli.cli.api_me", return_value=_ME_RESP):
            result = runner.invoke(main, ["me"])
        assert result.exit_code == 0
        assert "user@example.com" in result.output
        assert "pro" in result.output

    def test_exits_when_no_key(self, runner, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = Path("/tmp/nonexistent_config_xyz.json")
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            result = runner.invoke(main, ["me"])
        assert result.exit_code != 0

    def test_expires_at_shown_when_present(self, runner, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        with patch("reparatio_cli.cli.api_me", return_value=_ME_RESP):
            result = runner.invoke(main, ["me"])
        assert "2026-12-31" in result.output

    def test_expires_at_omitted_when_absent(self, runner, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        resp = {**_ME_RESP, "expires_at": None}
        with patch("reparatio_cli.cli.api_me", return_value=resp):
            result = runner.invoke(main, ["me"])
        assert result.exit_code == 0
        assert "Expires" not in result.output


# ---------------------------------------------------------------------------
# formats
# ---------------------------------------------------------------------------

class TestFormatsCommand:
    def test_shows_table(self, runner):
        with patch("reparatio_cli.cli.api_formats", return_value=_FORMATS_RESP):
            result = runner.invoke(main, ["formats"])
        assert result.exit_code == 0
        assert "csv" in result.output

    def test_json_flag_outputs_valid_json(self, runner):
        with patch("reparatio_cli.cli.api_formats", return_value=_FORMATS_RESP):
            result = runner.invoke(main, ["formats", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "input" in parsed
        assert "output" in parsed

    def test_works_without_api_key(self, runner, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        with patch("reparatio_cli.cli.api_formats", return_value=_FORMATS_RESP):
            result = runner.invoke(main, ["formats"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

class TestInspectCommand:
    def test_basic_output(self, runner, csv_file):
        with patch("reparatio_cli.cli.api_inspect", return_value=_INSPECT_RESP):
            result = runner.invoke(main, ["inspect", str(csv_file)])
        assert result.exit_code == 0
        assert "data.csv" in result.output
        assert "500" in result.output  # rows

    def test_json_flag(self, runner, csv_file):
        with patch("reparatio_cli.cli.api_inspect", return_value=_INSPECT_RESP):
            result = runner.invoke(main, ["inspect", str(csv_file), "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["rows"] == 500

    def test_no_header_flag_passed(self, runner, csv_file):
        with patch("reparatio_cli.cli.api_inspect", return_value=_INSPECT_RESP) as mock_inspect:
            result = runner.invoke(main, ["inspect", str(csv_file), "--no-header"])
        assert result.exit_code == 0
        call_kwargs = mock_inspect.call_args.kwargs
        assert call_kwargs.get("no_header") is True

    def test_fix_encoding_disabled(self, runner, csv_file):
        with patch("reparatio_cli.cli.api_inspect", return_value=_INSPECT_RESP) as mock_inspect:
            result = runner.invoke(main, ["inspect", str(csv_file), "--no-fix-encoding"])
        assert result.exit_code == 0
        call_kwargs = mock_inspect.call_args.kwargs
        assert call_kwargs.get("fix_encoding") is False

    def test_missing_file_fails(self, runner, tmp_path):
        ghost = tmp_path / "nonexistent.csv"
        result = runner.invoke(main, ["inspect", str(ghost)])
        assert result.exit_code != 0

    def test_custom_preview_rows(self, runner, csv_file):
        with patch("reparatio_cli.cli.api_inspect", return_value=_INSPECT_RESP) as mock_inspect:
            result = runner.invoke(main, ["inspect", str(csv_file), "-n", "20"])
        call_kwargs = mock_inspect.call_args.kwargs
        assert call_kwargs.get("preview_rows") == 20

    def test_sheets_displayed_when_present(self, runner, csv_file):
        resp = {**_INSPECT_RESP, "sheets": ["Sheet1", "Data"]}
        with patch("reparatio_cli.cli.api_inspect", return_value=resp):
            result = runner.invoke(main, ["inspect", str(csv_file)])
        assert "Sheet1" in result.output


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------

class TestConvertCommand:
    def test_basic_convert(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            result = runner.invoke(main, ["convert", str(csv_file), str(out)])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_format_inferred_from_output_extension(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), str(out)])
        call_args = mock_convert.call_args
        assert call_args.args[2] == "parquet"  # target_format positional arg

    def test_compound_extension_csv_gz_inferred(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.csv.gz"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), str(out)])
        assert mock_convert.call_args.args[2] == "csv.gz"

    def test_explicit_format_flag(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), "--format", "parquet"])
        assert mock_convert.call_args.args[2] == "parquet"

    def test_no_format_and_no_output_exits(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        result = runner.invoke(main, ["convert", str(csv_file)])
        assert result.exit_code != 0

    def test_warning_printed_to_output(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, "Row limit applied")):
            result = runner.invoke(main, ["convert", str(csv_file), str(out)])
        assert "Row limit applied" in result.output

    def test_no_key_exits(self, runner, csv_file, monkeypatch):
        monkeypatch.delenv("REPARATIO_API_KEY", raising=False)
        config_file = Path("/tmp/nonexistent_config_xyz.json")
        with patch("reparatio_cli.config._CONFIG_FILE", config_file):
            result = runner.invoke(main, ["convert", str(csv_file), "--format", "parquet"])
        assert result.exit_code != 0

    def test_cast_spec_parsed(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), str(out),
                                  "--cast", "price=Float64",
                                  "--cast", 'date=Date:%d/%m/%Y'])
        call_kwargs = mock_convert.call_args.kwargs
        cast = json.loads(call_kwargs["cast_columns"])
        assert cast["price"] == {"type": "Float64"}
        assert cast["date"] == {"type": "Date", "format": "%d/%m/%Y"}

    def test_invalid_cast_spec_exits(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        result = runner.invoke(main, ["convert", str(csv_file), "--format", "parquet",
                                      "--cast", "NOEQUALS"])
        assert result.exit_code != 0

    def test_select_columns_sent(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), str(out),
                                  "--select", "id,name"])
        call_kwargs = mock_convert.call_args.kwargs
        assert json.loads(call_kwargs["select_columns"]) == ["id", "name"]

    def test_encoding_override_sent(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "out.csv"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), str(out),
                                  "--encoding", "cp037"])
        call_kwargs = mock_convert.call_args.kwargs
        assert call_kwargs["encoding_override"] == "cp037"

    def test_null_values_sent(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "out.parquet"
        with patch("reparatio_cli.cli.api_convert", return_value=(out, None)) as mock_convert:
            runner.invoke(main, ["convert", str(csv_file), str(out),
                                  "--null-values", "N/A,NULL,-"])
        call_kwargs = mock_convert.call_args.kwargs
        null_vals = json.loads(call_kwargs["null_values"])
        assert null_vals == ["N/A", "NULL", "-"]


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

class TestMergeCommand:
    def test_left_join(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        f1 = tmp_path / "orders.csv"
        f2 = tmp_path / "customers.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        out = tmp_path / "merged.parquet"
        with patch("reparatio_cli.cli.api_merge", return_value=(out, None)):
            result = runner.invoke(main, ["merge", str(f1), str(f2),
                                          "--op", "left", "--format", "parquet",
                                          "--on", "id"])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_warning_printed(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        out = tmp_path / "merged.parquet"
        with patch("reparatio_cli.cli.api_merge", return_value=(out, "Column mismatch")):
            result = runner.invoke(main, ["merge", str(f1), str(f2),
                                          "--op", "append", "--format", "parquet"])
        assert "Column mismatch" in result.output

    def test_invalid_op_rejected(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        result = runner.invoke(main, ["merge", str(f1), str(f2),
                                      "--op", "badop", "--format", "parquet"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------

class TestAppendCommand:
    def test_two_files(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        f1 = tmp_path / "jan.csv"
        f2 = tmp_path / "feb.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        out = tmp_path / "appended.parquet"
        with patch("reparatio_cli.cli.api_append", return_value=(out, None)):
            result = runner.invoke(main, ["append", str(f1), str(f2), "--format", "parquet"])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_single_file_exits(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        f = tmp_path / "only.csv"
        f.write_bytes(CSV_BYTES)
        result = runner.invoke(main, ["append", str(f), "--format", "parquet"])
        assert result.exit_code != 0

    def test_warning_printed(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_bytes(CSV_BYTES)
        f2.write_bytes(CSV_BYTES)
        out = tmp_path / "appended.parquet"
        with patch("reparatio_cli.cli.api_append", return_value=(out, "3 columns filled with null")):
            result = runner.invoke(main, ["append", str(f1), str(f2), "--format", "parquet"])
        assert "3 columns filled with null" in result.output


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

class TestQueryCommand:
    def test_basic_query(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data_query.csv"
        with patch("reparatio_cli.cli.api_query", return_value=out):
            result = runner.invoke(main, ["query", str(csv_file),
                                          "SELECT * FROM data LIMIT 10"])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_custom_format(self, runner, csv_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = csv_file.parent / "data_query.parquet"
        with patch("reparatio_cli.cli.api_query", return_value=out) as mock_query:
            runner.invoke(main, ["query", str(csv_file), "SELECT 1", "--format", "parquet"])
        assert mock_query.call_args.args[3] == "parquet"

    def test_custom_output_path(self, runner, csv_file, tmp_path, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = tmp_path / "custom_out.csv"
        with patch("reparatio_cli.cli.api_query", return_value=out) as mock_query:
            runner.invoke(main, ["query", str(csv_file), "SELECT 1", "-o", str(out)])
        assert mock_query.call_args.args[4] == out


# ---------------------------------------------------------------------------
# batch-convert
# ---------------------------------------------------------------------------

class TestBatchConvertCommand:
    def test_basic(self, runner, zip_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = zip_file.parent / "converted.zip"
        with patch("reparatio_cli.cli.api_batch_convert", return_value=(out, None)):
            result = runner.invoke(main, ["batch-convert", str(zip_file), "--format", "parquet"])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_skip_errors_printed(self, runner, zip_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = zip_file.parent / "converted.zip"
        errors = json.dumps([{"file": "bad.bin", "error": "Cannot parse"}])
        with patch("reparatio_cli.cli.api_batch_convert", return_value=(out, errors)):
            result = runner.invoke(main, ["batch-convert", str(zip_file), "--format", "parquet"])
        assert "bad.bin" in result.output

    def test_cast_spec_parsed(self, runner, zip_file, monkeypatch):
        monkeypatch.setenv("REPARATIO_API_KEY", _FAKE_KEY)
        out = zip_file.parent / "converted.zip"
        with patch("reparatio_cli.cli.api_batch_convert", return_value=(out, None)) as mock_bc:
            runner.invoke(main, ["batch-convert", str(zip_file), "--format", "parquet",
                                  "--cast", "price=Float64"])
        call_kwargs = mock_bc.call_args.kwargs
        cast = json.loads(call_kwargs["cast_columns"])
        assert cast["price"] == {"type": "Float64"}
