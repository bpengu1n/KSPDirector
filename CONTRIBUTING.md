# Contributing to Perseus 1 KSP Mission Pack

Thanks for your interest in contributing! This guide covers everything you
need to get started.

## Prerequisites

- Python 3.10+
- Git

## Setup

```bash
git clone https://github.com/bpengu1n/KSPDirector.git
cd KSPDirector/code
pip install -r requirements.txt
pip install pytest pytest-randomly pytest-reverse
```

For UI tests, you also need Playwright with Chromium:

```bash
pip install playwright
playwright install chromium
```

## Running tests

All tests must pass before submitting a PR.

```bash
cd code

# Full suite (requires Playwright + Chromium for UI tests)
python -m pytest tests/ -v

# Non-browser tests only (matches CI)
python -m pytest tests/ -v \
    --ignore=tests/test_ui_playwright.py \
    --ignore=tests/test_isolation.py

# Verify UI test isolation (runs Playwright tests in 3 orderings)
python -m pytest tests/test_isolation.py -v

# With coverage report
python -m pytest tests/ --cov=sim --cov=mission_control --cov-report=term-missing
```

### Test files

| File | Tests | Scope |
|---|---|---|
| `test_p0_regressions.py` | 17 | Critical bug regressions |
| `test_p1_regressions.py` | 11 | High-priority issue regressions |
| `test_p2_p3_regressions.py` | 21 | Medium/low priority regressions |
| `test_scenario.py` | 188 | Scenario system + integration |
| `test_ballistic_projection.py` | 33 | Ballistic projection + drag |
| `test_ui_playwright.py` | 230 | DOM-based UI tests (headless Chromium) |
| `test_isolation.py` | 3 | Meta-test for UI test order independence |

### Test isolation

Every Playwright UI test is fully atomic — an autouse `reset_ui` fixture
resets all mutable JS state and DOM elements before each test. Tests pass
in any execution order (natural, reversed, or random). The `test_isolation.py`
meta-test enforces this.

When writing new Playwright tests that mutate page state, you do **not** need
to clean up after yourself — the fixture handles it. Just write the test as
if it runs on a fresh page load.

## CI

GitHub Actions runs the non-browser test suite on every push and PR to `main`
across Python 3.10, 3.11, and 3.12. All three must pass before merging.

Playwright and isolation tests are excluded from CI (no browser available).
Run them locally before submitting.

## Making changes

### Branch workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run the full test suite locally
4. Commit with a clear message describing *why*, not just *what*
5. Open a PR against `main`

### Code style

- No comments unless the *why* is non-obvious
- No unnecessary abstractions — three similar lines beat a premature helper
- Follow existing patterns in the file you're editing

### Adding tests

- **Bug fix?** Write the test first (red), then fix (green)
- **New feature?** Include tests covering the happy path and edge cases
- **Regression tests** follow the `test_pNNN_description` naming pattern
- Use `pytest.mark.parametrize` for data-driven tests
- Use `pytest.approx()` for float comparisons
- Use shared fixtures from `conftest.py` (`vehicle_config`,
  `terrier_ignition_state`, `telemetry_state`) instead of building state dicts
  inline

### Simulation changes

If you change any part mass, engine stat, or physics parameter:

1. Update the source of truth in `sim/constants.py`
2. Re-run `python -m sim.ascent_sim` and verify numbers
3. Update the verified numbers table in `CLAUDE.md`
4. Run `python tools/update_sheet3_trajectory.py` to regenerate diagram data

### Diagram changes

After modifying any diagram generator:

```bash
python diagrams/generate_diagrams.py
python -c "
import xml.dom.minidom as m
for f in ['sheet1','sheet2','sheet3','sheet4']:
    m.parse(f'{f}.svg'); print(f'{f}: valid')
"
```

### CHANGELOG

Update `CHANGELOG.md` under `[Unreleased]` with every PR. Use the appropriate
section (Added, Changed, Fixed). Keep entries concise and specific.

## Architecture overview

```
sim/                  Pure Python ascent simulator (no external deps)
mission_control/      Flask + Socket.IO server, Telemachus client, flight director
diagrams/             SVG technical reference sheet generators
tests/                pytest suite + Playwright UI tests
```

Key design decisions are documented in `CLAUDE.md` under "Settled vehicle
design" — read those sections before modifying related code.

## Questions?

Open an issue for questions, bug reports, or feature proposals.
