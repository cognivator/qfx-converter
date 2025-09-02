# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QFX Converter is a CLI utility that converts Nordstrom QFX transaction files to Chase format for Quicken import. The conversion applies specific transformations:
- Changes FID from anything (Nordstrom is 12139) to 10898 (Chase Bank)
- Changes INTU.BID from anything (varies) to 10898
- Peserves the transaction amounts
- Preserves FITID tags and transaction descriptions

## Architecture

The project consists of three main components:

1. **qfx-convert-lib.py** - Core Python module containing:
   - `convert_qfx()` - Main conversion logic using regex transformations
   - `extract_date_range()` - Extracts DTSTART/DTEND from QFX files
   - `extract_latest_year()` - Determines output year from transaction dates
   - `verify_conversion()` - Built-in verification with detailed reporting

2. **qfx-convert** - Shell script wrapper that:
   - Detects Python 3 installation
   - Locates the Python converter script
   - Passes through all command-line arguments

3. **qfx-convert-verify.py** - Standalone verification utility for manual checking

## Common Commands

### Development and Testing
```bash
# Test conversion locally (before installation)
./qfx-convert test/transactions.qfx

# Manual verification
./qfx-convert-verify.py original.qfx converted.QFX

# Install system-wide
./setup.sh
```

### Production Usage (after installation)
```bash
# Basic conversion
qfx-convert

# Convert specific file
qfx-convert /path/to/file.qfx

# Custom output location
qfx-convert -o /output/dir file.qfx

# Skip verification for speed
qfx-convert --no-verify file.qfx
```

## Key Implementation Details

- Uses regex patterns to modify QFX XML structure
- Automatically extracts date ranges for output naming: `<startYYYYMMDD>-<endYYYYMMDD>_transactions.QFX`
- Creates year-based output directories (e.g., `./2025/`)
- Built-in verification compares original vs converted files
- Error handling for missing files, invalid QFX format, and conversion failures

## File Processing Flow

1. Parse command-line arguments with argparse
2. Extract date range from QFX DTSTART/DTEND tags
3. Apply FID/INTU.BID substitutions (* → 10898)
4. Generate output filename from date range
5. Write converted file to year-based directory
6. Automatically verify conversion success (unless --no-verify)

## Development Notes

- Test files are in `test/` directory
- No external dependencies beyond Python 3 standard library
- Uses UTF-8 encoding for file operations
- POSIX-compliant shell scripts for broad compatibility