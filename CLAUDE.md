# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QFX Converter is a CLI utility that adjusts the financial-institution id in a
Nordstrom QFX transaction file so Quicken will import it via Web Connect.
Nordstrom's directory entry `12139` supports only Express Web Connect (the
automatic feed that stopped working), so the utility rewrites the id in a
manually downloaded QFX file to a Web-Connect-capable id.

The id target is selected with `--fid`:
- `nord` (default) — Nordstrom Web Connect id `71411` (FID and INTU.BID)
- `chase` — Chase Web Connect id `10898` (fallback if `nord` fails to import)
- `orig` — leave FID/INTU.BID unchanged

Other behavior:
- Transaction amounts are preserved (no sign changes)
- FITID tags and transaction descriptions are preserved

The ids were verified against Intuit's Financial Institution Directory
(`fidir.txt`). Note: `10898` is genuinely Chase; `71411` is Nordstrom's own
Web-Connect entry (distinct from its Express-Web-Connect-only entry `12139`).

## Architecture

The project consists of three main components:

1. **qfx_convert_lib.py** - Core Python module and single source of truth:
   - `FID_TARGETS` / `DEFAULT_FID` - maps `--fid` choices to `(target_id, label)`
   - `convert_qfx(content, fid)` - id-rewrite logic (skipped for `orig`)
   - `extract_date_range()` - Extracts DTSTART/DTEND from QFX files
   - `extract_latest_year()` - Determines output year from transaction dates
   - `extract_key_elements()` - Pulls FID/INTU.BID/amounts/count for checks
   - `verify_conversion(orig, conv, fid, show_details)` - shared verification,
     used by both the built-in check and the standalone verifier
   - CLI entry point guarded by `if __name__ == '__main__'`, so importing the
     module is side-effect free

2. **qfx-convert** - Shell script wrapper (the command name) that:
   - Detects Python 3 installation
   - Locates `qfx_convert_lib.py` in its own directory
   - Passes through all command-line arguments

3. **qfx_convert_verify.py** - Standalone verifier. A thin CLI wrapper that
   imports `FID_TARGETS`, `DEFAULT_FID`, and `verify_conversion` from
   `qfx_convert_lib` (no duplicated logic) and only handles argument parsing and
   file I/O.

### Import / naming note

`qfx_convert_lib.py` must keep that exact underscore filename so it is a valid
importable module. `qfx_convert_verify.py` imports it by module name and relies
on Python putting the running script's own directory on `sys.path`; the library
sits in that same directory both in the repo and, after `setup.sh`, in
`/usr/local/bin`. The verifier installs as the extensionless command
`qfx-convert-verify`, which is fine because nothing imports the verifier itself.

## Common Commands

### Development and Testing
```bash
# Test conversion locally (before installation), default --fid nord
./qfx-convert test/transactions.qfx

# Try the Chase fallback id
./qfx-convert --fid chase test/transactions.qfx

# Leave ids unchanged
./qfx-convert --fid orig test/transactions.qfx

# Manual verification (pass the same --fid used for the conversion)
./qfx_convert_verify.py original.qfx converted.QFX
./qfx_convert_verify.py --fid chase original.qfx converted.QFX

# Install system-wide
./setup.sh
```

### Production Usage (after installation)
```bash
# Basic conversion (default --fid nord)
qfx-convert

# Convert specific file
qfx-convert /path/to/file.qfx

# Choose institution id
qfx-convert --fid chase file.qfx

# Custom output location
qfx-convert -o /output/dir file.qfx

# Skip verification for speed
qfx-convert --no-verify file.qfx
```

## Key Implementation Details

- Uses regex patterns to modify QFX XML structure
- `--fid` choices are derived from `FID_TARGETS` so they are defined once
- Only FID/INTU.BID are rewritten; transaction amounts are left untouched
- Automatically extracts date ranges for output naming: `<startYYYYMMDD>-<endYYYYMMDD>_transactions.QFX`
- Creates year-based output directories (e.g., `./2025/`)
- Verification is shared between the converter and the standalone tool, so both
  apply identical rules; for `orig` it checks ids are unchanged, otherwise it
  checks ids equal the chosen target
- Error handling for missing files, invalid QFX format, and conversion failures

## File Processing Flow

1. Parse command-line arguments with argparse (including `--fid`)
2. Extract date range from QFX DTSTART/DTEND tags
3. Apply FID/INTU.BID substitution per `--fid` (or skip it for `orig`)
4. Generate output filename from date range
5. Write converted file to year-based directory
6. Automatically verify conversion success for the chosen `--fid` (unless `--no-verify`)

## Development Notes

- Test files are in `test/` directory
- No external dependencies beyond Python 3 standard library
- Uses UTF-8 encoding for file operations
- POSIX-compliant shell scripts for broad compatibility

## Known / Open Items

- The utility does not adjust the online balance (`LEDGERBAL` / `AVAILBAL`)
  sign; that is a separate, still-open concern from the reconciliation issue.