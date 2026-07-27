# QFX Converter

A CLI utility that adjusts the financial-institution id in a Nordstrom QFX
transaction file so Quicken will import it via Web Connect.

## Overview

Nordstrom's card stopped updating automatically in Quicken (its directory entry
`12139` supports only Express Web Connect, the automatic aggregation feed). This
utility rewrites the id in a manually downloaded QFX file to an id that supports
Web Connect (QFX) import, then you import the file.

By default it targets **Nordstrom's own Web-Connect id (`71411`)** so the file
imports under the card's real identity. A Chase id (`10898`) is available as a
fallback, and you can also leave the id untouched. The utility:

1. Rewrites `FID` and `INTU.BID` according to `--fid` (see below)
2. Preserves the transaction amounts (no sign changes)
3. Maintains all existing `FITID` tags (no changes needed)
4. Maintains all transaction descriptions (no changes needed)

### `--fid` options

| `--fid` value | Target | FID / INTU.BID |
|---------------|--------|----------------|
| `nord` (default) | Nordstrom (Web Connect) | `71411` |
| `chase` | Chase (Web Connect) | `10898` |
| `orig` | Leave the file's ids unchanged | (unchanged) |

The ids were verified against Intuit's Financial Institution Directory
(`fidir.txt`). Use `nord` unless it fails to import, then try `chase`.

## Installation

Run the setup script to install the utility system-wide:

```bash
cd ~/DEV/qfx-converter
./setup.sh
```

This copies the scripts to `/usr/local/bin` and makes the `qfx-convert` and
`qfx-convert-verify` commands available globally. The library file
`qfx_convert_lib.py` is installed alongside them (the verifier imports it).

## Usage

### Basic Usage

Convert `transactions.qfx` in the current directory (default `--fid nord`):
```bash
qfx-convert
```

### Choose the institution id

```bash
qfx-convert --fid nord  transactions.qfx   # Nordstrom Web Connect (71411) — default
qfx-convert --fid chase transactions.qfx   # Chase Web Connect (10898) — fallback
qfx-convert --fid orig  transactions.qfx   # leave FID/INTU.BID unchanged
```

### Specify Input File

```bash
qfx-convert /path/to/your/file.qfx
```

### Specify Output Directory

```bash
qfx-convert -o /path/to/output/dir transactions.qfx
```

### Specify Output Filename

```bash
qfx-convert -f custom_name.QFX transactions.qfx
```

### Skip Automatic Verification

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
Target institution:  Nordstrom (Web Connect)
FID:                 ✓ (12139 → 71411)
INTU.BID:            ✓ (98932 → 71411)
Transaction Count:   ✓ (7 transactions)
Amounts Preserved:   ✓

Overall Status:      ✓ SUCCESS

Sample Amounts (first 3):
    -92.59 →   -92.59
    -77.07 →   -77.07
    145.00 →   145.00
==================================================
```

**Verification checks:**
- ✅ FID set to the target for the chosen `--fid` (or unchanged for `orig`)
- ✅ INTU.BID set to the target for the chosen `--fid` (or unchanged for `orig`)
- ✅ Transaction count preserved
- ✅ Transaction amounts preserved (not altered)

**Skip verification** with `--no-verify` for faster processing.

## Manual Verification

A standalone verifier is also available. It shares the same checking logic as the
built-in verification (imported from `qfx_convert_lib`), so results are
consistent no matter how verification is initiated.

```bash
# Installed command
qfx-convert-verify original.qfx converted.QFX

# From the repo
./qfx_convert_verify.py original.qfx converted.QFX
```

Pass the **same** `--fid` you used for the conversion so the check targets the
right id (defaults to `nord`):

```bash
qfx-convert-verify --fid chase original.qfx converted.QFX
```

## File Structure

```
~/DEV/qfx-converter/
├── qfx-convert              # Shell script wrapper (command name)
├── qfx_convert_lib.py       # Main Python conversion logic + shared verification
├── qfx_convert_verify.py    # Standalone verifier (imports qfx_convert_lib)
├── setup.sh                 # Installation script
├── README.md                # This documentation
└── test/                    # Test directory
```

## Requirements

- Python 3.x
- POSIX-compliant shell (sh, bash, zsh)

## Quicken Import Process

After conversion:

1. Import the converted QFX file into Quicken.
2. With `--fid nord` (default), Quicken should recognize the file as the
   Nordstrom card and let you add/link the transactions to your existing
   Nordstrom account.
3. If the Nordstrom id fails to import, re-run with `--fid chase`. Quicken will
   create a temporary Chase account; move the imported transactions to your
   Nordstrom account, then delete the temporary Chase account.

## Uninstallation

To remove the utility:

```bash
sudo rm /usr/local/bin/qfx_convert_lib.py /usr/local/bin/qfx-convert /usr/local/bin/qfx-convert-verify
```

## Development

The utility is developed in `~/DEV/qfx-converter/` with financial data stored in
`~/Documents/Finance/Statements/NordstromCard/`.

### Testing

Test the utility before installation:

```bash
cd ~/DEV/qfx-converter
./qfx-convert test/transactions.qfx
./qfx_convert_verify.py test/transactions.qfx 2025/<converted-file>.QFX
```

## License

This utility is provided as-is for personal use in converting Nordstrom QFX
files for Quicken import.