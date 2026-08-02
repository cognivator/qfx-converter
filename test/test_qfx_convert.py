#!/usr/bin/env python3
"""
Test suite for the QFX converter CLI utility.

Covers the library-level helpers and the two command-line surfaces:
  * qfx_convert_lib.py  (the `qfx-convert` command)
  * qfx_convert_verify.py (the `qfx-convert-verify` command)

Isolation contract
------------------
Pristine sample inputs live in test/fixtures/ and are treated as read-only.
Every test that runs the CLI first COPIES the fixture it needs into a private
temporary directory under test/fixtures/temp/ (see _Base.setUp/stage) and runs
the tool there, then asserts on the produced (AFTER) file. Fixtures are never
passed to the CLI directly, so the masters stay byte-for-byte pristine. A passing
test deletes its own sandbox; a FAILED test keeps its sandbox (named after the
Class.method) so the produced files can be inspected. setUpModule clears the
whole temp/ tree at the START of every run, so kept sandboxes survive only until
the next run. Because the fixtures tree is gitignored, no sample data can be
committed even if a run fails to clean up.

Stdlib only (unittest + subprocess), matching the project's zero-dependency
philosophy. Run via `python3 -m unittest` or the test/run_tests.sh runner.
"""

import re
import sys
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"

# Private per-test sandbox lives UNDER the (gitignored) fixtures tree, so any
# working copy or produced output is guaranteed never to be committed even if a
# run fails to clean up. Passing tests delete their own sandbox; FAILED tests
# keep theirs for inspection (see _Base.tearDown). setUpModule clears the whole
# tree at the start of every run, so kept sandboxes live only until the next run.
TEMP_ROOT = FIXTURES / "temp"

# Sandboxes of failed tests, kept for inspection and reported by tearDownModule.
_KEPT_SANDBOXES = []

LIB = PROJECT_ROOT / "qfx_convert_lib.py"
VERIFY = PROJECT_ROOT / "qfx_convert_verify.py"
WRAPPER = PROJECT_ROOT / "qfx-convert"

# Import the library directly for the pure-unit tests (import is side-effect
# free: its CLI is guarded by `if __name__ == '__main__'`).
sys.path.insert(0, str(PROJECT_ROOT))
import qfx_convert_lib as lib  # noqa: E402


def setUpModule():
    """Fresh start: clear any sandboxes kept from a previous (failed) run."""
    shutil.rmtree(TEMP_ROOT, ignore_errors=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

# Fixture file names (pristine masters — copied, never used in place).
FX_2025 = "nordstrom_2025_original.qfx"
FX_2026 = "nordstrom_2026_original.qfx"
FX_LEGACY = "nordstrom_2025_converted_legacy.QFX"

# Expected id targets (independent restatement of FID_TARGETS, so the test is
# not merely echoing the module it validates).
ID_NORD = "71411"
ID_CHASE = "10898"


# --- Independent assertion helpers (regex, not the library's extractors) ------
def _one(pat, text):
    m = re.search(pat, text)
    return m.group(1) if m else None

def get_fid(text):
    return _one(r"<FID>(\d+)</FID>", text)

def get_intu(text):
    return _one(r"<INTU\.BID>(\d+)</INTU\.BID>", text)

def get_marker_fid(text):
    return _one(r'<!--\s*QFX-CONVERT\s+fid="([^"]+)"', text)

def has_marker(text):
    return "QFX-CONVERT" in text

def get_amounts(text):
    return [float(x) for x in re.findall(r"<TRNAMT>([^<]+)</TRNAMT>", text)]

def txn_count(text):
    return len(re.findall(r"<STMTTRN>", text))

def get_ledgerbal(text):
    """Signed LEDGERBAL amount as a float (independent of the lib's extractor)."""
    v = _one(r"<LEDGERBAL>\s*<BALAMT>(-?[\d.]+)</BALAMT>", text)
    return float(v) if v is not None else None

def get_availbal(text):
    """Signed AVAILBAL amount as a float (independent of the lib's extractor)."""
    v = _one(r"<AVAILBAL>\s*<BALAMT>(-?[\d.]+)</BALAMT>", text)
    return float(v) if v is not None else None


class _Base(unittest.TestCase):
    """Per-test temp sandbox. Fixtures are copied in; nothing runs in place."""

    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        # Name the sandbox after Class.method so a kept (failed) one is
        # self-identifying; mkdtemp still appends a unique suffix.
        prefix = f"{self.__class__.__name__}.{self._testMethodName}_"
        self.tmp = Path(tempfile.mkdtemp(prefix=prefix, dir=str(TEMP_ROOT)))

    def tearDown(self):
        # Passing tests clean up after themselves; failed/errored tests keep
        # their sandbox so the produced (AFTER) files can be inspected. The
        # kept dir is cleared at the start of the next run by setUpModule.
        if self._test_failed():
            _KEPT_SANDBOXES.append(self.tmp)
        else:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def _test_failed(self):
        """Did THIS test record a failure or error? Works on Python 3.4-3.14."""
        outcome = getattr(self, "_outcome", None)
        if outcome is None:
            return False
        result = getattr(outcome, "result", None)
        if result is not None:  # Python 3.11+: lists accumulate across the run
            for test, _exc in (result.errors + result.failures):
                if test is self or (hasattr(test, "id") and test.id() == self.id()):
                    return True
            return False
        errors = getattr(outcome, "errors", None)  # Python 3.4-3.10: per-test
        return any(exc for _t, exc in errors) if errors else False

    def stage(self, fixture_name, as_name=None):
        """Copy a pristine fixture into the sandbox and return the copy's path.

        Also self-checks that the master is untouched by comparing sizes before
        and after (cheap guard against accidental in-place mutation)."""
        src = FIXTURES / fixture_name
        self.assertTrue(src.is_file(), f"missing fixture: {src}")
        before = src.stat().st_size
        dst = self.tmp / (as_name or fixture_name)
        shutil.copy2(src, dst)
        self.assertEqual(src.stat().st_size, before, "fixture was mutated!")
        return dst

    def read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def run_convert(self, *args, cwd=None):
        cmd = [sys.executable, str(LIB), *map(str, args)]
        return subprocess.run(cmd, cwd=str(cwd or self.tmp),
                              capture_output=True, text=True)

    def run_verify(self, *args, cwd=None):
        cmd = [sys.executable, str(VERIFY), *map(str, args)]
        return subprocess.run(cmd, cwd=str(cwd or self.tmp),
                              capture_output=True, text=True)

    def only_output(self, *subdirs):
        """Return the single produced .QFX under tmp[/subdirs], asserting one."""
        base = self.tmp.joinpath(*subdirs) if subdirs else self.tmp
        produced = list(base.glob("*.QFX"))
        self.assertEqual(len(produced), 1, f"expected 1 output in {base}, got {produced}")
        return produced[0]


class TestLibraryUnit(_Base):
    """Direct tests of the shared library (single source of truth)."""

    def setUp(self):
        super().setUp()
        self.orig_2025 = self.read(FIXTURES / FX_2025)
        self.orig_2026 = self.read(FIXTURES / FX_2026)

    def test_fid_targets_integrity(self):
        self.assertEqual(lib.FID_TARGETS["nord"][0], ID_NORD)
        self.assertEqual(lib.FID_TARGETS["chase"][0], ID_CHASE)
        self.assertIsNone(lib.FID_TARGETS["orig"][0])
        self.assertEqual(lib.DEFAULT_FID, "nord")

    def test_marker_roundtrip_each_fid(self):
        for fid in ("nord", "chase", "orig"):
            out = lib.convert_qfx(self.orig_2025, fid=fid, write_marker=True)
            self.assertEqual(lib.read_marker(out), fid)

    def test_marker_has_no_double_hyphen(self):
        # XML comments may not contain a literal '--'.
        for fid in ("nord", "chase", "orig"):
            self.assertNotIn("--", lib.make_marker(fid).strip("<!->"))

    def test_reconvert_does_not_stack_markers(self):
        once = lib.convert_qfx(self.orig_2025, fid="nord", write_marker=True)
        twice = lib.convert_qfx(once, fid="chase", write_marker=True)
        self.assertEqual(twice.count("QFX-CONVERT"), 1)
        self.assertEqual(lib.read_marker(twice), "chase")

    def test_read_marker_none_on_original(self):
        self.assertIsNone(lib.read_marker(self.orig_2025))

    def test_extract_date_range(self):
        self.assertEqual(lib.extract_date_range(self.orig_2025),
                         ("20250712", "20250901"))

    def test_extract_latest_year(self):
        self.assertEqual(lib.extract_latest_year(self.orig_2025), "2025")
        self.assertEqual(lib.extract_latest_year(self.orig_2026), "2026")

    def test_convert_orig_leaves_ids(self):
        out = lib.convert_qfx(self.orig_2025, fid="orig", write_marker=False)
        self.assertEqual(get_fid(out), get_fid(self.orig_2025))
        self.assertEqual(get_intu(out), get_intu(self.orig_2025))

    def test_convert_nord_sets_both_ids(self):
        out = lib.convert_qfx(self.orig_2025, fid="nord", write_marker=False)
        self.assertEqual(get_fid(out), ID_NORD)
        self.assertEqual(get_intu(out), ID_NORD)

    def test_no_marker_option_suppresses_marker(self):
        out = lib.convert_qfx(self.orig_2025, fid="nord", write_marker=False)
        self.assertFalse(has_marker(out))


class TestConvertCLI(_Base):
    """End-to-end tests of `qfx-convert` params; each checks the AFTER file."""

    def test_default_fid_is_nord(self):
        src = self.stage(FX_2025)
        r = self.run_convert(src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read(self.only_output("2025"))
        self.assertEqual(get_fid(out), ID_NORD)
        self.assertEqual(get_intu(out), ID_NORD)
        self.assertEqual(get_marker_fid(out), "nord")

    def test_fid_nord_explicit(self):
        src = self.stage(FX_2025)
        r = self.run_convert("--fid", "nord", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read(self.only_output("2025"))
        self.assertEqual((get_fid(out), get_intu(out)), (ID_NORD, ID_NORD))
        self.assertEqual(get_marker_fid(out), "nord")

    def test_fid_chase(self):
        src = self.stage(FX_2025)
        r = self.run_convert("--fid", "chase", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read(self.only_output("2025"))
        self.assertEqual((get_fid(out), get_intu(out)), (ID_CHASE, ID_CHASE))
        self.assertEqual(get_marker_fid(out), "chase")

    def test_fid_orig_leaves_ids_unchanged(self):
        src = self.stage(FX_2025)
        before = self.read(src)
        r = self.run_convert("--fid", "orig", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read(self.only_output("2025"))
        self.assertEqual(get_fid(out), get_fid(before))
        self.assertEqual(get_intu(out), get_intu(before))
        self.assertEqual(get_marker_fid(out), "orig")

    def test_no_marker_flag(self):
        src = self.stage(FX_2025)
        r = self.run_convert("--fid", "nord", "--no-marker", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read(self.only_output("2025"))
        self.assertFalse(has_marker(out))          # marker suppressed
        self.assertEqual(get_fid(out), ID_NORD)    # ids still converted

    def test_no_verify_flag(self):
        src = self.stage(FX_2025)
        r = self.run_convert("--fid", "nord", "--no-verify", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Verification skipped", r.stdout)
        self.assertNotIn("VERIFICATION RESULTS", r.stdout)
        # Output is still produced and converted.
        out = self.read(self.only_output("2025"))
        self.assertEqual(get_fid(out), ID_NORD)

    def test_output_dir_flag(self):
        src = self.stage(FX_2025)
        dest = self.tmp / "custom_out"
        r = self.run_convert("-o", dest, src)
        self.assertEqual(r.returncode, 0, r.stderr)
        produced = list(dest.glob("*.QFX"))
        self.assertEqual(len(produced), 1, produced)
        # And nothing leaked into a year dir.
        self.assertFalse((self.tmp / "2025").exists())

    def test_output_file_flag(self):
        src = self.stage(FX_2025)
        r = self.run_convert("-o", self.tmp / "out", "-f", "custom_name.QFX", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "out" / "custom_name.QFX").is_file())

    def test_auto_filename_from_dates(self):
        src = self.stage(FX_2025)
        r = self.run_convert(src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.only_output("2025")
        self.assertEqual(out.name, "20250712-20250901_transactions.QFX")

    def test_auto_year_directory(self):
        src = self.stage(FX_2025)
        r = self.run_convert(src)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "2025").is_dir())

    def test_amounts_and_count_preserved(self):
        src = self.stage(FX_2025)
        before = self.read(src)
        r = self.run_convert("--fid", "nord", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.read(self.only_output("2025"))
        self.assertEqual(txn_count(out), txn_count(before))
        self.assertEqual(get_amounts(out), get_amounts(before))

    def test_missing_input_exits_1(self):
        r = self.run_convert(self.tmp / "does_not_exist.qfx")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not found", r.stderr)

    def test_invalid_fid_exits_2(self):
        src = self.stage(FX_2025)
        r = self.run_convert("--fid", "bogus", src)
        self.assertEqual(r.returncode, 2)  # argparse usage error

    def test_2026_fixture_end_to_end(self):
        src = self.stage(FX_2026)
        before = self.read(src)
        r = self.run_convert("--fid", "nord", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "2026").is_dir())
        out = self.read(self.only_output("2026"))
        self.assertEqual((get_fid(out), get_intu(out)), (ID_NORD, ID_NORD))
        self.assertEqual(get_marker_fid(out), "nord")
        self.assertEqual(txn_count(out), txn_count(before))
        self.assertEqual(get_amounts(out), get_amounts(before))


class TestVerifyCLI(_Base):
    """Tests of the standalone `qfx-convert-verify` (shared logic import)."""

    def _make_converted(self, fid, no_marker=False):
        """Stage the 2025 original, convert it, return (original, converted)."""
        src = self.stage(FX_2025)
        args = ["--fid", fid]
        if no_marker:
            args.append("--no-marker")
        args.append(str(src))
        r = self.run_convert(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return src, self.only_output("2025")

    def test_verify_marker_driven_pass(self):
        orig, conv = self._make_converted("nord")
        r = self.run_verify(orig, conv)             # no --fid: read the marker
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("file marker", r.stdout)
        self.assertIn("SUCCESS", r.stdout)

    def test_verify_fid_agrees_with_marker(self):
        orig, conv = self._make_converted("chase")
        r = self.run_verify("--fid", "chase", orig, conv)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SUCCESS", r.stdout)

    def test_verify_fid_contradicts_marker_exits_2(self):
        orig, conv = self._make_converted("nord")
        r = self.run_verify("--fid", "chase", orig, conv)
        self.assertEqual(r.returncode, 2)
        self.assertIn("contradicts", r.stderr)

    def test_verify_no_marker_falls_back_to_default(self):
        # chase ids but no marker -> default expectation (nord) mismatches -> fail
        orig, conv = self._make_converted("chase", no_marker=True)
        r = self.run_verify(orig, conv)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no marker found", r.stdout)

    def test_verify_no_marker_with_explicit_fid_pass(self):
        # same file, but assert the correct id explicitly -> passes
        orig, conv = self._make_converted("chase", no_marker=True)
        r = self.run_verify("--fid", "chase", orig, conv)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SUCCESS", r.stdout)

    def test_verify_legacy_fixture_orig_path(self):
        # Legacy converted sample (no marker). Compared to itself under --fid
        # orig, the 'ids unchanged' rule holds -> exercises no-marker legacy file.
        conv = self.stage(FX_LEGACY)
        r = self.run_verify("--fid", "orig", conv, conv)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SUCCESS", r.stdout)


class TestWrapperScript(_Base):
    """Smoke test of the shipped `qfx-convert` shell wrapper (python detection)."""

    def test_wrapper_runs_end_to_end(self):
        if shutil.which("sh") is None:
            self.skipTest("sh not available")
        src = self.stage(FX_2025)
        r = subprocess.run(["sh", str(WRAPPER), str(src), "-o", str(self.tmp / "w")],
                           cwd=str(self.tmp), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        produced = list((self.tmp / "w").glob("*.QFX"))
        self.assertEqual(len(produced), 1, produced)
        self.assertEqual(get_fid(self.read(produced[0])), ID_NORD)


# ============================================================================
# GROUP: institutions
# ----------------------------------------------------------------------------
# Per-institution-id DATA transforms that go beyond the FID/INTU.BID rewrite,
# keyed to --fid via lib.FID_BALANCE_FLIPS. Each id that triggers a transform
# gets its own sub-group class below; add future ids (e.g. chase) as sibling
# _InstitutionCase subclasses following the same pattern.
#
#   sub-group nord (71411): flips the LEDGERBAL sign (pos<->neg), magnitude
#       preserved; AVAILBAL and every transaction <TRNAMT> left untouched.
# ============================================================================

class _InstitutionCase(_Base):
    """Shared scaffolding for the institutions group.

    Subclasses set INST_FID; convert_fixture() stages a pristine fixture, runs
    the CLI under that --fid, and returns (before_text, after_text) so sub-group
    tests can assert on the institution-specific transform.
    """

    INST_FID = None  # set by each sub-group

    def convert_fixture(self, fixture_name, year):
        src = self.stage(fixture_name)
        before = self.read(src)
        r = self.run_convert("--fid", self.INST_FID, src)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = self.read(self.only_output(year))
        return before, after


class TestInstitutionNord(_InstitutionCase):
    """SUB-GROUP: id 'nord' (71411).

    Expected transform: the online LEDGERBAL sign is flipped (Quicken imports
    the Nordstrom Web Connect balance with the wrong sign, so pre-flipping
    compensates); AVAILBAL and transaction amounts are preserved exactly.
    """

    INST_FID = "nord"

    def test_fid_registered_for_ledgerbal_flip(self):
        # Independent restatement of the policy this sub-group validates.
        self.assertIn("LEDGERBAL", lib.FID_BALANCE_FLIPS["nord"])
        self.assertNotIn("AVAILBAL", lib.FID_BALANCE_FLIPS["nord"])

    def test_ledgerbal_flipped_neg_to_pos(self):
        # 2025 fixture carries a NEGATIVE ledger balance (-3768.18).
        before, after = self.convert_fixture(FX_2025, "2025")
        self.assertLess(get_ledgerbal(before), 0)                       # precondition
        self.assertAlmostEqual(get_ledgerbal(after), -get_ledgerbal(before), places=2)
        self.assertGreater(get_ledgerbal(after), 0)                     # now positive

    def test_ledgerbal_flipped_pos_to_neg(self):
        # 2026 fixture carries a POSITIVE ledger balance (4369.11).
        before, after = self.convert_fixture(FX_2026, "2026")
        self.assertGreater(get_ledgerbal(before), 0)                    # precondition
        self.assertAlmostEqual(get_ledgerbal(after), -get_ledgerbal(before), places=2)
        self.assertLess(get_ledgerbal(after), 0)                        # now negative

    def test_availbal_not_flipped(self):
        before, after = self.convert_fixture(FX_2025, "2025")
        self.assertAlmostEqual(get_availbal(after), get_availbal(before), places=2)

    def test_transaction_amounts_not_flipped(self):
        # The flip must not bleed into <TRNAMT>, which also holds signed amounts.
        before, after = self.convert_fixture(FX_2025, "2025")
        self.assertEqual(get_amounts(after), get_amounts(before))

    def test_verify_reports_ledgerbal_flip(self):
        # The shared verifier's balance section marks LEDGERBAL as a passing
        # 'flip' and reports overall SUCCESS for a nord conversion.
        src = self.stage(FX_2025)
        r = self.run_convert("--fid", "nord", src)
        self.assertEqual(r.returncode, 0, r.stderr)
        conv = self.only_output("2025")
        v = self.run_verify(src, conv)                  # marker-driven (nord)
        self.assertEqual(v.returncode, 0, v.stderr)
        self.assertIn("SUCCESS", v.stdout)
        self.assertIn("LEDGERBAL", v.stdout)
        self.assertIn("flip", v.stdout)

    def test_verify_balance_check_is_not_vacuous(self):
        # Take a correct nord conversion, then revert ONLY the ledger sign so
        # ids/marker stay valid but the balance is wrong. Verification must fail,
        # proving the balance rule is enforced independently (not vacuous).
        before = self.read(FIXTURES / FX_2025)
        good = lib.convert_qfx(before, fid="nord", write_marker=True)
        bad = re.sub(r"(<LEDGERBAL>\s*<BALAMT>)(-?)([\d.]+)",
                     lambda m: m.group(1) + ("" if m.group(2) else "-") + m.group(3),
                     good)
        self.assertNotEqual(get_ledgerbal(bad), get_ledgerbal(good))    # sign reverted
        self.assertFalse(
            lib.verify_conversion(before, bad, fid="nord", show_details=False))


class TestFixtureIntegrity(unittest.TestCase):
    """Guards that the pristine masters exist and are what the suite assumes."""

    def test_fixtures_present_and_unconverted(self):
        for name in (FX_2025, FX_2026, FX_LEGACY):
            self.assertTrue((FIXTURES / name).is_file(), name)
        for name in (FX_2025, FX_2026):
            text = (FIXTURES / name).read_text(encoding="utf-8")
            self.assertNotIn("QFX-CONVERT", text)   # originals carry no marker
            self.assertEqual(get_fid(text), "12139")  # Nordstrom source id


def tearDownModule():
    """Report kept sandboxes; on a fully clean run, remove the temp tree."""
    if _KEPT_SANDBOXES:
        sys.stderr.write(
            "\n%d failed-test sandbox(es) kept for inspection "
            "(cleared at the start of the next run):\n" % len(_KEPT_SANDBOXES))
        for p in _KEPT_SANDBOXES:
            sys.stderr.write("  %s\n" % p)
    else:
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
