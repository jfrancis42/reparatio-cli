# reparatio — CLI

> **Alpha software.** Commands, options, and output formats may change without notice between versions.

Command-line tool for the [Reparatio](https://reparatio.app) data conversion API.

Convert, inspect, merge, append, and query CSV, Excel, Parquet, JSON, GeoJSON, SQLite, and 30+ other formats directly from your terminal.

**See also:** [reparatio-mcp](https://github.com/jfrancis42/reparatio-mcp) (MCP server for AI assistants) · [reparatio-sdk](https://github.com/jfrancis42/reparatio-sdk) (Python SDK)

---

## Installation

**Via pipx (recommended — isolated, no dependency conflicts):**

```bash
pipx install reparatio-cli
```

**Via uv:**

```bash
uv tool install reparatio-cli
```

**Via pip:**

```bash
pip install reparatio-cli
```

All three methods install a `reparatio` command on your PATH.

---

## Quick start

```bash
# 1. Set your API key (get one at reparatio.app)
reparatio key set rp_YOUR_KEY

# 2. Inspect a file
reparatio inspect sales.csv

# 3. Convert it
reparatio convert sales.csv sales.parquet
```

---

## Pricing

| Plan | Price | Max file | Formats | API / CLI / MCP |
|---|---|---|---|---|
| Free (anonymous) | $0 | 10 MB | Basic (csv, tsv, xlsx, json, jsonl, parquet) | No |
| Free (registered) | $0 | 10 MB | Basic | No |
| Standard | $29/month | 500 MB | All formats | No |
| Professional | $79/month | 2 GB | All formats + Fixed-Width + EBCDIC | Yes |
| Credits | $10 = 25 conversions | 500 MB | All formats (no API/FWF/EBCDIC) | No |

**The Professional plan is required to use the CLI, REST API, Python/JS SDKs, MCP server, Fixed-Width parser, and EBCDIC encoding support.**

Get an API key at [reparatio.app](https://reparatio.app).

---

## Authentication

The API key can be configured in three ways, in order of precedence:

1. **Environment variable:** `export REPARATIO_API_KEY=rp_...`
2. **Stored key:** `reparatio key set rp_...` (saved to `~/.config/reparatio/config.json`)
3. **No key:** only `inspect` and `formats` work without a key

---

## Command reference

### `reparatio key`

Manage your API key.

```bash
reparatio key set rp_YOUR_KEY   # Save to disk
reparatio key show               # Print the current key
reparatio key clear              # Remove the stored key
```

---

### `reparatio me`

Show subscription details for the current API key.

```
$ reparatio me

  Email      alice@example.com
  Plan       pro
  Active     yes
  API access yes
  Expires    2026-04-01T00:00:00Z
```

---

### `reparatio formats`

List all supported input and output formats.

```bash
reparatio formats          # Pretty table
reparatio formats --json   # Raw JSON
```

No API key required.

---

### `reparatio inspect FILE`

Inspect a file: encoding, row count, column types, null counts, unique counts, and a data preview.

```bash
reparatio inspect sales.csv
reparatio inspect report.xlsx --sheet Q3
reparatio inspect data.csv --preview-rows 20
reparatio inspect data.tsv --delimiter $'\t'
reparatio inspect file.csv --json    # Machine-readable output
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--preview-rows N` | `8` | Number of preview rows (1–100) |
| `--no-header` | off | Treat first row as data |
| `--no-fix-encoding` | off | Disable encoding repair |
| `--delimiter TEXT` | auto | Custom delimiter |
| `--sheet TEXT` | first | Sheet or table name (Excel, ODS, SQLite) |
| `--json` | off | Output raw JSON |

No API key required.

---

### `reparatio convert INPUT [OUTPUT]`

Convert a file to any supported format.

The output format is inferred from the `OUTPUT` filename extension.
If `OUTPUT` is omitted, the result is written next to `INPUT` with the appropriate extension.

```bash
# Basic
reparatio convert sales.csv sales.parquet
reparatio convert report.xlsx report.csv

# Output format without specifying a full output path
reparatio convert sales.csv --format json.gz

# Select columns
reparatio convert big.csv slim.csv --select date,region,revenue

# Rename columns
reparatio convert data.csv renamed.csv --rename Date,Region,Revenue

# Deduplicate
reparatio convert events.csv clean.csv --deduplicate

# Sample
reparatio convert huge.csv sample.csv --sample-n 10000
reparatio convert huge.csv sample.csv --sample-frac 0.05

# Encoding issues (legacy Windows CSV)
reparatio convert legacy.csv fixed.xlsx

# EBCDIC mainframe file (cp037 = EBCDIC US, cp500 = EBCDIC International)
reparatio convert mainframe.dat output.csv --encoding cp037
reparatio convert ibm.dat output.csv --encoding cp500

# Read a specific Excel sheet
reparatio convert workbook.xlsx q3.csv --sheet Q3

# Compressed output
reparatio convert data.csv data.csv.gz
reparatio convert data.csv data.parquet    # already compressed by Parquet
```

**Options:**

| Option | Description |
|---|---|
| `--format TEXT` | Output format (inferred from OUTPUT if omitted) |
| `--no-header` | Treat first row as data |
| `--no-fix-encoding` | Disable encoding repair |
| `--delimiter TEXT` | Custom delimiter for CSV-like input |
| `--sheet TEXT` | Sheet or table name |
| `--select col1,col2` | Columns to include in output |
| `--rename col1,col2` | New column names in order |
| `--deduplicate` | Remove duplicate rows |
| `--sample-n N` | Random sample of N rows |
| `--sample-frac F` | Random sample fraction (e.g. `0.1` for 10%) |
| `--geometry-column TEXT` | WKT geometry column for GeoJSON output |
| `--null-values TEXT` | Comma-separated strings to treat as null, e.g. `"N/A,NULL,-"` |
| `--cast COL=TYPE[:FORMAT]` | Override a column type (repeatable) |
| `--encoding TEXT` | Force a specific encoding (bypasses auto-detection), e.g. `cp037` for EBCDIC US, `cp500` for EBCDIC International |

**`--null-values` example:**

```bash
# Treat "N/A", "NULL", and "-" as null values when loading
reparatio convert legacy.csv clean.parquet --null-values "N/A,NULL,-"
```

**`--cast` examples:**

```bash
# Cast price to Float64
reparatio convert data.csv out.parquet --cast price=Float64

# Parse dates in day/month/year format
reparatio convert data.csv out.parquet --cast date=Date:"%d/%m/%Y"

# Multiple overrides
reparatio convert data.csv out.parquet --cast price=Float64 --cast qty=Int32
```

Supported types: `String`, `Int8`–`Int64`, `UInt8`–`UInt64`, `Float32`, `Float64`,
`Boolean`, `Date` (optionally `Date:FORMAT`), `Datetime` (optionally `Datetime:FORMAT`), `Time`.

---

### `reparatio batch-convert ZIP_FILE`

Convert every file inside a ZIP archive to a common format.
Returns a ZIP of converted files. Files that cannot be parsed are skipped with a warning.

```bash
reparatio batch-convert monthly_reports.zip --format parquet
reparatio batch-convert raw_data.zip --format csv.gz -o processed.zip
reparatio batch-convert data.zip --format parquet --cast price=Float64
```

**Options:**

| Option | Description |
|---|---|
| `--format TEXT` | Output format (required) |
| `--output FILE` | Output ZIP path (default: `converted.zip`) |
| `--no-header` | Treat first row as data |
| `--no-fix-encoding` | Disable encoding repair |
| `--delimiter TEXT` | Custom delimiter |
| `--select col1,col2` | Columns to include from every file |
| `--deduplicate` | Remove duplicate rows from each file |
| `--sample-n N` | Random sample of N rows per file |
| `--sample-frac F` | Random sample fraction per file |
| `--cast COL=TYPE[:FORMAT]` | Column type override (repeatable) |

---

### `reparatio merge FILE1 FILE2`

Merge or join two files.

```bash
# Left join on customer_id, output as Parquet
reparatio merge orders.csv customers.xlsx --op left --on customer_id --format parquet

# Stack two files (append/union)
reparatio merge jan.csv feb.csv --op append --format csv -o q1.csv

# Inner join on multiple columns
reparatio merge a.csv b.csv --op inner --on "user_id,date" --format xlsx
```

**`--op` values:**

| Value | Behaviour |
|---|---|
| `append` | Stack all rows from both files; missing columns filled with null |
| `left` | All rows from FILE1; matching columns from FILE2 |
| `right` | All rows from FILE2; matching columns from FILE1 |
| `outer` | All rows from both files; nulls where no match |
| `inner` | Only rows present in both files |

**Options:**

| Option | Description |
|---|---|
| `--op` | Join operation (required) |
| `--format TEXT` | Output format (required) |
| `--on col1,col2` | Columns to join on (not needed for `append`) |
| `--output / -o PATH` | Output path (defaults to FILE1 directory) |
| `--no-header` | Treat first row as data |
| `--no-fix-encoding` | Disable encoding repair |
| `--geometry-column TEXT` | WKT geometry column for GeoJSON output |

---

### `reparatio append FILES...`

Stack rows from two or more files vertically.

Column mismatches are handled gracefully — missing values are filled with null.

```bash
# Stack three monthly CSVs into a single Parquet file
reparatio append jan.csv feb.csv mar.csv --format parquet -o q1.parquet

# Using shell glob
reparatio append monthly/*.csv --format csv -o all_months.csv
```

**Options:**

| Option | Description |
|---|---|
| `--format TEXT` | Output format (required) |
| `--output / -o PATH` | Output path (defaults to `appended.<format>` next to the first file) |
| `--no-header` | Treat first row as data |
| `--no-fix-encoding` | Disable encoding repair |

---

### `reparatio query FILE SQL`

Run a SQL query against a file. The file is loaded as a table named `data`.

```bash
# Aggregate
reparatio query events.parquet "SELECT region, SUM(revenue) AS total FROM data GROUP BY region ORDER BY total DESC"

# Filter and limit
reparatio query sales.csv "SELECT * FROM data WHERE amount > 1000 ORDER BY date DESC LIMIT 50" --format xlsx

# Read a specific sheet
reparatio query workbook.xlsx "SELECT COUNT(*) FROM data" --sheet Summary

# Output as JSON
reparatio query data.parquet "SELECT * FROM data LIMIT 10" --format json -o preview.json
```

Supports `SELECT`, `WHERE`, `GROUP BY`, `ORDER BY`, `LIMIT`, aggregations, and most scalar functions.

**Options:**

| Option | Default | Description |
|---|---|---|
| `--format TEXT` | `csv` | Output format |
| `--output / -o PATH` | auto | Output path |
| `--no-header` | off | Treat first row as data |
| `--no-fix-encoding` | off | Disable encoding repair |
| `--delimiter TEXT` | auto | Custom delimiter for CSV-like input |
| `--sheet TEXT` | first | Sheet or table name |

---

## Supported formats

### Input

CSV, TSV, CSV.GZ, CSV.BZ2, CSV.ZST, CSV.ZIP, TSV.GZ, TSV.BZ2, TSV.ZST, TSV.ZIP, GZ (any supported format), ZIP (any supported format), BZ2 (any supported format), ZST (any supported format), Excel (.xlsx / .xls), ODS, JSON, JSON.GZ, JSON.BZ2, JSON.ZST, JSON.ZIP, JSON Lines, GeoJSON, Parquet, Feather, Arrow, ORC, Avro, SQLite, YAML, BSON, SRT, VTT, HTML, Markdown, XML, SQL dump, PDF (text layer)

### Output

CSV, TSV, CSV.GZ, CSV.BZ2, CSV.ZST, CSV.ZIP, TSV.GZ, TSV.BZ2, TSV.ZST, TSV.ZIP, Excel (.xlsx), ODS, JSON, JSON.GZ, JSON.BZ2, JSON.ZST, JSON.ZIP, JSON Lines, JSON Lines.GZ, JSON Lines.BZ2, JSON Lines.ZST, JSON Lines.ZIP, GeoJSON, GeoJSON.GZ, GeoJSON.BZ2, GeoJSON.ZST, GeoJSON.ZIP, Parquet, Feather, Arrow, ORC, Avro, SQLite, YAML, BSON, SRT, VTT

Run `reparatio formats` for the authoritative live list.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error (authentication, parse failure, API error, etc.) |

---

## Privacy

Files are sent to the Reparatio API at `reparatio.app` for processing.
Files are handled in memory and never stored — see the [Privacy Policy](https://reparatio.app).
