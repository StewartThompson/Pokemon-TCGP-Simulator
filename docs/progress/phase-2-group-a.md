# Phase 2 Group A — Setup & Turn Flow

**Status: Complete**

## Files Created

| File | Description |
|------|-------------|
| `ptcgp/engine/setup.py` | `create_game`, `start_game`, `_draw_opening_hand`, `_place_starting_pokemon` |
| `ptcgp/engine/turn.py` | `start_turn`, `end_turn` |
| `ptcgp/engine/checkup.py` | `resolve_between_turns` |
| `tests/engine/test_setup.py` | 11 tests for game creation and setup |
| `tests/engine/test_turn.py` | 14 tests for turn management |
| `tests/engine/test_checkup.py` | 12 tests for between-turns status resolution |

## Test Results

37 / 37 tests passing.

```
tests/engine/test_setup.py   11 passed
tests/engine/test_turn.py    14 passed
tests/engine/test_checkup.py 12 passed
```

## Key Implementation Notes

- `create_game` initializes decks and energy types but does NOT shuffle (left to `start_game`)
- `_draw_opening_hand` retries until at least one Basic Pokemon is in hand
- `start_game` initialises `turn_number = -1` before calling `start_turn` so the first increment lands on `0`
- `start_turn` with `turn_number == 0` skips draw and energy generation (first player rule)
- `resolve_between_turns` operates on `state.current` (called BEFORE `end_turn` switches player)
- BURNED applies damage then coin-flips for cure; PARALYZED auto-cures; ASLEEP coin-flips; CONFUSED has no checkup effect
- KO'd HP clamped to 0; full KO handling deferred to Group C
