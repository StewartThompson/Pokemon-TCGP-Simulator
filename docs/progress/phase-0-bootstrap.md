# Task: Phase 0 — Bootstrap
Status: Complete
Date: 2026-04-09

## Files Created
- `pyproject.toml` — Python 3.13, deps: click, rich, numpy, pytest
- `.gitignore` — updated with standard exclusions
- `ptcgp/__init__.py` + all subpackage `__init__.py` files (cards, engine, effects, agents, ui, runner, decks, ml)
- `tests/__init__.py` + all test subpackage `__init__.py` files
- `tests/conftest.py` — shared fixture stubs
- `docs/ARCHITECTURE.md` — layer diagram + key design principles
- `docs/CARD_EFFECTS.md` — 16 effects in a1-genetic-apex, all ❌ Not implemented
- `docs/progress/` — this directory

## RULES.md Corrections Applied
1. §5 Retreating: "player chooses energy" → "energy discarded at random"
2. §2 Components: added Energy Types section clarifying Colorless is only a cost specifier; 8 real types listed
3. §10 Bench Promotion: removed duplicate spread damage bullet
4. §11 Card-Specific Rules: removed duplicate Supporters/Items sections

## Tests
- `pytest` runs with 0 tests, exit code 5 (expected — no tests yet)
- `import ptcgp` succeeds

## Notes
- Using Python 3.13 venv at `.venv/`
- pyproject.toml uses `setuptools.build_meta` backend (not the legacy variant)
