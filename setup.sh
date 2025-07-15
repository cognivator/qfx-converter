#!/bin/sh
#
# setup.sh - Installation script for qfx-convert utility
# Copies the QFX converter to /usr/local/bin for system-wide access
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(dirname "$0")"
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd)"  # Get absolute path

# Installation directory
INSTALL_DIR="/usr/local/bin"

# Files to install
PYTHON_SCRIPT="$SCRIPT_DIR/qfx_converter.py"
SHELL_SCRIPT="$SCRIPT_DIR/qfx-convert"
VERIFY_SCRIPT="$SCRIPT_DIR/verify_conversion.py"

echo "QFX Converter Setup"
echo "==================="

# Check if files exist
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "${RED}Error: qfx_converter.py not found at $PYTHON_SCRIPT${NC}" >&2
    exit 1
fi

if [ ! -f "$SHELL_SCRIPT" ]; then
    echo "${RED}Error: qfx-convert not found at $SHELL_SCRIPT${NC}" >&2
    exit 1
fi

if [ ! -f "$VERIFY_SCRIPT" ]; then
    echo "${RED}Error: verify_conversion.py not found at $VERIFY_SCRIPT${NC}" >&2
    exit 1
fi

# Check if installation directory exists and is writable
if [ ! -d "$INSTALL_DIR" ]; then
    echo "${RED}Error: Installation directory $INSTALL_DIR does not exist${NC}" >&2
    exit 1
fi

# Check for write permissions (will prompt for sudo if needed)
if [ ! -w "$INSTALL_DIR" ]; then
    echo "${YELLOW}Administrator privileges required to install to $INSTALL_DIR${NC}"
    SUDO_CMD="sudo"
else
    SUDO_CMD=""
fi

echo "Installing QFX converter..."
echo "Source directory: $SCRIPT_DIR"
echo "Install directory: $INSTALL_DIR"
echo

# Copy the Python script
echo "Installing qfx_converter.py..."
$SUDO_CMD cp "$PYTHON_SCRIPT" "$INSTALL_DIR/"
$SUDO_CMD chmod 755 "$INSTALL_DIR/qfx_converter.py"

# Copy the shell script
echo "Installing qfx-convert..."
$SUDO_CMD cp "$SHELL_SCRIPT" "$INSTALL_DIR/"
$SUDO_CMD chmod 755 "$INSTALL_DIR/qfx-convert"

# Copy the verification script
echo "Installing verify_conversion.py..."
$SUDO_CMD cp "$VERIFY_SCRIPT" "$INSTALL_DIR/"
$SUDO_CMD chmod 755 "$INSTALL_DIR/verify_conversion.py"

echo "${GREEN}Installation completed successfully!${NC}"
echo
echo "The qfx-convert command is now available system-wide."
echo "Usage examples:"
echo "  qfx-convert                          # Convert transactions.qfx in current directory"
echo "  qfx-convert /path/to/file.qfx        # Convert specific file"
echo "  qfx-convert --help                   # Show help"
echo
echo "To uninstall, run:"
echo "  sudo rm $INSTALL_DIR/qfx_converter.py $INSTALL_DIR/qfx-convert $INSTALL_DIR/verify_conversion.py"
