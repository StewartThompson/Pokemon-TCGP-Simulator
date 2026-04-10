# Task: Phase 1 — Foundation
Status: Complete
Date: 2026-04-09

## Files Created
- `ptcgp/cards/types.py` — Element (8 types), CostSymbol (8+Colorless), Stage, CardKind enums
- `ptcgp/engine/constants.py` — DECK_SIZE, BENCH_SIZE, POINTS_TO_WIN, WEAKNESS_CHART, MAX_TURNS=60
- `ptcgp/cards/attack.py` — Attack, Ability frozen dataclasses
- `ptcgp/cards/card.py` — Card frozen dataclass with ko_points property
- `ptcgp/engine/state.py` — GameState, PlayerState, PokemonSlot, StatusEffect, GamePhase
- `ptcgp/engine/actions.py` — ActionKind, Action, SlotRef
- `ptcgp/cards/loader.py` — JSON → Card (handles attacks, abilities, trainer effects)
- `ptcgp/cards/database.py` — Module-level card DB with register/get/clear/load_defaults

## Tests
- `tests/cards/test_loader.py`: 12 tests — all pass
- `tests/cards/test_database.py`: 7 tests — all pass
- Total: 19/19 passed
