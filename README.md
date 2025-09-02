# QFX Converter

A CLI utility that converts Nordstrom QFX transaction files to Chase format for Quicken import.

## Overview

This utility applies the following transformations to Nordstrom QFX files:

1. Changes FID from anything (Nordstrom is 12139) to 10898 (Chase Bank)
2. Changes INTU.BID from anything to 10898
3. Preserves the transaction amounts
4. Maintains all existing FITID tags (no changes needed)
5. Maintains all transaction descriptions (no changes needed)

## Installation

Run the setup script to install the utility system-wide:

```bash
cd ~/DEV/qfx-converter
./setup.sh
```

This will copy the scripts to `/usr/local/bin` and make the `qfx-convert` command available globally.

## Usage

### Basic Usage

Convert `transactions.qfx` in the current directory:
```bash
qfx-convert
```

### Specify Input File

Convert a specific QFX file:
```bash
qfx-convert /path/to/your/file.qfx
```

### Specify Output Directory

Convert and save to a specific directory:
```bash
qfx-convert -o /path/to/output/dir transactions.qfx
```

### Specify Output Filename

Convert and use a custom filename:
```bash
qfx-convert -f custom_name.QFX transactions.qfx
```

### Skip Automatic Verification

Convert without verification (faster):
```bash
qfx-convert --no-verify transactions.qfx
```

## Output

The utility automatically:

1. **Extracts date range** from the QFX file's DTSTART and DTEND fields
2. **Determines output year** from the latest transaction date
3. **Creates output directory** named with the year (e.g., `./2025/`)
4. **Generates filename** using the pattern: `<startYYYYMMDD>-<endYYYYMMDD>_transactions.QFX`

Example output: `./2025/20250607-20250715_transactions.QFX`

## Automatic Verification

The utility **automatically verifies** each conversion and displays results:

```
==================================================
CONVERSION VERIFICATION RESULTS
==================================================
FID Changed:         ✓ (12139 → 10898)
INTU.BID Changed:    ✓ (12139 → 10898)
Transaction Count:   ✓ (7 transactions)
Amount Signs Flipped: ✓

Overall Status:      ✓ SUCCESS

Sample Amount Changes (first 3):
    -92.59 →    92.59
    -77.07 →    77.07
    145.00 →  -145.00
==================================================
```

**Verification checks:**
- ✅ FID changed from 12139 to 10898
- ✅ INTU.BID changed from 12139 to 10898  
- ✅ Transaction count preserved
- ✅ All amounts have signs reversed

**Skip verification** with `--no-verify` flag for faster processing.

## Manual Verification

A standalone verification script is also available:

```bash
verify_conversion.py original.qfx converted.QFX
```

## File Structure

```
~/DEV/qfx-converter/
├── qfx-convert             # Shell script wrapper
├── qfx-convert-lib.py      # Main Python conversion logic
├── qfx-convert-verify.py   # Standalone verification script
├── setup.sh                # Installation script
├── README.md               # This documentation
└── test/                   # Test directory (created during development)
```

## Requirements

- Python 3.x
- POSIX-compliant shell (sh, bash, zsh)

## Quicken Import Process

After conversion:

1. Import the converted QFX file into Quicken
2. A new Chase Bank account will be created
3. Move the imported transactions to your existing Nordstrom account
4. Delete the temporary Chase Bank account

## Uninstallation

To remove the utility:

```bash
sudo rm /usr/local/bin/qfx-convert /usr/local/bin/qfx-convert-lib.py /usr/local/bin/qfx-convert-verify.py
```

## Development

The utility is developed in `~/DEV/qfx-converter/` with financial data stored in `~/Documents/Finance/Statements/NordstromCard/`.

### Testing

Test the utility before installation:

```bash
cd ~/DEV/qfx-converter
./qfx-convert test/transactions.qfx
```

## License

This utility is provided as-is for personal use in converting Nordstrom QFX files for Quicken import.
