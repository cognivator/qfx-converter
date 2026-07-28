#!/bin/sh
#
# run_tests.sh - Test runner for the qfx-convert utility.
#
# Responsibilities:
#   1. Fixture setup/validation: confirm the pristine masters exist. The suite
#      itself NEVER runs the CLI against these files - it copies each into a
#      private temp dir first. This runner enforces that contract by snapshotting
#      the fixtures (cksum) before and after the run and failing if any changed.
#   2. Invoke the unittest suite (all temp copies are made and cleaned up there).
#   3. Clean up ephemeral test data: __pycache__ and any leftover qfxtest_* temp
#      dirs, without touching real financial data.
#
set -eu

TEST_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$TEST_DIR/.." && pwd)"
FIXTURES_DIR="$TEST_DIR/fixtures"

# Pick Python 3.
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1 && python -c 'import sys;exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null; then
    PY=python
else
    echo "Error: Python 3 is required but not found" >&2
    exit 1
fi

# --- 1. Validate + snapshot fixtures ----------------------------------------
REQUIRED="nordstrom_2025_original.qfx nordstrom_2026_original.qfx nordstrom_2025_converted_legacy.QFX"
for f in $REQUIRED; do
    if [ ! -f "$FIXTURES_DIR/$f" ]; then
        echo "Error: missing fixture $FIXTURES_DIR/$f" >&2
        exit 1
    fi
done

# cksum is POSIX and always present; used to prove fixtures stay pristine.
snapshot() { ( cd "$FIXTURES_DIR" && cksum $REQUIRED ); }
BEFORE="$(snapshot)"

echo "Fixtures validated (pristine masters):"
echo "$BEFORE" | sed 's/^/  /'
echo

# --- 2. Run the suite --------------------------------------------------------
# The suite copies each fixture into its own temp dir; nothing runs in place.
echo "Running test suite..."
set +e
"$PY" "$TEST_DIR/test_qfx_convert.py" "$@"
STATUS=$?
set -e
echo

# --- 3. Prove fixtures were not adulterated ---------------------------------
AFTER="$(snapshot)"
if [ "$BEFORE" != "$AFTER" ]; then
    echo "ERROR: a fixture master changed during the run (tests must use copies)!" >&2
    echo "Before:" >&2; echo "$BEFORE" | sed 's/^/  /' >&2
    echo "After:"  >&2; echo "$AFTER"  | sed 's/^/  /' >&2
    exit 1
fi

# --- 4. Clean up ephemeral test data ----------------------------------------
# Compiled caches from importing the library during tests.
rm -rf "$TEST_DIR/__pycache__" "$PROJECT_ROOT/__pycache__" 2>/dev/null || true
# NOTE: we deliberately do NOT remove test/fixtures/temp here. Passing tests
# delete their own sandbox; FAILED tests keep theirs for inspection. The suite's
# setUpModule clears the whole temp/ tree at the START of the next run (which
# also sweeps up anything left by an abnormally-killed run). Everything under
# the gitignored fixtures tree is uncommittable regardless.

if [ "$STATUS" -eq 0 ]; then
    echo "All tests passed. Fixtures verified pristine; temp sandbox cleared."
else
    echo "Tests FAILED (exit $STATUS). Fixtures verified pristine; failed sandbox(es) kept under test/fixtures/temp/ for inspection (cleared at next run)." >&2
fi
exit "$STATUS"
