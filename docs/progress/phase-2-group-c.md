# Phase 2 Group C: Combat & Abilities

Status: Complete

## Files Created

### Engine Modules
- `ptcgp/engine/slot_utils.py` — already existed (no changes made)
- `ptcgp/engine/attack.py` — `can_pay_cost()` and `execute_attack()` with weakness, confusion, and energy validation
- `ptcgp/engine/abilities.py` — `use_ability()` marks non-passive ability as used this turn
- `ptcgp/engine/status.py` — `apply_status()` enforces active-only rule, supports all 5 stacking effects
- `ptcgp/engine/ko.py` — `handle_ko()`, `promote_bench()`, `check_winner()` with full win condition logic

### Tests
- `tests/engine/test_attack.py` — 14 tests
- `tests/engine/test_status.py` — 10 tests
- `tests/engine/test_ko.py` — 17 tests

## Test Results

41 new tests, all passing. Full suite: 147 passed.

## Key Implementation Notes

- `can_pay_cost`: counts typed requirements first, then checks if remaining energy covers Colorless demand
- `execute_attack`: confusion tails returns state unchanged (no self-damage per PTCGP rules); energy is never consumed by attacking
- `apply_status`: only allows targeting active slot (ref.slot == -1); all 5 statuses stack freely
- `handle_ko`: awards points to `1 - ko_ref.player`; checks simultaneous KO tie when both players reach POINTS_TO_WIN; Mega EX KO (3 pts) triggers instant win; no-bench KO triggers immediate GAME_OVER
- `check_winner`: checks `state.winner`, then point thresholds, then no-Pokemon condition, then turn limit (MAX_TURNS = 60)
