# Card Effects — a1-genetic-apex

Implementation status for all non-trivial card effects in the MVP set.
Cards with only plain damage attacks (no effect text) require no implementation.

## Status Legend
- ❌ Not implemented — card blocked from deck building
- ✅ Implemented — card usable in decks

---

## Attack Effects

| Card | ID | Attack | Effect | Status |
|------|----|--------|--------|--------|
| Venusaur ex | a1-004 | Giant Bloom | Heal 30 damage from this Pokémon | ✅ |
| Caterpie | a1-005 | Find a Friend | Put 1 random Grass Pokémon from deck into hand | ✅ |
| Petilil | a1-029 | Blot | Heal 10 damage from this Pokémon | ✅ |
| Lilligant | a1-030 | Leaf Supply | Take a Grass Energy from Energy Zone, attach to a Benched Grass Pokémon | ✅ |
| Vulpix | a1-037 | Tail Whip | Flip a coin. Heads: opponent can't attack next turn | ✅ |
| Ninetales | a1-038 | Flamethrower | Discard a Fire Energy from this Pokémon | ✅ |
| Charmander | a1-230 | Ember | Discard a Fire Energy from this Pokémon | ✅ |
| Charizard ex | a2b-010 | Stoke | Take 3 Fire Energy from Energy Zone, attach to this Pokémon | ✅ |

## Abilities

| Card | ID | Ability | Effect | Status |
|------|----|---------|--------|--------|
| Butterfree | a1-007 | Powder Heal | Once per turn: Heal 20 damage from each of your Pokémon | ✅ |

## Trainer — Item Cards

| Card | ID | Effect | Status |
|------|----|--------|--------|
| Potion | pa-001 | Heal 20 damage from 1 of your Pokémon | ✅ |
| Poké Ball | pa-005 | Draw 1 random Basic Pokémon from deck into hand | ✅ |
| Rare Candy | a3-144 | Evolve a Basic Pokémon directly to Stage 2 this turn | ✅ |

## Trainer — Supporter Cards

| Card | ID | Effect | Status |
|------|----|--------|--------|
| Erika | a1-219 | Heal 50 damage from 1 of your Grass Pokémon | ✅ |
| Professor's Research | pa-007 | Draw 2 cards | ✅ |
| Sabrina | a1-272 | Switch opponent's Active Pokémon to Bench (opponent chooses new Active) | ✅ |

## Trainer — Tool Cards

| Card | ID | Effect | Status |
|------|----|--------|--------|
| Giant Cape | a2-147 | The attached Pokémon has +20 HP | ✅ |

---

## Cards With No Effects (no implementation needed)

These cards have only plain damage attacks — they require no effect handler and are always usable:

| Card | ID |
|------|----|
| Bulbasaur | a1-001 |
| Ivysaur | a1-002 |
| Metapod | a1-006 |
| Weedle | a1-008 |
| Kakuna | a1-009 |
| Beedrill | a1-010 |

---

## Effect Handler Summary

| Handler Name | Used By |
|-------------|---------|
| `heal_self(amount)` | Giant Bloom (30), Blot (10) |
| `search_deck_grass_pokemon()` | Find a Friend |
| `attach_energy_from_zone(type, target)` | Leaf Supply (Grass→bench), Stoke (3×Fire→self) |
| `cant_attack_next_turn()` | Tail Whip |
| `discard_energy_from_self(type)` | Flamethrower, Ember |
| `heal_ability(amount, all=True)` | Powder Heal |
| `heal_target(amount)` | Potion, Erika |
| `draw_basic_pokemon(count)` | Poké Ball |
| `rare_candy_evolve()` | Rare Candy |
| `draw_cards(count)` | Professor's Research |
| `switch_opponent_active()` | Sabrina |
| `hp_bonus(amount)` | Giant Cape |
