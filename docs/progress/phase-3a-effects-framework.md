# Phase 3a: Effects Framework

**Date:** 2026-04-09
**Branch:** engine-rebuild
**Tests:** 26 new tests added, 215 total passing (up from 189)

---

## Summary

Implemented the Effects Framework foundation — the infrastructure that will enable Phase 3b to wire up actual game-logic handlers for each card effect.

---

## Files Created

| File | Purpose |
|------|---------|
| `ptcgp/effects/base.py` | `Effect` and `UnknownEffect` frozen dataclasses |
| `ptcgp/effects/registry.py` | `EffectContext`, `@register_effect` decorator, `resolve_effect` dispatcher |
| `ptcgp/effects/parser.py` | Pattern-based text → `Effect` parser for all 16 Phase 3b effects |
| `ptcgp/effects/__init__.py` | Ensures registry module is initialized on import |
| `ptcgp/decks/validator.py` | `validate_deck()`, `is_card_fully_implemented()`, `get_unimplemented_cards()` |
| `tests/effects/test_parser.py` | 19 parser tests |
| `tests/effects/test_registry.py` | 7 registry tests |

---

## Design Decisions

### Effect Dataclass (`base.py`)
- Frozen dataclasses for immutability — Effects are value objects, not entities.
- `UnknownEffect` extends `Effect` with a `raw_text` field to preserve original text for debugging.
- `params: dict[str, Any]` is flexible — avoids needing a subclass per effect type.

### Registry (`registry.py`)
- `_REGISTRY` is a module-level dict, so `@register_effect('name')` decorators in Phase 3b handlers register themselves on import.
- `resolve_effect` returns the (possibly mutated) `GameState` — handlers receive an `EffectContext` and return a new state (copy-on-write consistent with the engine).
- Unknown or unregistered effects emit `warnings.warn` and return `ctx.state` unchanged — safe degradation.

### Parser (`parser.py`)
- Simple linear scan of `PATTERNS` list — first match wins.
- More specific patterns (e.g., `heal_grass_target`) appear before more general ones (`heal_target`) to avoid false matches.
- `parse_effect_text("")` returns `[]` (no effects, not an error).
- All 14 effect patterns from the a1-genetic-apex set are covered.

### Deck Validator (`decks/validator.py`)
- `is_card_fully_implemented` checks each effect text on the card: attack effects, non-passive ability effects, and trainer effect text.
- `validate_deck` blocks cards with unimplemented effects from being used — deck building is gated on Phase 3b completion.
- Duplicate detection is name-based (matching game rules: 2 copies max per name).

---

## Effects Recognized by Parser

| Effect Name | Example Text |
|-------------|-------------|
| `heal_self` | "Heal 30 damage from this Pokémon" |
| `search_deck_grass_pokemon` | "Put 1 random Grass Pokémon from deck into hand" |
| `attach_energy_zone_self` | "Take 3 Fire Energy from your Energy Zone and attach it to this Pokémon" |
| `attach_energy_zone_bench` | "Take a Grass Energy from your Energy Zone and attach it to 1 of your Benched Grass Pokémon" |
| `cant_attack_next_turn` | "Defending Pokémon can't attack during your opponent's next turn" |
| `discard_energy_self` | "Discard a Fire Energy from this Pokémon" |
| `heal_all_own` | "Heal 20 damage from each of your Pokémon" |
| `heal_grass_target` | "Heal 50 damage from 1 of your Grass Pokémon" |
| `heal_target` | "Heal 20 damage from 1 of your Pokémon" |
| `draw_cards` | "Draw 2 cards" |
| `draw_basic_pokemon` | "Draw 1 Basic Pokémon card" |
| `rare_candy_evolve` | "Evolve a Basic Pokémon directly to a Stage 2 Pokémon this turn" |
| `switch_opponent_active` | "Switch out your opponent's Active Pokémon to the Bench" |
| `hp_bonus` | "The Pokémon this card is attached to has +20 HP" |

---

## Next Phase

**Phase 3b** will implement the actual handler functions for each of the 14 effect names above. Each handler:
1. Is decorated with `@register_effect('effect_name')`
2. Accepts `(ctx: EffectContext, **params)` and returns a new `GameState`
3. Lives in `ptcgp/effects/handlers/` (one file per logical group)

Once all handlers are registered, `is_card_fully_implemented()` will return `True` for all cards in the a1-genetic-apex set and deck building will be fully unblocked.
