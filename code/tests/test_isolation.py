"""
tests/test_isolation.py
========================
Meta-test that verifies Playwright UI tests are order-independent.

Runs test_ui_playwright.py in three orders — natural, reversed, and random —
each in a subprocess. All three must produce 0 failures. This catches any
test that leaks state to (or depends on state from) another test.

Requires: playwright, pytest-randomly
"""

import os
import subprocess
import sys

import pytest


PLAYWRIGHT_FILE = os.path.join(os.path.dirname(__file__), "test_ui_playwright.py")
_BASE_CMD = [sys.executable, "-m", "pytest", "-x", "--tb=short", "-q"]


def _run_tests(extra_args):
    result = subprocess.run(
        _BASE_CMD + extra_args,
        capture_output=True, text=True, timeout=300,
    )
    return result


def _assert_all_passed(result, label):
    assert result.returncode == 0, (
        f"Tests failed in {label} order (rc={result.returncode}).\n"
        f"stdout:\n{result.stdout[-2000:]}\n"
        f"stderr:\n{result.stderr[-1000:]}"
    )


def test_natural_order():
    """Run Playwright tests in file-declaration order."""
    r = _run_tests(["-p", "no:randomly", PLAYWRIGHT_FILE])
    _assert_all_passed(r, "natural")


def test_reversed_order():
    """Run Playwright tests in reverse file-declaration order."""
    r = _run_tests(["-p", "no:randomly", "--reverse", PLAYWRIGHT_FILE])
    _assert_all_passed(r, "reversed")


def test_random_order():
    """Run Playwright tests in a random order (pytest-randomly)."""
    r = _run_tests([PLAYWRIGHT_FILE])
    _assert_all_passed(r, "random")
