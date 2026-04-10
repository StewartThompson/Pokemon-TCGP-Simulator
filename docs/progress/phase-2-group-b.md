## Phase 2 Group B: Movement Actions

Status: Complete

### Files Created

**Engine modules:**
- `ptcgp/engine/slot_utils.py` — `get_slot` / `set_slot` copy-on-write primitives for resolving `SlotRef` to `PokemonSlot`
- `ptcgp/engine/play_card.py` — `play_basic`, `play_item`, `play_supporter`, `attach_tool`
- `ptcgp/engine/energy.py` — `attach_energy` (Energy Zone → Pokemon)
- `ptcgp/engine/evolve.py` — `evolve_pokemon` (Stage 1 / Stage 2 with full validation)
- `ptcgp/engine/retreat.py` — `retreat` (active ↔ bench swap, random energy discard)

**Test files:**
- `tests/engine/test_play_card.py` — 16 tests
- `tests/engine/test_energy.py` — 8 tests
- `tests/engine/test_evolve.py` — 15 tests
- `tests/engine/test_retreat.py` — 11 tests

### Test Results

50 / 50 passed (0 failed)

### Key Implementation Notes

- All functions follow copy-on-write: `state = state.copy()` before any mutation
- `slot_utils.py` provides the shared `get_slot` / `set_slot` primitives imported by other modules
- Retreat energy discard uses `state.rng.sample(energy_list, retreat_cost)` for deterministic randomness
- Evolution correctly carries over `attached_energy`, `tool_card_id`, and `turns_in_play`; clears `status_effects` and sets `evolved_this_turn = True`
- First-turn evolution block uses `state.is_first_turn()` logic: blocked on turn 0 and on turn 1 for the second player
