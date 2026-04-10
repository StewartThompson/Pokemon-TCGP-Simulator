# Phase 4 Group F: Game Runner + Decks

**Date:** 2026-04-09
**Branch:** engine-rebuild
**Tests:** 277 passing (254 pre-existing + 8 new + 15 from agents group)

---

## Overview

Phase 4 Group F implements the game runner and sample decks, completing the core simulation loop. The runner orchestrates full games between two agents from first turn through to win-condition resolution, handling all phase transitions, KO promotions, and between-turn status effects.

---

## Files Created

### `ptcgp/runner/game_runner.py`

Core game loop function `run_game(agent1, agent2, deck1, deck2, energy_types1, energy_types2, seed, max_steps)`.

Key design decisions:
- **No dependency on `ptcgp.agents`** — agents are duck-typed. Any object with `choose_action(state, legal) -> Action` works. Optional callbacks: `choose_promotion`, `on_game_start`, `on_game_end`.
- **Phase-aware loop** — handles `AWAITING_BENCH_PROMOTION` as a special case, correctly routing to the promoting player (the one whose active is `None`).
- **Turn transition ownership** — the runner owns all `resolve_between_turns → end_turn → start_turn` sequencing after ATTACK or END_TURN actions, as documented in `mutations.py`.
- **Safety valve** — `max_steps=10_000` prevents infinite loops in degenerate game states.
- Returns `(GameState, winner)` where winner is `0`, `1`, `-1` (tie), or `None` if aborted.

### `ptcgp/decks/sample_decks.py`

Two pre-built 20-card decks validated against the deck validator:

**GRASS_DECK** — Bulbasaur/Ivysaur/Venusaur ex + Weedle/Kakuna/Beedrill + Petilil/Lilligant + Potion/Professor's Research
- Note: Caterpie (a1-005) was excluded because its `search_deck_grass_pokemon` effect is not yet implemented. The Weedle line was substituted.

**FIRE_DECK** — Charmander/Charizard ex + Vulpix/Ninetales + Weedle/Kakuna/Beedrill + Poke Ball/Potion/Giant Cape

Both decks pass `validate_deck()` with no errors.

Also exports `get_sample_deck(name: str) -> tuple[list[str], list[Element]]`.

### `tests/runner/test_game_runner.py`

8 tests covering:
- `test_single_game_completes` — game finishes, winner is valid
- `test_winner_is_valid` — winner is in `{0, 1, -1}`
- `test_100_games_all_complete` — 100 seeds, all finish, all valid winners
- `test_game_returns_final_state` — returned state is `GameState`
- `test_seeded_reproducible` — same seed → same winner
- `test_both_decks_work` — grass vs fire completes
- `test_agent_callbacks_called` — `on_game_start` and `on_game_end` are invoked
- `test_grass_vs_grass` — mirror match completes

**Implementation note:** Tests use an inline `InlineRandomAgent` class (no import from `ptcgp.agents`) and an autouse session fixture to load the card database, avoiding the infinite-loop failure mode caused by `_draw_opening_hand` retrying forever when the database is empty.

---

## Key Implementation Notes

### Bench Promotion Phase Handling

When the active Pokemon is KO'd mid-turn, `apply_action` on ATTACK transitions the state to `AWAITING_BENCH_PROMOTION`. The runner:
1. Detects the phase at the top of the loop
2. Identifies the promoting player (`active is None`)
3. Routes promotion to the correct agent
4. After promotion, if the game continues (phase returns to MAIN), completes the turn sequence

### Card Validation Finding

During deck construction, `a1-005` (Caterpie) was found to have an unimplemented effect (`search_deck_grass_pokemon` — "Put 1 random Grass Pokémon from your deck into your hand"). This effect was not yet registered in the effects registry despite Phase 3b being described as complete. The Weedle line (a1-008/009/010) was used instead.

---

## Test Results

```
277 passed in 1.83s
```

All 254 pre-existing tests continue to pass alongside 8 new runner tests and 15 agent tests added by Group E.
