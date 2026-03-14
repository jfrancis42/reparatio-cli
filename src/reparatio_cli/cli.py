"""Reparatio CLI — command definitions."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .api import (
    api_append,
    api_batch_convert,
    api_convert,
    api_formats,
    api_inspect,
    api_me,
    api_merge,
    api_query,
)
from .config import clear_api_key, get_api_key, set_api_key

out = Console()
err = Console(stderr=True, highlight=False)


def _require_key() -> str:
    key = get_api_key()
    if not key:
        err.print("[red]No API key configured.[/]")
        err.print("Run [bold]reparatio key set <YOUR_KEY>[/] or set the REPARATIO_API_KEY environment variable.")
        sys.exit(1)
    return key


def _resolve_output(input_path: Path, target_format: str, output_arg: Optional[str]) -> Path:
    """Return an output Path, defaulting to the input directory."""
    if output_arg:
        p = Path(output_arg)
        if p.is_dir():
            return p / (input_path.stem + "." + target_format)
        return p
    return input_path.parent / (input_path.stem + "." + target_format)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="reparatio-cli")
def main() -> None:
    """Reparatio — data conversion on the command line.

    Convert, inspect, merge, append, and query CSV, Parquet, Excel, JSON,
    and 30+ other formats via the Reparatio API.

    \b
    Quick start:
        reparatio key set rp_YOUR_KEY
        reparatio inspect sales.csv
        reparatio convert sales.csv sales.parquet
    """


# ---------------------------------------------------------------------------
# key sub-group
# ---------------------------------------------------------------------------


@main.group()
def key() -> None:
    """Manage your Reparatio API key."""


@key.command("set")
@click.argument("api_key")
def key_set(api_key: str) -> None:
    """Store API_KEY in ~/.config/reparatio/config.json."""
    if not api_key.startswith("rp_"):
        err.print("[yellow]Warning:[/] keys are typically prefixed with 'rp_'.")
    set_api_key(api_key)
    out.print(f"[green]API key saved.[/]")


@key.command("show")
def key_show() -> None:
    """Print the currently configured API key."""
    k = get_api_key()
    if k:
        out.print(k)
    else:
        err.print("[yellow]No API key configured.[/]")
        sys.exit(1)


@key.command("clear")
def key_clear() -> None:
    """Remove the stored API key."""
    clear_api_key()
    out.print("[green]API key cleared.[/]")


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------


@main.command()
def me() -> None:
    """Show subscription details for the current API key.

    Plans: standard ($29/mo), pro ($79/mo), credits_25 (pay-as-you-go).
    API, CLI, MCP, Fixed-Width, and EBCDIC features require the Professional plan.
    """
    k = _require_key()
    data = api_me(k)
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Email", data["email"])
    t.add_row("Plan", data["plan"])
    t.add_row("Active", "[green]yes[/]" if data["active"] else "[red]no[/]")
    t.add_row("API access", "[green]yes[/]" if data["api_access"] else "[red]no[/]")
    if data.get("expires_at"):
        t.add_row("Expires", data["expires_at"])
    out.print(t)


# ---------------------------------------------------------------------------
# formats
# ---------------------------------------------------------------------------


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def formats(as_json: bool) -> None:
    """List supported input and output formats."""
    k = get_api_key()
    data = api_formats(k)
    if as_json:
        out.print_json(json.dumps(data))
        return

    t = Table(title="Supported formats", show_lines=False)
    t.add_column("Input formats", style="cyan")
    t.add_column("Output formats", style="green")
    max_rows = max(len(data["input"]), len(data["output"]))
    for i in range(max_rows):
        inp = data["input"][i] if i < len(data["input"]) else ""
        outp = data["output"][i] if i < len(data["output"]) else ""
        t.add_row(inp, outp)
    out.print(t)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--preview-rows", "-n", default=8, show_default=True, help="Number of preview rows (1–100).")
@click.option("--no-header", is_flag=True, help="Treat first row as data.")
@click.option("--no-fix-encoding", is_flag=True, help="Disable encoding repair.")
@click.option("--delimiter", "-d", default="", help="Custom delimiter (auto-detected if omitted).")
@click.option("--sheet", "-s", default="", help="Sheet or table name (Excel, ODS, SQLite).")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def inspect(
    file: Path,
    preview_rows: int,
    no_header: bool,
    no_fix_encoding: bool,
    delimiter: str,
    sheet: str,
    as_json: bool,
) -> None:
    """Inspect FILE: schema, encoding, statistics, and a data preview.

    No API key required.
    """
    k = get_api_key()
    data = api_inspect(
        k, file,
        no_header=no_header,
        fix_encoding=not no_fix_encoding,
        preview_rows=preview_rows,
        delimiter=delimiter,
        sheet=sheet,
    )
    if as_json:
        out.print_json(json.dumps(data))
        return

    out.print(f"[bold]{data['filename']}[/]  [dim]{data['rows']:,} rows[/]  [dim]encoding: {data['detected_encoding']}[/]")
    if data.get("sheets"):
        out.print(f"[dim]Sheets: {', '.join(data['sheets'])}[/]")

    t = Table(show_header=True, header_style="bold")
    t.add_column("Column")
    t.add_column("Type", style="cyan")
    t.add_column("Nulls", justify="right")
    t.add_column("Unique", justify="right")
    for col in data.get("columns", []):
        t.add_row(
            col["name"],
            col["dtype"],
            str(col["null_count"]),
            str(col["unique_count"]),
        )
    out.print(t)

    if data.get("preview"):
        out.print(f"\n[dim]Preview ({min(preview_rows, len(data['preview']))} rows):[/]")
        headers = list(data["preview"][0].keys()) if data["preview"] else []
        p = Table(show_header=True, header_style="bold dim", box=None)
        for h in headers:
            p.add_column(h, no_wrap=False)
        for row in data["preview"]:
            p.add_row(*[str(v) if v is not None else "[dim]null[/]" for v in row.values()])
        out.print(p)


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


@main.command()
@click.argument("input", "input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", "output_arg", required=False)
@click.option("--format", "-f", "target_format", default="", help="Output format (inferred from OUTPUT extension if omitted).")
@click.option("--no-header", is_flag=True)
@click.option("--no-fix-encoding", is_flag=True)
@click.option("--delimiter", "-d", default="")
@click.option("--sheet", "-s", default="")
@click.option("--select", "select_columns", default="", help="Comma-separated columns to include.")
@click.option("--rename", "columns", default="", help="Comma-separated new column names (in order).")
@click.option("--deduplicate", is_flag=True)
@click.option("--sample-n", default=0, help="Random sample of N rows.")
@click.option("--sample-frac", default=0.0, help="Random sample fraction (e.g. 0.1).")
@click.option("--geometry-column", default="geometry")
@click.option("--null-values", "null_values", default="",
              help='Comma-separated strings to treat as null, e.g. "N/A,NULL,-".')
@click.option("--cast", "cast_specs", multiple=True,
              metavar="COL=TYPE[:FORMAT]",
              help='Override a column type. Repeatable. E.g. --cast price=Float64 --cast date=Date:"%d/%m/%%Y"')
@click.option("--encoding", "encoding_override", default="",
              help="Encoding override, e.g. cp037 for EBCDIC US, cp500 for EBCDIC International.")
def convert(
    input_path: Path,
    output_arg: Optional[str],
    target_format: str,
    no_header: bool,
    no_fix_encoding: bool,
    delimiter: str,
    sheet: str,
    select_columns: str,
    columns: str,
    deduplicate: bool,
    sample_n: int,
    sample_frac: float,
    geometry_column: str,
    null_values: str,
    cast_specs: tuple,
    encoding_override: str,
) -> None:
    """Convert INPUT to a different format.

    The output format is inferred from the OUTPUT filename extension.
    If OUTPUT is omitted, the result is written to the same directory
    as INPUT with the appropriate extension.

    \b
    Examples:
        reparatio convert sales.csv sales.parquet
        reparatio convert report.xlsx --format csv.gz
        reparatio convert data.csv out.csv --select date,region,revenue
        reparatio convert legacy.csv fixed.csv --no-fix-encoding
        reparatio convert data.csv out.parquet --cast price=Float64 --cast date=Date:"%d/%m/%Y"
    """
    k = _require_key()

    # Resolve target format
    if not target_format:
        if output_arg:
            # Try to infer compound extensions like csv.gz
            p = Path(output_arg)
            name = p.name
            for ext in [".csv.gz", ".csv.bz2", ".csv.zst", ".csv.zip",
                        ".tsv.gz", ".tsv.bz2", ".tsv.zst", ".tsv.zip",
                        ".json.gz", ".json.bz2", ".json.zst", ".json.zip",
                        ".jsonl.gz", ".jsonl.bz2", ".jsonl.zst", ".jsonl.zip",
                        ".geojson.gz", ".geojson.bz2", ".geojson.zst", ".geojson.zip"]:
                if name.endswith(ext):
                    target_format = ext.lstrip(".")
                    break
            if not target_format:
                suffix = p.suffix.lstrip(".")
                if suffix:
                    target_format = suffix
        if not target_format:
            err.print("[red]Cannot infer output format.[/] Pass --format or provide an OUTPUT filename.")
            sys.exit(1)

    output_path = _resolve_output(input_path, target_format, output_arg)

    sel = json.dumps([c.strip() for c in select_columns.split(",") if c.strip()]) if select_columns else "[]"
    cols = json.dumps([c.strip() for c in columns.split(",") if c.strip()]) if columns else "[]"

    cast_dict: dict = {}
    for spec in cast_specs:
        if "=" not in spec:
            err.print(f"[red]Invalid --cast value:[/] {spec!r}  (expected COL=TYPE or COL=TYPE:FORMAT)")
            sys.exit(1)
        col_name, rest = spec.split("=", 1)
        if ":" in rest:
            typ, fmt = rest.split(":", 1)
            cast_dict[col_name] = {"type": typ, "format": fmt}
        else:
            cast_dict[col_name] = {"type": rest}

    null_vals = json.dumps([v.strip() for v in null_values.split(",") if v.strip()]) if null_values else "[]"

    written, warning = api_convert(
        k, input_path, target_format, output_path,
        no_header=no_header,
        fix_encoding=not no_fix_encoding,
        delimiter=delimiter,
        sheet=sheet,
        select_columns=sel,
        columns=cols,
        deduplicate=deduplicate,
        sample_n=sample_n,
        sample_frac=sample_frac,
        geometry_column=geometry_column,
        null_values=null_vals,
        cast_columns=json.dumps(cast_dict),
        encoding_override=encoding_override,
    )
    out.print(f"[green]Saved:[/] {written}")
    if warning:
        err.print(f"[yellow]Warning:[/] {warning}")


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


@main.command()
@click.argument("file1", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("file2", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--op", "operation", required=True,
              type=click.Choice(["append", "left", "right", "outer", "inner"]),
              help="Join operation.")
@click.option("--format", "-f", "target_format", required=True, help="Output format.")
@click.option("--on", "join_on", default="", help="Comma-separated join column(s).")
@click.option("--output", "-o", "output_arg", default=None)
@click.option("--no-header", is_flag=True)
@click.option("--no-fix-encoding", is_flag=True)
@click.option("--geometry-column", default="geometry")
def merge(
    file1: Path,
    file2: Path,
    operation: str,
    target_format: str,
    join_on: str,
    output_arg: Optional[str],
    no_header: bool,
    no_fix_encoding: bool,
    geometry_column: str,
) -> None:
    """Merge or join FILE1 and FILE2.

    \b
    Operations:
        append  Stack all rows from both files
        left    All rows from FILE1, matched columns from FILE2
        right   All rows from FILE2, matched columns from FILE1
        outer   All rows from both files; nulls where no match
        inner   Only rows present in both files

    \b
    Examples:
        reparatio merge orders.csv customers.xlsx --op left --on customer_id --format parquet
        reparatio merge jan.csv feb.csv --op append --format csv
    """
    k = _require_key()
    default_name = f"{file1.stem}_{operation}_{file2.stem}.{target_format}"
    output_path = Path(output_arg) if output_arg else file1.parent / default_name

    written, warning = api_merge(
        k, file1, file2, operation, target_format, output_path,
        join_on=join_on,
        no_header=no_header,
        fix_encoding=not no_fix_encoding,
        geometry_column=geometry_column,
    )
    out.print(f"[green]Saved:[/] {written}")
    if warning:
        err.print(f"[yellow]Warning:[/] {warning}")


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------


@main.command()
@click.argument("files", nargs=-1, required=True,
                type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--format", "-f", "target_format", required=True, help="Output format.")
@click.option("--output", "-o", "output_arg", default=None)
@click.option("--no-header", is_flag=True)
@click.option("--no-fix-encoding", is_flag=True)
def append(
    files: tuple,
    target_format: str,
    output_arg: Optional[str],
    no_header: bool,
    no_fix_encoding: bool,
) -> None:
    """Stack rows from FILES vertically.

    Column mismatches are handled gracefully — missing values are filled
    with null.  At least 2 files are required.

    \b
    Examples:
        reparatio append jan.csv feb.csv mar.csv --format parquet
        reparatio append *.csv --format csv -o combined.csv
    """
    if len(files) < 2:
        err.print("[red]At least 2 files are required.[/]")
        sys.exit(1)

    k = _require_key()
    paths = list(files)
    output_path = Path(output_arg) if output_arg else paths[0].parent / f"appended.{target_format}"

    written, warning = api_append(
        k, paths, target_format, output_path,
        no_header=no_header,
        fix_encoding=not no_fix_encoding,
    )
    out.print(f"[green]Saved:[/] {written}")
    if warning:
        err.print(f"[yellow]Warning:[/] {warning}")


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("sql")
@click.option("--format", "-f", "target_format", default="csv", show_default=True)
@click.option("--output", "-o", "output_arg", default=None)
@click.option("--no-header", is_flag=True)
@click.option("--no-fix-encoding", is_flag=True)
@click.option("--delimiter", "-d", default="")
@click.option("--sheet", "-s", default="")
def query(
    file: Path,
    sql: str,
    target_format: str,
    output_arg: Optional[str],
    no_header: bool,
    no_fix_encoding: bool,
    delimiter: str,
    sheet: str,
) -> None:
    """Run a SQL query against FILE.

    The file is loaded as a table named 'data'.

    \b
    Examples:
        reparatio query events.parquet "SELECT region, SUM(revenue) FROM data GROUP BY region"
        reparatio query sales.csv "SELECT * FROM data WHERE amount > 1000 LIMIT 100" --format xlsx
    """
    k = _require_key()
    output_path = (
        Path(output_arg)
        if output_arg
        else file.parent / f"{file.stem}_query.{target_format}"
    )

    written = api_query(
        k, file, sql, target_format, output_path,
        no_header=no_header,
        fix_encoding=not no_fix_encoding,
        delimiter=delimiter,
        sheet=sheet,
    )
    out.print(f"[green]Saved:[/] {written}")


# ---------------------------------------------------------------------------
# batch-convert
# ---------------------------------------------------------------------------


@main.command("batch-convert")
@click.argument("zip_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--format", "-f", "target_format", required=True, help="Output format for all files (e.g. parquet, csv.gz).")
@click.option("--output", "-o", "output_arg", default=None, help="Output ZIP path (default: converted.zip in same directory).")
@click.option("--no-header", is_flag=True)
@click.option("--no-fix-encoding", is_flag=True)
@click.option("--delimiter", "-d", default="")
@click.option("--select", "select_columns", default="", help="Comma-separated columns to include.")
@click.option("--deduplicate", is_flag=True)
@click.option("--sample-n", default=0, help="Random sample of N rows per file.")
@click.option("--sample-frac", default=0.0, help="Random sample fraction per file (e.g. 0.1).")
@click.option("--cast", "cast_specs", multiple=True,
              metavar="COL=TYPE[:FORMAT]",
              help="Override a column type. Repeatable.")
def batch_convert(
    zip_file: Path,
    target_format: str,
    output_arg: Optional[str],
    no_header: bool,
    no_fix_encoding: bool,
    delimiter: str,
    select_columns: str,
    deduplicate: bool,
    sample_n: int,
    sample_frac: float,
    cast_specs: tuple,
) -> None:
    """Convert every file inside ZIP_FILE to a common format.

    Returns a ZIP archive containing all converted files.  Files that
    cannot be parsed are skipped; any errors are printed as warnings.

    \b
    Examples:
        reparatio batch-convert monthly_reports.zip --format parquet
        reparatio batch-convert raw_data.zip --format csv.gz -o processed.zip
        reparatio batch-convert data.zip --format parquet --cast price=Float64
    """
    k = _require_key()
    output_path = (
        Path(output_arg) if output_arg else zip_file.parent / "converted.zip"
    )

    sel = json.dumps([c.strip() for c in select_columns.split(",") if c.strip()]) if select_columns else "[]"

    cast_dict: dict = {}
    for spec in cast_specs:
        if "=" not in spec:
            err.print(f"[red]Invalid --cast value:[/] {spec!r}  (expected COL=TYPE or COL=TYPE:FORMAT)")
            sys.exit(1)
        col_name, rest = spec.split("=", 1)
        if ":" in rest:
            typ, fmt = rest.split(":", 1)
            cast_dict[col_name] = {"type": typ, "format": fmt}
        else:
            cast_dict[col_name] = {"type": rest}

    written, errors_json = api_batch_convert(
        k, zip_file, target_format, output_path,
        no_header=no_header,
        fix_encoding=not no_fix_encoding,
        delimiter=delimiter,
        select_columns=sel,
        deduplicate=deduplicate,
        sample_n=sample_n,
        sample_frac=sample_frac,
        cast_columns=json.dumps(cast_dict),
    )
    out.print(f"[green]Saved:[/] {written}")
    if errors_json:
        try:
            import json as _json
            for e in _json.loads(errors_json):
                err.print(f"[yellow]Skipped[/] {e['file']}: {e['error']}")
        except Exception:
            err.print(f"[yellow]Errors:[/] {errors_json}")
