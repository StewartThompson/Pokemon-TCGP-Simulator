# Phase 3b — All 16 Card Effects Implemented

## Summary

Implemented all 16 card effect handlers from a1-genetic-apex, increasing the test suite from 215 to 254 passing tests.

## New Effect Modules

| File | Handlers |
|------|----------|
| `ptcgp/effects/heal.py` | `heal_self`, `heal_all_own`, `heal_target`, `heal_grass_target` |
| `ptcgp/effects/draw.py` | `draw_cards`, `draw_basic_pokemon` |
| `ptcgp/effects/energy_effects.py` | `attach_energy_zone_self`, `attach_energy_zone_bench`, `discard_energy_self` |
| `ptcgp/effects/coin_flip.py` | `cant_attack_next_turn` |
| `ptcgp/effects/movement.py` | `switch_opponent_active` |
| `ptcgp/effects/tool_effects.py` | `hp_bonus` |
| `ptcgp/effects/items.py` | `rare_candy_evolve` |

Total: 13 registered handlers covering all 16 card effects (some handlers cover multiple cards).

## Updated Files

- `ptcgp/effects/__init__.py` — imports all new modules to trigger `@register_effect` decorators
- `docs/CARD_EFFECTS.md` — all 16 effect rows updated from ❌ to ✅

## New Test Files

| File | Tests |
|------|-------|
| `tests/effects/test_heal.py` | 12 tests — heal_self, heal_all_own, heal_target, heal_grass_target |
| `tests/effects/test_draw.py` | 8 tests — draw_cards, draw_basic_pokemon |
| `tests/effects/test_energy_effects.py` | 9 tests — attach_energy_zone_self/bench, discard_energy_self |
| `tests/effects/test_status_effects.py` | 4 tests — cant_attack_next_turn (heads/tails/edge cases) |
| `tests/effects/test_movement.py` | 4 tests — switch_opponent_active |

## Implementation Notes

- **heal_all_own**: Heals all own Pokemon (active + non-None bench slots) up to their respective max_hp. Used by Butterfree's Powder Heal ability.
- **cant_attack_next_turn**: Coin flip is handled inside the effect handler (not in execute_attack). Heads → sets `cant_attack_next_turn=True` on opponent's active.
- **draw_basic_pokemon**: Uses `state.rng.sample()` to randomly select from Basic Pokemon in the deck. No error if deck is empty or has no basics.
- **attach_energy_zone_bench**: Attaches exactly 1 energy to the `target_ref` bench slot. Target selection (valid Grass Pokemon) is enforced by the caller/legal_actions.
- **rare_candy_evolve**: Bypasses the Stage 1 requirement; damage is preserved across evolution; status conditions are cleared (standard PTCGP rule).
- **switch_opponent_active**: Uses `state.rng.choice()` for random bench selection in bot play. UI/human play would need to prompt.
- **hp_bonus**: Increases both `max_hp` and `current_hp` by `amount` when attached (matches PTCGP behaviour for Giant Cape).

## Test Count

- Before: 215 passing
- After: 254 passing (+39)
