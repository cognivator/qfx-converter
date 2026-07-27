#!/usr/bin/env python3
"""
QFX Converter - Adjusts the financial-institution ID in a Nordstrom QFX file
so Quicken will import it via Web Connect.

By default (--fid nord) it rewrites the FID/INTU.BID to Nordstrom's own
Web-Connect-capable id (71411). Use --fid chase to target Chase (10898) as a
fallback if the Nordstrom id fails to import, or --fid orig to leave the
ids unchanged.

The converter also embeds a small XML comment recording the requested --fid
choice, e.g. <!--QFX-CONVERT fid="nord" target="71411" tool-version="1.1"-->.
The verifier reads this marker to check the actual FID/INTU.BID fields against
what was *requested* (independent provenance), rather than auto-detecting the
target from the very field being validated. Use --no-marker to suppress it.

This module is import-safe: the constants and helper functions can be imported
by other tools (e.g. the standalone verifier) without triggering a conversion,
because the CLI entry point is guarded by `if __name__ == '__main__'`.
"""

import re
import sys
import os
import argparse
from pathlib import Path


# Target financial-institution ids for the --fid parameter.
# Each entry maps the choice to (target_id, human_label). A target_id of
# None means "leave the FID/INTU.BID unchanged".
#   nord  -> Nordstrom Card Account, Web Connect entry (verified in Intuit fidir.txt)
#   chase -> Chase, Web Connect entry (verified in Intuit fidir.txt)
#   orig  -> original file, no id substitution
#
# This table is the single source of truth for the valid --fid choices; both
# this converter and the standalone verifier derive their choices from it.
FID_TARGETS = {
    'nord':  ('71411', 'Nordstrom (Web Connect)'),
    'chase': ('10898', 'Chase (Web Connect)'),
    'orig':  (None,     'Original (unchanged)'),
}
DEFAULT_FID = 'nord'

# Version stamped into the embedded marker.
TOOL_VERSION = '1.1'

# Matches the embedded provenance marker and captures the requested fid.
# (fid is always written as the first attribute, so this stays simple/robust.)
_MARKER_RE = re.compile(r'<!--\s*QFX-CONVERT\s+fid="([^"]+)"[^>]*-->')


def make_marker(fid):
    """Build the QFX-CONVERT comment recording the requested fid choice.

    Note: XML comments may not contain a literal '--', so the marker uses only
    single hyphens.
    """
    target_id, _label = FID_TARGETS[fid]
    target = target_id if target_id is not None else 'orig'
    return f'<!--QFX-CONVERT fid="{fid}" target="{target}" tool-version="{TOOL_VERSION}"-->'


def strip_marker(qfx_content):
    """Remove any existing QFX-CONVERT marker (so re-conversions don't stack)."""
    return _MARKER_RE.sub('', qfx_content)


def read_marker(qfx_content):
    """Return the fid choice recorded in the file's QFX-CONVERT marker, or None
    if there is no marker (or it names an unknown choice)."""
    m = _MARKER_RE.search(qfx_content)
    if not m:
        return None
    fid = m.group(1)
    return fid if fid in FID_TARGETS else None


def extract_date_range(qfx_content):
    """Extract start and end dates from QFX content"""
    # Find DTSTART and DTEND
    start_match = re.search(r'<DTSTART>(\d{8})\d+\.?\d*</DTSTART>', qfx_content)
    end_match = re.search(r'<DTEND>(\d{8})\d+\.?\d*</DTEND>', qfx_content)
    
    if not start_match or not end_match:
        raise ValueError("Could not find date range in QFX file")
    
    start_date = start_match.group(1)
    end_date = end_match.group(1)
    
    return start_date, end_date


def extract_latest_year(qfx_content):
    """Extract the latest transaction year from QFX content"""
    # Find all transaction dates
    date_matches = re.findall(r'<DTPOSTED>(\d{4})\d+\.?\d*</DTPOSTED>', qfx_content)
    
    if not date_matches:
        # Fallback to end date year
        _, end_date = extract_date_range(qfx_content)
        return end_date[:4]
    
    # Return the latest year
    years = [int(date) for date in date_matches]
    return str(max(years))


def extract_key_elements(qfx_content):
    """Extract key elements from QFX for verification"""
    elements = {}
    
    # Extract FID
    fid_match = re.search(r'<FID>(\d+)</FID>', qfx_content)
    elements['FID'] = fid_match.group(1) if fid_match else 'Not found'
    
    # Extract INTU.BID  
    intu_match = re.search(r'<INTU\.BID>(\d+)</INTU\.BID>', qfx_content)
    elements['INTU.BID'] = intu_match.group(1) if intu_match else 'Not found'
    
    # Extract transaction amounts
    amounts = re.findall(r'<TRNAMT>([^<]+)</TRNAMT>', qfx_content)
    elements['amounts'] = [float(amt) for amt in amounts if amounts]
    
    # Count transactions
    transactions = re.findall(r'<STMTTRN>', qfx_content)
    elements['transaction_count'] = len(transactions)
    
    return elements


def verify_conversion(original_content, converted_content, fid=DEFAULT_FID, show_details=True):
    """Verify the conversion was successful for the given expected fid.

    Shared by the converter's automatic post-run check and by the standalone
    verifier, so both apply identical rules. The check of the actual
    FID/INTU.BID fields against the expected target is the non-tautological
    guarantee: when the caller derives `fid` from the file's marker, this
    confirms the real ids match what was *requested*.
    """
    orig_elements = extract_key_elements(original_content)
    conv_elements = extract_key_elements(converted_content)

    target_id, label = FID_TARGETS[fid]

    # Check the id requirements based on the expected target.
    if target_id is None:
        # 'orig': ids must be left unchanged.
        fid_ok = conv_elements['FID'] == orig_elements['FID']
        intu_ok = conv_elements['INTU.BID'] == orig_elements['INTU.BID']
    else:
        # 'nord'/'chase': ids must equal the target id.
        fid_ok = conv_elements['FID'] == target_id
        intu_ok = conv_elements['INTU.BID'] == target_id

    count_same = orig_elements['transaction_count'] == conv_elements['transaction_count']

    # Check if amounts are preserved (not reversed)
    amounts_preserved = True
    if orig_elements['amounts'] and conv_elements['amounts']:
        for orig, conv in zip(orig_elements['amounts'], conv_elements['amounts']):
            if abs(orig - conv) > 0.01:  # Allow for small floating point differences
                amounts_preserved = False
                break

    # Marker consistency: if the file records a requested fid, it must match the
    # fid we are verifying against. An absent marker is not itself a failure
    # (older files, or files produced with --no-marker).
    marker_fid = read_marker(converted_content)
    marker_ok = (marker_fid is None) or (marker_fid == fid)

    success = fid_ok and intu_ok and count_same and amounts_preserved and marker_ok

    if show_details:
        marker_display = marker_fid if marker_fid is not None else '(none)'
        print("\n" + "="*50)
        print("CONVERSION VERIFICATION RESULTS")
        print("="*50)
        print(f"Target institution:  {label}")
        print(f"Marker (requested):  {'✓' if marker_ok else '✗'} ({marker_display})")
        print(f"FID:                 {'✓' if fid_ok else '✗'} ({orig_elements['FID']} → {conv_elements['FID']})")
        print(f"INTU.BID:            {'✓' if intu_ok else '✗'} ({orig_elements['INTU.BID']} → {conv_elements['INTU.BID']})")
        print(f"Transaction Count:   {'✓' if count_same else '✗'} ({orig_elements['transaction_count']} transactions)")
        print(f"Amounts Preserved:   {'✓' if amounts_preserved else '✗'}")
        print(f"\nOverall Status:      {'✓ SUCCESS' if success else '✗ FAILED'}")

        if orig_elements['amounts']:
            print(f"\nSample Amounts (first 3):")
            for i, (orig, conv) in enumerate(zip(orig_elements['amounts'][:3], conv_elements['amounts'][:3])):
                print(f"  {orig:>8.2f} → {conv:>8.2f}")
        print("="*50)

    return success


def convert_qfx(input_content, fid=DEFAULT_FID, write_marker=True):
    """Apply conversion rules to QFX content.

    The --fid choice controls the FID/INTU.BID rewrite:
      nord  -> 71411 (Nordstrom Web Connect, default)
      chase -> 10898 (Chase Web Connect)
      orig  -> leave FID/INTU.BID unchanged

    When write_marker is True, a QFX-CONVERT comment recording the requested
    fid is embedded just after <OFX> for the verifier to read.
    """
    # Make a copy to work with
    converted = input_content

    target_id, _label = FID_TARGETS[fid]

    # Rule 1: Set FID and INTU.BID to the chosen institution id
    # (skipped entirely when target_id is None, i.e. --fid orig).
    if target_id is not None:
        converted = re.sub(r'<FID>\d+</FID>', f'<FID>{target_id}</FID>', converted)
        converted = re.sub(r'<INTU\.BID>\d+</INTU\.BID>', f'<INTU.BID>{target_id}</INTU.BID>', converted)

    # Rule 2: Record the requested fid choice as a marker comment.
    # Always strip any prior marker first so re-conversions don't stack them;
    # only re-embed when write_marker is True.
    converted = strip_marker(converted)
    if write_marker:
        marker = make_marker(fid)
        # Inject immediately after the opening <OFX> tag (use a lambda so the
        # marker text is inserted literally, never interpreted as a backref).
        converted = re.sub(r'(<OFX>)', lambda m: m.group(1) + marker, converted, count=1)

    return converted


def main():
    parser = argparse.ArgumentParser(description='Convert Nordstrom QFX files for Quicken import')
    parser.add_argument('input_file', nargs='?', default='transactions.qfx',
                       help='Input QFX file (default: transactions.qfx)')
    parser.add_argument('--fid', choices=list(FID_TARGETS), default=DEFAULT_FID,
                       help="Financial-institution id to write into FID/INTU.BID: "
                            "'nord' (default) = Nordstrom Web Connect (71411); "
                            "'chase' = Chase Web Connect (10898); "
                            "'orig' = leave the ids unchanged")
    parser.add_argument('--no-marker', action='store_true',
                       help='Do not embed the QFX-CONVERT fid marker comment in the output')
    parser.add_argument('--output-dir', '-o', 
                       help='Output directory (default: ./<YEAR>/)')
    parser.add_argument('--output-file', '-f',
                       help='Output filename (default: auto-generated from dates)')
    parser.add_argument('--no-verify', action='store_true',
                       help='Skip automatic verification of conversion')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Read input file
        with open(args.input_file, 'r', encoding='utf-8') as f:
            qfx_content = f.read()
        
        # Extract date information
        start_date, end_date = extract_date_range(qfx_content)
        latest_year = extract_latest_year(qfx_content)
        
        # Determine output directory
        if args.output_dir:
            output_dir = Path(args.output_dir)
        else:
            output_dir = Path(f'./{latest_year}')
        
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine output filename
        if args.output_file:
            output_filename = args.output_file
        else:
            output_filename = f'{start_date}-{end_date}_transactions.QFX'
        
        output_path = output_dir / output_filename
        
        # Convert QFX content
        converted_content = convert_qfx(qfx_content, args.fid, write_marker=not args.no_marker)
        
        # Write output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(converted_content)
        
        print(f"Conversion completed successfully!")
        print(f"Input:  {args.input_file}")
        print(f"Output: {output_path}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Year: {latest_year}")
        print(f"Institution: {FID_TARGETS[args.fid][1]}")
        print(f"Marker: {'omitted (--no-marker)' if args.no_marker else 'embedded'}")
        
        # Automatically verify the conversion (unless disabled)
        if not args.no_verify:
            verification_success = verify_conversion(qfx_content, converted_content,
                                                     fid=args.fid, show_details=True)
            
            if not verification_success:
                print("\n⚠️  WARNING: Conversion verification failed! Please check the output file.")
                sys.exit(1)
        else:
            print("\nVerification skipped (--no-verify flag used)")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()