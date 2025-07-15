#!/usr/bin/env python3
"""
QFX Converter - Converts Nordstrom QFX files to Chase format for Quicken import
"""

import re
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path


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


def verify_conversion(original_content, converted_content, show_details=True):
    """Verify the conversion was successful"""
    orig_elements = extract_key_elements(original_content)
    conv_elements = extract_key_elements(converted_content)
    
    # Check each conversion requirement
    fid_changed = orig_elements['FID'] != conv_elements['FID']
    intu_changed = orig_elements['INTU.BID'] != conv_elements['INTU.BID']
    count_same = orig_elements['transaction_count'] == conv_elements['transaction_count']
    
    # Check if signs are reversed
    signs_reversed = True
    if orig_elements['amounts'] and conv_elements['amounts']:
        for orig, conv in zip(orig_elements['amounts'], conv_elements['amounts']):
            if abs(orig + conv) > 0.01:  # Allow for small floating point differences
                signs_reversed = False
                break
    
    success = fid_changed and intu_changed and count_same and signs_reversed
    
    if show_details:
        print("\n" + "="*50)
        print("CONVERSION VERIFICATION RESULTS")
        print("="*50)
        print(f"FID Changed:         {'✓' if fid_changed else '✗'} ({orig_elements['FID']} → {conv_elements['FID']})")
        print(f"INTU.BID Changed:    {'✓' if intu_changed else '✗'} ({orig_elements['INTU.BID']} → {conv_elements['INTU.BID']})")
        print(f"Transaction Count:   {'✓' if count_same else '✗'} ({orig_elements['transaction_count']} transactions)")
        print(f"Amount Signs Flipped: {'✓' if signs_reversed else '✗'}")
        print(f"\nOverall Status:      {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        if orig_elements['amounts']:
            print(f"\nSample Amount Changes (first 3):")
            for i, (orig, conv) in enumerate(zip(orig_elements['amounts'][:3], conv_elements['amounts'][:3])):
                print(f"  {orig:>8.2f} → {conv:>8.2f}")
        print("="*50)
    
    return success


def convert_qfx(input_content):
    """Apply conversion rules to QFX content"""
    # Make a copy to work with
    converted = input_content
    
    # Rule 2: Change FID and INTU.BID from 12139 to 10898 (Chase Bank)
    converted = re.sub(r'<FID>12139</FID>', '<FID>10898</FID>', converted)
    converted = re.sub(r'<INTU\.BID>12139</INTU\.BID>', '<INTU.BID>10898</INTU.BID>', converted)
    
    # Rule 3: Reverse the sign of each transaction amount
    def reverse_amount(match):
        amount = float(match.group(1))
        reversed_amount = -amount
        return f'<TRNAMT>{reversed_amount}</TRNAMT>'
    
    converted = re.sub(r'<TRNAMT>([^<]+)</TRNAMT>', reverse_amount, converted)
    
    return converted


def main():
    parser = argparse.ArgumentParser(description='Convert Nordstrom QFX files for Quicken import')
    parser.add_argument('input_file', nargs='?', default='transactions.qfx',
                       help='Input QFX file (default: transactions.qfx)')
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
        converted_content = convert_qfx(qfx_content)
        
        # Write output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(converted_content)
        
        print(f"Conversion completed successfully!")
        print(f"Input:  {args.input_file}")
        print(f"Output: {output_path}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Year: {latest_year}")
        
        # Automatically verify the conversion (unless disabled)
        if not args.no_verify:
            verification_success = verify_conversion(qfx_content, converted_content, show_details=True)
            
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
