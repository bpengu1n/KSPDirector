"""
tests/test_isolation.py
========================
Meta-test that verifies tests are order-independent.

Runs test suites in three orders — natural, reversed, and random —
each in a subprocess. All three must produce 0 failures. This catches any
test that leaks state to (or depends on state from) another test.

Requires: pytest-randomly, pytest-reverse
Playwright tests additionally require: playwright + Chromium
"""

import os
import subprocess
import sys

import pytest


_TESTS_DIR = os.path.dirname(__file__)
PLAYWRIGHT_FILE = os.path.join(_TESTS_DIR, "test_ui_playwright.py")
_NON_UI_FILES = [
    os.path.join(_TESTS_DIR, f) for f in [
        "test_p0_regressions.py",
        "test_p1_regressions.py",
        "test_p2_p3_regressions.py",
        "test_scenario.py",
        "test_ballistic_projection.py",
    ]
]
_BASE_CMD = [sys.executable, "-m", "pytest", "-x", "--tb=short", "-q"]


def _run_tests(extra_args, timeout=300):
    result = subprocess.run(
        _BASE_CMD + extra_args,
        capture_output=True, text=True, timeout=timeout,
    )
    return result


def _assert_all_passed(result, label):
    assert result.returncode == 0, (
        f"Tests failed in {label} order (rc={result.returncode}).\n"
        f"stdout:\n{result.stdout[-2000:]}\n"
        f"stderr:\n{result.stderr[-1000:]}"
    )


# ---------------------------------------------------------------------------
# Playwright UI tests (require browser)
# ---------------------------------------------------------------------------

def test_ui_natural_order():
    """Run Playwright tests in file-declaration order."""
    r = _run_tests(["-p", "no:randomly", PLAYWRIGHT_FILE])
    _assert_all_passed(r, "UI natural")


def test_ui_reversed_order():
    """Run Playwright tests in reverse file-declaration order."""
    r = _run_tests(["-p", "no:randomly", "--reverse", PLAYWRIGHT_FILE])
    _assert_all_passed(r, "UI reversed")


def test_ui_random_order():
    """Run Playwright tests in a random order (pytest-randomly)."""
    r = _run_tests([PLAYWRIGHT_FILE])
    _assert_all_passed(r, "UI random")


# ---------------------------------------------------------------------------
# Non-UI tests (no browser needed)
# ---------------------------------------------------------------------------

def test_nonui_natural_order():
    """Run non-UI tests in file-declaration order."""
    r = _run_tests(["-p", "no:randomly"] + _NON_UI_FILES, timeout=180)
    _assert_all_passed(r, "non-UI natural")


def test_nonui_reversed_order():
    """Run non-UI tests in reverse file-declaration order."""
    r = _run_tests(["-p", "no:randomly", "--reverse"] + _NON_UI_FILES, timeout=180)
    _assert_all_passed(r, "non-UI reversed")


def test_nonui_random_order():
    """Run non-UI tests in a random order (pytest-randomly)."""
    r = _run_tests(_NON_UI_FILES, timeout=180)
    _assert_all_passed(r, "non-UI random")
