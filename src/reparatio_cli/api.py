"""Thin HTTP layer for the Reparatio CLI.

Keeps the CLI code free of raw httpx calls and provides consistent error
messages for every failure mode.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import httpx
from rich.console import Console

_BASE_URL = "https://reparatio.app"

_err = Console(stderr=True, highlight=False)


def _raise(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text

    if response.status_code in (401, 403):
        _err.print(f"[red]Authentication error:[/] {detail}")
        _err.print("Run [bold]reparatio key set <YOUR_KEY>[/] to configure your API key.")
    elif response.status_code == 402:
        _err.print(f"[red]Insufficient plan:[/] {detail}")
        _err.print("A Monthly plan is required. Visit [link=https://reparatio.app]reparatio.app[/link].")
    elif response.status_code == 413:
        _err.print(f"[red]File too large:[/] {detail}")
    elif response.status_code == 422:
        _err.print(f"[red]Parse error:[/] {detail}")
    else:
        _err.print(f"[red]API error {response.status_code}:[/] {detail}")
    sys.exit(1)


def _client(api_key: Optional[str]) -> httpx.Client:
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return httpx.Client(base_url=_BASE_URL, headers=headers, timeout=180.0)


def _filename_from_response(response: httpx.Response, fallback: str) -> str:
    cd = response.headers.get("content-disposition", "")
    if 'filename="' in cd:
        return cd.split('filename="', 1)[1].rstrip('"')
    return fallback


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------


def api_formats(api_key: Optional[str]) -> dict:
    with _client(api_key) as c:
        r = c.get("/api/v1/formats")
    _raise(r)
    return r.json()


def api_me(api_key: str) -> dict:
    with _client(api_key) as c:
        r = c.get("/api/v1/me")
    _raise(r)
    return r.json()


def api_inspect(
    api_key: Optional[str],
    path: Path,
    *,
    no_header: bool = False,
    fix_encoding: bool = True,
    preview_rows: int = 8,
    delimiter: str = "",
    sheet: str = "",
) -> dict:
    with _client(api_key) as c:
        r = c.post(
            "/api/v1/inspect",
            files={"file": (path.name, path.read_bytes())},
            data={
                "no_header": str(no_header).lower(),
                "fix_encoding": str(fix_encoding).lower(),
                "preview_rows": str(preview_rows),
                "delimiter": delimiter,
                "sheet": sheet,
            },
        )
    _raise(r)
    return r.json()


def api_convert(
    api_key: str,
    input_path: Path,
    target_format: str,
    output_path: Path,
    *,
    no_header: bool = False,
    fix_encoding: bool = True,
    delimiter: str = "",
    sheet: str = "",
    columns: str = "[]",
    select_columns: str = "[]",
    deduplicate: bool = False,
    sample_n: int = 0,
    sample_frac: float = 0.0,
    geometry_column: str = "geometry",
    cast_columns: str = "{}",
    encoding_override: str = "",
) -> Tuple[Path, Optional[str]]:
    with _client(api_key) as c:
        data: dict = {
            "target_format": target_format,
            "no_header": str(no_header).lower(),
            "fix_encoding": str(fix_encoding).lower(),
            "delimiter": delimiter,
            "sheet": sheet,
            "columns": columns,
            "select_columns": select_columns,
            "deduplicate": str(deduplicate).lower(),
            "sample_n": str(sample_n),
            "sample_frac": str(sample_frac),
            "geometry_column": geometry_column,
            "cast_columns": cast_columns,
        }
        if encoding_override:
            data["encoding_override"] = encoding_override
        r = c.post(
            "/api/v1/convert",
            files={"file": (input_path.name, input_path.read_bytes())},
            data=data,
        )
    _raise(r)
    suggested = _filename_from_response(r, output_path.name)
    if output_path.is_dir():
        output_path = output_path / suggested
    output_path.write_bytes(r.content)
    warning = r.headers.get("x-reparatio-warning")
    return output_path, warning


def api_batch_convert(
    api_key: str,
    zip_path: Path,
    target_format: str,
    output_path: Path,
    *,
    no_header: bool = False,
    fix_encoding: bool = True,
    delimiter: str = "",
    select_columns: str = "[]",
    deduplicate: bool = False,
    sample_n: int = 0,
    sample_frac: float = 0.0,
    cast_columns: str = "{}",
) -> Tuple[Path, Optional[str]]:
    with _client(api_key) as c:
        r = c.post(
            "/api/v1/batch-convert",
            files={"zip_file": (zip_path.name, zip_path.read_bytes())},
            data={
                "target_format": target_format,
                "no_header": str(no_header).lower(),
                "fix_encoding": str(fix_encoding).lower(),
                "delimiter": delimiter,
                "select_columns": select_columns,
                "deduplicate": str(deduplicate).lower(),
                "sample_n": str(sample_n),
                "sample_frac": str(sample_frac),
                "cast_columns": cast_columns,
            },
        )
    _raise(r)
    suggested = _filename_from_response(r, "converted.zip")
    if output_path.is_dir():
        output_path = output_path / suggested
    output_path.write_bytes(r.content)
    import urllib.parse as _up
    raw_errors = r.headers.get("x-reparatio-errors")
    errors = _up.unquote(raw_errors) if raw_errors else None
    return output_path, errors


def api_merge(
    api_key: str,
    file1: Path,
    file2: Path,
    operation: str,
    target_format: str,
    output_path: Path,
    *,
    join_on: str = "",
    no_header: bool = False,
    fix_encoding: bool = True,
    geometry_column: str = "geometry",
) -> Tuple[Path, Optional[str]]:
    with _client(api_key) as c:
        r = c.post(
            "/api/v1/merge",
            files={
                "file1": (file1.name, file1.read_bytes()),
                "file2": (file2.name, file2.read_bytes()),
            },
            data={
                "operation": operation,
                "target_format": target_format,
                "join_on": join_on,
                "no_header": str(no_header).lower(),
                "fix_encoding": str(fix_encoding).lower(),
                "geometry_column": geometry_column,
            },
        )
    _raise(r)
    base1 = file1.stem
    base2 = file2.stem
    suggested = _filename_from_response(r, f"{base1}_{operation}_{base2}.{target_format}")
    if output_path.is_dir():
        output_path = output_path / suggested
    output_path.write_bytes(r.content)
    warning = r.headers.get("x-reparatio-warning")
    return output_path, warning


def api_append(
    api_key: str,
    paths: List[Path],
    target_format: str,
    output_path: Path,
    *,
    no_header: bool = False,
    fix_encoding: bool = True,
) -> Tuple[Path, Optional[str]]:
    multipart = [("files", (p.name, p.read_bytes())) for p in paths]
    with _client(api_key) as c:
        r = c.post(
            "/api/v1/append",
            files=multipart,
            data={
                "target_format": target_format,
                "no_header": str(no_header).lower(),
                "fix_encoding": str(fix_encoding).lower(),
            },
        )
    _raise(r)
    suggested = _filename_from_response(r, f"appended.{target_format}")
    if output_path.is_dir():
        output_path = output_path / suggested
    output_path.write_bytes(r.content)
    warning = r.headers.get("x-reparatio-warning")
    return output_path, warning


def api_query(
    api_key: str,
    path: Path,
    sql: str,
    target_format: str,
    output_path: Path,
    *,
    no_header: bool = False,
    fix_encoding: bool = True,
    delimiter: str = "",
    sheet: str = "",
) -> Path:
    with _client(api_key) as c:
        r = c.post(
            "/api/v1/query",
            files={"file": (path.name, path.read_bytes())},
            data={
                "sql": sql,
                "target_format": target_format,
                "no_header": str(no_header).lower(),
                "fix_encoding": str(fix_encoding).lower(),
                "delimiter": delimiter,
                "sheet": sheet,
            },
        )
    _raise(r)
    suggested = _filename_from_response(r, f"{path.stem}_query.{target_format}")
    if output_path.is_dir():
        output_path = output_path / suggested
    output_path.write_bytes(r.content)
    return output_path
