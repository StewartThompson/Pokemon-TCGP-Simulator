# Phase 2 Group D: Legal Actions + Dispatcher

## Status: Complete

All 42 new tests pass. Total test count: 189 (147 pre-existing + 42 new).

## Files Created

### `ptcgp/engine/legal_actions.py`
Implements `get_legal_actions(state)` and `get_legal_promotions(state, player_index)`.

`get_legal_actions` enumerates all legal moves for the current player when `state.phase == MAIN`:
- PLAY_CARD: basics to empty bench slots; items; supporters (blocked if already played); tools to pokemon without tools
- ATTACH_ENERGY: to active and bench pokemon when energy is available and not yet attached
- EVOLVE: stage 1/2 cards from hand to valid targets (turn_number >= 2, turns_in_play >= 1, not evolved_this_turn)
- USE_ABILITY: non-passive abilities not yet used this turn
- RETREAT: when not already retreated, not paralyzed/asleep, enough energy for retreat cost, and bench exists
- ATTACK: when turn_number >= 2, not cant_attack_next_turn, not paralyzed/asleep, can pay cost
- END_TURN: always available

`get_legal_promotions` returns PROMOTE actions for a player during AWAITING_BENCH_PROMOTION.

### `ptcgp/engine/mutations.py`
Implements `apply_action(state, action)` dispatching each ActionKind to the appropriate engine function:
- PLAY_CARD: routes to play_basic / play_item / play_supporter / attach_tool based on card kind and stage
- ATTACH_ENERGY: delegates to energy.attach_energy
- EVOLVE: delegates to evolve.evolve_pokemon
- USE_ABILITY: delegates to abilities.use_ability
- RETREAT: delegates to retreat.retreat (bench_slot int, not SlotRef)
- ATTACK: delegates to attack.execute_attack, then calls handle_ko for opponent active and current player active if HP <= 0
- END_TURN: no-op (runner handles turn transitions)
- PROMOTE: delegates to ko.promote_bench

### `ptcgp/engine/__init__.py`
Updated to export the full public API: GameState, PlayerState, PokemonSlot, StatusEffect, GamePhase, Action, ActionKind, SlotRef, create_game, start_game, get_legal_actions, get_legal_promotions, apply_action, check_winner, start_turn, end_turn, resolve_between_turns.

### `tests/engine/test_legal_actions.py`
37 tests covering:
- Phase guards (SETUP, AWAITING_BENCH_PROMOTION, GAME_OVER, winner set)
- END_TURN always present
- PLAY_CARD: basics to bench, full bench blocking, multiple slots, items, supporters, second-supporter blocking
- ATTACH_ENERGY: to active, to bench, blocked when attached/no energy
- EVOLVE: legal on turn 2+, blocked on turn 0/1, requires turns_in_play >= 1, blocked if evolved_this_turn
- ATTACK: blocked turns 0/1, legal turn 2+, blocked by PARALYZED/ASLEEP/cant_attack_next_turn/insufficient energy
- RETREAT: legal, blocked by PARALYZED/ASLEEP/no bench/already retreated/insufficient energy
- get_legal_promotions: returns bench slots, handles empty bench, wrong phase

### `tests/engine/test_full_game.py`
5 tests running end-to-end Random vs Random games:
- Single game completes (seed=42)
- Winner is valid (0, 1, or -1)
- Ten games all complete (seeds 0-9)
- Game finishes within MAX_STEPS (10000)
- Seeds 10-19 run without exception

## Test Counts

| File | Tests |
|------|-------|
| test_legal_actions.py | 37 |
| test_full_game.py | 5 |
| **New total** | **42** |
| Pre-existing | 147 |
| **Grand total** | **189** |
