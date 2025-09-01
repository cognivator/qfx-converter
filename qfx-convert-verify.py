#!/usr/bin/env python3
"""
QFX Verification Script - Compare original and converted QFX files
"""

import re
import sys
import argparse


def extract_key_elements(qfx_content):
    """Extract key elements from QFX for comparison"""
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


def main():
    parser = argparse.ArgumentParser(description='Verify QFX conversion')
    parser.add_argument('original', help='Original QFX file')
    parser.add_argument('converted', help='Converted QFX file')
    
    args = parser.parse_args()
    
    try:
        # Read files
        with open(args.original, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        with open(args.converted, 'r', encoding='utf-8') as f:
            converted_content = f.read()
        
        # Extract elements
        orig_elements = extract_key_elements(original_content)
        conv_elements = extract_key_elements(converted_content)
        
        print("QFX Conversion Verification")
        print("===========================")
        print()
        
        print(f"Original file:  {args.original}")
        print(f"Converted file: {args.converted}")
        print()
        
        # Compare FID
        print("FID (Financial Institution ID):")
        print(f"  Original:  {orig_elements['FID']}")
        print(f"  Converted: {conv_elements['FID']}")
        print(f"  Status:    {'✓ Changed' if orig_elements['FID'] != conv_elements['FID'] else '✗ Unchanged'}")
        print()
        
        # Compare INTU.BID
        print("INTU.BID:")
        print(f"  Original:  {orig_elements['INTU.BID']}")
        print(f"  Converted: {conv_elements['INTU.BID']}")
        print(f"  Status:    {'✓ Changed' if orig_elements['INTU.BID'] != conv_elements['INTU.BID'] else '✗ Unchanged'}")
        print()
        
        # Compare transaction count
        print("Transaction Count:")
        print(f"  Original:  {orig_elements['transaction_count']}")
        print(f"  Converted: {conv_elements['transaction_count']}")
        print(f"  Status:    {'✓ Same' if orig_elements['transaction_count'] == conv_elements['transaction_count'] else '✗ Different'}")
        print()
        
        # Compare amounts (check if signs are reversed)
        print("Transaction Amounts (first 5):")
        orig_amounts = orig_elements['amounts'][:5]
        conv_amounts = conv_elements['amounts'][:5]
        
        signs_reversed = True
        for orig, conv in zip(orig_amounts, conv_amounts):
            print(f"  {orig:>8.2f} → {conv:>8.2f}")
            if abs(orig + conv) > 0.01:  # Allow for small floating point differences
                signs_reversed = False
                
        print(f"  Status:    {'✓ Signs reversed' if signs_reversed else '✗ Signs not properly reversed'}")
        print()
        
        # Summary
        all_good = (
            orig_elements['FID'] != conv_elements['FID'] and
            orig_elements['INTU.BID'] != conv_elements['INTU.BID'] and
            orig_elements['transaction_count'] == conv_elements['transaction_count'] and
            signs_reversed
        )
        
        print("Overall Status:")
        print(f"  {'✓ Conversion appears successful!' if all_good else '✗ Conversion may have issues'}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
