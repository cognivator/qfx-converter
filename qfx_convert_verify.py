#!/usr/bin/env python3
"""
QFX Verification Script - standalone CLI wrapper.

Compares an original QFX file against a converted one using the SHARED
verification logic in qfx_convert_lib, so the post-hoc check applies exactly
the same rules as the converter's built-in verification.

By default the expected fid is read from the converted file's QFX-CONVERT
marker (the id that was *requested* at conversion time), which is independent
of the FID field being validated. Passing --fid turns the run into an assertion
that must agree with the marker. If no marker is present (older file or one made
with --no-marker), it falls back to --fid, or to the library default.
"""

import argparse
import sys

# Shared, single-source-of-truth logic from the converter library.
# (Import is safe: qfx_convert_lib guards its CLI under __main__.)
from qfx_convert_lib import DEFAULT_FID, FID_TARGETS, read_marker, verify_conversion


def main():
    parser = argparse.ArgumentParser(description='Verify a QFX conversion')
    parser.add_argument('original', help='Original QFX file')
    parser.add_argument('converted', help='Converted QFX file')
    parser.add_argument('--fid', choices=list(FID_TARGETS), default=None,
                        help="Assert the file was converted to this id. If omitted, the "
                             "expected id is read from the file's QFX-CONVERT marker "
                             f"(falling back to '{DEFAULT_FID}' if no marker is present). "
                             "If provided, it must match the marker when one exists.")

    args = parser.parse_args()

    # Read both files (I/O lives here; all checking lives in the shared lib).
    try:
        with open(args.original, 'r', encoding='utf-8') as f:
            original_content = f.read()
        with open(args.converted, 'r', encoding='utf-8') as f:
            converted_content = f.read()
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    marker_fid = read_marker(converted_content)

    # Decide which fid to verify against.
    if args.fid is not None:
        # Explicit assertion: it must agree with the file's own claim (if any).
        if marker_fid is not None and marker_fid != args.fid:
            print(f"Error: --fid {args.fid} contradicts the file's marker "
                  f"(fid={marker_fid}).", file=sys.stderr)
            sys.exit(2)
        expected_fid = args.fid
        source = "command line"
    elif marker_fid is not None:
        expected_fid = marker_fid
        source = "file marker"
    else:
        expected_fid = DEFAULT_FID
        source = "default (no marker found)"

    print("QFX Conversion Verification")
    print("===========================")
    print(f"Original file:  {args.original}")
    print(f"Converted file: {args.converted}")
    print(f"Expected fid:   {expected_fid}  (from {source})")

    success = verify_conversion(original_content, converted_content,
                                fid=expected_fid, show_details=True)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()