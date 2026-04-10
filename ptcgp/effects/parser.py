"""Parse card effect text strings into Effect tokens.

The parser walks a card's raw effect text and tries to match each recognised
pattern, emitting one or more :class:`Effect` tokens. A single piece of text
may contain multiple effects (e.g. "Flip a coin. If heads, this attack does
30 more damage. This Pokémon also does 20 damage to itself.") — we keep
scanning the text so every matching pattern contributes one token.

Patterns are intentionally forgiving: case-insensitive, accent-insensitive on
Pokémon/pokemon, and tolerant of minor punctuation differences between sets.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from ptcgp.effects.base import Effect, UnknownEffect


# Shorthand for "pokemon" with optional accent
_POK = r"pok[eé]mon"

# Unicode minus (U+2212) vs ASCII hyphen — match both everywhere
_DASH = r"[-\u2212]"


def _int(m, group: int | str = 1) -> int:
    return int(m.group(group))


# (regex, effect_name, params_extractor)
# Patterns are tried in order and any number of them may match a single text.
PATTERNS: list[tuple[str, str, Callable[[re.Match], dict[str, Any]]]] = [
    # ---- heals ----------------------------------------------------------
    (rf"heal (\d+) damage from this {_POK}", "heal_self",
     lambda m: {"amount": _int(m)}),
    (rf"heal (\d+) damage from each of your {_POK}", "heal_all_own",
     lambda m: {"amount": _int(m)}),
    (rf"heal (\d+) damage from 1 of your grass {_POK}", "heal_grass_target",
     lambda m: {"amount": _int(m)}),
    (rf"heal (\d+) damage from each of your (\w+) {_POK}", "heal_all_typed",
     lambda m: {"amount": _int(m), "energy_type": m.group(2).capitalize()}),
    (rf"heal (\d+) damage from 1 of your {_POK}", "heal_target",
     lambda m: {"amount": _int(m)}),
    (rf"heal (\d+) damage from your active {_POK}", "heal_active",
     lambda m: {"amount": _int(m)}),
    (rf"heal from this {_POK} the same amount of damage", "heal_self_equal_to_damage_dealt",
     lambda m: {}),

    # ---- deck search / draw --------------------------------------------
    (rf"put 1 random grass {_POK}.*into your hand", "search_deck_grass_pokemon",
     lambda m: {}),
    (rf"put 1 random (\w+).*from your deck onto your bench", "search_deck_named_basic",
     lambda m: {"name": m.group(1)}),
    (rf"put a random card that evolves from (\w+) from your deck into your hand",
     "search_deck_evolves_from",
     lambda m: {"name": m.group(1)}),
    (rf"put a random {_POK} from your deck into your hand", "search_deck_random_pokemon",
     lambda m: {}),
    (rf"draw 1 basic {_POK}", "draw_basic_pokemon",
     lambda m: {"count": 1}),
    (r"draw (\d+) cards?", "draw_cards",
     lambda m: {"count": _int(m)}),
    (r"draw a card for each card in your opponent'?s hand",
     "shuffle_hand_draw_opponent_count", lambda m: {}),
    (r"draw a card\.?", "draw_one_card",
     lambda m: {}),
    (r"draw 1 card\.?", "draw_one_card",
     lambda m: {}),
    (rf"your opponent reveals their hand", "reveal_opponent_hand",
     lambda m: {}),
    (r"look at.*top.*of your deck", "look_top_of_deck",
     lambda m: {"count": 1}),
    (r"look at the top card of that player'?s deck", "look_top_of_deck",
     lambda m: {"count": 1}),
    (r"shuffle your hand into your deck", "shuffle_hand_into_deck",
     lambda m: {}),

    # ---- discard from opponent hand ------------------------------------
    (rf"discard a random {_POK} tool card from your opponent'?s hand",
     "discard_random_tool_from_hand", lambda m: {}),
    (rf"discard a random item card from your opponent'?s hand",
     "discard_random_item_from_hand", lambda m: {}),

    # ---- energy manipulation -------------------------------------------
    (rf"take (\d+) (\w+) energy from your energy zone and attach it to 1 of your benched {_POK}",
     "attach_n_energy_zone_bench",
     lambda m: {"count": _int(m), "energy_type": m.group(2).capitalize()}),
    (rf"take (\d+) (\w+) energy from your energy zone and attach it to this",
     "attach_energy_zone_self",
     lambda m: {"count": _int(m), "energy_type": m.group(2).capitalize()}),
    (rf"take a (\w+) energy from your energy zone and attach it to 1 of your benched (\w+) {_POK}",
     "attach_energy_zone_bench",
     lambda m: {"energy_type": m.group(1).capitalize(), "target_type": m.group(2).capitalize()}),
    # bracket notation: [L], [M], [W], etc.
    (rf"take a \[(\w+)\] energy from your energy zone and attach it to 1 of your benched \[(\w+)\] {_POK}",
     "attach_energy_zone_bench_bracket",
     lambda m: {"energy_type": m.group(1), "target_type": m.group(2)}),
    (rf"take a \[(\w+)\] energy from your energy zone and attach it to this {_POK}",
     "attach_energy_zone_self_bracket",
     lambda m: {"energy_type": m.group(1)}),
    (rf"take a \[(\w+)\] energy from your energy zone and attach it to 1 of your benched {_POK}",
     "attach_energy_zone_bench_any_bracket",
     lambda m: {"energy_type": m.group(1)}),
    (rf"at the end of your first turn, take a \[(\w+)\] energy.*attach it to this {_POK}",
     "first_turn_energy_attach",
     lambda m: {"energy_type": m.group(1)}),
    (rf"take a colorless energy from your energy zone and attach it to 1 of your benched {_POK}",
     "attach_colorless_energy_zone_bench",
     lambda m: {}),
    (rf"take a (\w+) energy from your energy zone and attach it to this {_POK}",
     "attach_energy_zone_self",
     lambda m: {"count": 1, "energy_type": m.group(1).capitalize()}),
    (rf"take 1? ?\[?(\w+)\]? energy from your energy zone and attach it to this {_POK}",
     "attach_energy_zone_self",
     lambda m: {"count": 1, "energy_type": m.group(1).strip("[]").capitalize()}),
    (rf"choose 1 of your (\w+) {_POK}, and flip a coin until you get tails. for each heads, take a (\w+) energy",
     "coin_flip_until_tails_attach_energy",
     lambda m: {"energy_type": m.group(2).capitalize(), "element_filter": m.group(1).capitalize()}),
    (rf"flip (\d+) coins?\. take an amount of (\w+) energy.*benched (\w+) {_POK}",
     "multi_coin_attach_bench",
     lambda m: {"count": _int(m), "energy_type": m.group(2).capitalize(),
                "element_filter": m.group(3).capitalize()}),
    (rf"take a (\w+) energy from your energy zone and attach it to (\w+) or (\w+)",
     "attach_energy_zone_named",
     lambda m: {"energy_type": m.group(1).capitalize(),
                "names": (m.group(2), m.group(3))}),
    (rf"choose 2 of your benched {_POK}.*take a water energy",
     "attach_water_two_bench", lambda m: {}),
    (rf"move all (\w+) energy from 1 of your benched (\w+) {_POK} to your active {_POK}",
     "move_all_typed_energy_bench_to_active",
     lambda m: {"energy_type": m.group(1).capitalize(), "element_filter": m.group(2).capitalize()}),
    (rf"move all (\w+) energy from your benched {_POK} to your (\w+), (\w+), or (\w+)",
     "move_all_electric_to_active_named",
     lambda m: {"names": (m.group(2), m.group(3), m.group(4))}),
    (rf"move a water energy from 1 of your benched water {_POK} to your active water {_POK}",
     "move_water_bench_to_active", lambda m: {}),
    (rf"move an energy from 1 of your benched {_POK} to your active",
     "move_bench_energy_to_active",
     lambda m: {}),

    (rf"discard (\d+) (\w+) energy from this {_POK}", "discard_n_energy_self",
     lambda m: {"count": _int(m), "energy_type": m.group(2).capitalize()}),
    (rf"discard all (\w+) energy from this {_POK}", "discard_all_typed_energy_self",
     lambda m: {"energy_type": m.group(1).capitalize()}),
    (rf"discard a? ?(\w+) energy from this {_POK}", "discard_energy_self",
     lambda m: {"energy_type": m.group(1).capitalize()}),
    (rf"discard all energy from this {_POK}", "discard_all_energy_self",
     lambda m: {}),
    (r"flip a coin\. if heads, discard a random energy from your opponent",
     "coin_flip_discard_random_energy_opponent",
     lambda m: {}),
    (r"discard a random energy from your opponent'?s? active",
     "discard_random_energy_opponent",
     lambda m: {}),
    (r"discard a random energy from both active", "discard_random_energy_both_active",
     lambda m: {}),
    (rf"discard a random energy from among the energy attached to all {_POK}",
     "discard_random_energy_all_pokemon", lambda m: {}),
    (r"discard the top (\d+) cards? of your deck", "discard_top_deck",
     lambda m: {"count": _int(m)}),

    # ---- status effects -----------------------------------------------
    (rf"your opponent'?s active {_POK} is now asleep", "apply_sleep", lambda m: {}),
    (rf"your opponent'?s active {_POK} is now poisoned", "apply_poison", lambda m: {}),
    (rf"your opponent'?s active {_POK} is now paralyzed", "apply_paralysis", lambda m: {}),
    (rf"your opponent'?s active {_POK} is now burned", "apply_burn", lambda m: {}),
    (rf"your opponent'?s active {_POK} is now confused", "apply_confusion", lambda m: {}),
    (rf"flip a coin\. if heads, your opponent'?s active {_POK} is now paralyzed",
     "coin_flip_apply_paralysis", lambda m: {}),
    (rf"flip a coin\. if heads, your opponent'?s active {_POK} is now asleep",
     "coin_flip_apply_sleep", lambda m: {}),
    (rf"this {_POK} is now confused", "self_confuse", lambda m: {}),
    (rf"this {_POK} is now asleep", "self_sleep", lambda m: {}),
    (rf"1 special condition.*chosen at random.*opponent'?s active", "apply_random_status",
     lambda m: {}),
    (rf"your opponent'?s active {_POK} takes \+(\d+) damage from being poisoned",
     "toxic_poison", lambda m: {}),

    # ---- damage modifiers (coin flips / conditionals) ------------------
    (r"flip a coin\. if tails, this attack does nothing", "coin_flip_nothing",
     lambda m: {}),
    (rf"flip a coin\. if heads, this attack does (\d+) more damage\. if tails, this {_POK} also does (\d+) damage to itself",
     "coin_flip_bonus_or_self_damage",
     lambda m: {"bonus": _int(m, 1), "self_damage": _int(m, 2)}),
    (r"flip a coin\. if heads, this attack does (\d+) more damage", "coin_flip_bonus_damage",
     lambda m: {"amount": _int(m)}),
    (r"flip 2 coins\. if both.*heads, this attack does (\d+) more damage",
     "both_coins_bonus",
     lambda m: {"amount": _int(m)}),
    (rf"flip 2 coins\. if both of them are heads, your opponent'?s active {_POK} is knocked out",
     "double_heads_instant_ko", lambda m: {}),
    (r"flip (\d+) coins?\. this attack does (\d+) damage for each heads",
     "multi_coin_damage",
     lambda m: {"count": _int(m, 1), "per": _int(m, 2)}),
    (r"flip (\d+) coins?\. this attack does (\d+) more damage for each heads",
     "multi_coin_bonus",
     lambda m: {"count": _int(m, 1), "per": _int(m, 2)}),
    (r"flip a coin until you get tails\. this attack does (\d+) damage for each heads",
     "flip_until_tails_damage",
     lambda m: {"per": _int(m)}),
    (r"flip a coin until you get tails\. this attack does (\d+) more damage for each heads",
     "flip_until_tails_bonus",
     lambda m: {"per": _int(m)}),
    (rf"flip a coin for each energy attached to this {_POK}\. this attack does (\d+) damage for each heads",
     "multi_coin_per_energy_damage",
     lambda m: {"per": _int(m)}),
    (rf"flip a coin for each \[(\w+)\] energy attached to this {_POK}\. this attack does (\d+) damage for each heads",
     "multi_coin_per_typed_energy_damage",
     lambda m: {"per": _int(m, 2), "energy_type": m.group(1)}),
    (rf"flip a coin for each {_POK} you have in play\. this attack does (\d+) damage for each heads",
     "multi_coin_per_pokemon_damage",
     lambda m: {"per": _int(m)}),
    (rf"this attack does (\d+) damage for each of your benched (\w+) {_POK}",
     "bonus_per_bench_element",
     lambda m: {"per": _int(m, 1), "element": m.group(2).capitalize()}),
    (rf"this attack does (\d+) damage for each of your benched {_POK}",
     "bonus_per_bench",
     lambda m: {"per": _int(m)}),
    (rf"this attack does (\d+) more damage for each of your benched (\w+)",
     "bonus_per_bench_named",
     lambda m: {"per": _int(m, 1), "name": m.group(2)}),
    (rf"if passimian is on your bench, this attack does (\d+) more damage",
     "bonus_per_bench_named",
     lambda m: {"per": _int(m), "name": "Passimian"}),
    (rf"this attack does (\d+) more damage for each energy attached to your opponent'?s active {_POK}",
     "bonus_per_opponent_energy",
     lambda m: {"per": _int(m)}),
    (rf"this attack does (\d+) more damage for each of your opponent'?s benched {_POK}",
     "bonus_per_opponent_bench",
     lambda m: {"per": _int(m)}),
    # generalized extra energy bonus (any type)
    (rf"if this {_POK} has at least (\d+) extra (\w+) energy attached, this attack does (\d+) more damage",
     "bonus_if_extra_energy",
     lambda m: {"threshold": _int(m, 1), "bonus": _int(m, 3), "energy_type": m.group(2).capitalize()}),
    (rf"if your opponent'?s active {_POK} has damage on it, this attack does (\d+) more damage",
     "bonus_if_opponent_damaged",
     lambda m: {"bonus": _int(m)}),
    (rf"if this {_POK} has damage on it, this attack does (\d+) more damage",
     "bonus_if_self_damaged",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} is poisoned, this attack does (\d+) more damage",
     "bonus_if_opponent_poisoned",
     lambda m: {"bonus": _int(m)}),
    (rf"if this {_POK} has a {_POK} tool attached, this attack does (\d+) more damage",
     "bonus_if_tool_attached",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} has a {_POK} tool attached, this attack does (\d+) more damage",
     "bonus_if_opponent_has_tool",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} is a {_POK} ex, this attack does (\d+)\s*more damage",
     "bonus_if_opponent_ex",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} is a basic {_POK}, this attack does (\d+) more damage",
     "bonus_if_opponent_basic",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} is a \[(\w+)\] {_POK}, this attack does (\d+) more damage",
     "bonus_if_opponent_element",
     lambda m: {"bonus": _int(m, 2), "element": m.group(1)}),
    (rf"if your opponent'?s active {_POK} is a (\w+) {_POK}, this attack does (\d+) more damage",
     "bonus_if_opponent_element",
     lambda m: {"bonus": _int(m, 2), "element": m.group(1).capitalize()}),
    (rf"if your opponent'?s active {_POK} has an ability, this attack does (\d+) more damage",
     "bonus_if_opponent_has_ability",
     lambda m: {"bonus": _int(m)}),
    (rf"if any of your benched {_POK} have damage on them, this attack does (\d+) more damage",
     "bonus_if_bench_damaged",
     lambda m: {"bonus": _int(m)}),
    (rf"if any of your {_POK} were knocked out.*last turn, this attack does (\d+) more damage",
     "bonus_if_ko_last_turn",
     lambda m: {"bonus": _int(m)}),
    (r"if you played a supporter card from your hand during this turn, this attack does (\d+) more damage",
     "bonus_if_played_supporter",
     lambda m: {"bonus": _int(m)}),
    (rf"if this {_POK} moved from your bench to the active spot this turn, this attack does (\d+) more damage",
     "bonus_if_just_promoted",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} has more remaining hp than this {_POK}, this attack does (\d+) more damage",
     "bonus_if_opponent_more_hp",
     lambda m: {"bonus": _int(m)}),
    (rf"if your opponent'?s active {_POK} is affected by a special condition, this attack does (\d+) more damage",
     "bonus_if_opponent_has_status",
     lambda m: {"bonus": _int(m)}),
    (rf"this attack does more damage equal to the damage this {_POK} has on it",
     "bonus_equal_to_damage_taken",
     lambda m: {}),
    (rf"halve your opponent'?s active {_POK}'?s remaining hp, rounded down",
     "halve_opponent_hp", lambda m: {}),
    (rf"if you have arceus or arceus ex in play, attacks used by this {_POK} do \+(\d+) damage",
     "bonus_if_named_in_play",
     lambda m: {"bonus": _int(m), "names": ("Arceus", "Arceus ex")}),

    # ---- self / bench damage ------------------------------------------
    (rf"this {_POK} also does (\d+) damage to itself", "self_damage",
     lambda m: {"amount": _int(m)}),
    (rf"this attack also does (\d+) damage to each of your opponent'?s benched {_POK}",
     "splash_bench_opponent",
     lambda m: {"amount": _int(m)}),
    (rf"this attack also does (\d+) damage to 1 of your opponent'?s benched {_POK}",
     "bench_hit_opponent",
     lambda m: {"amount": _int(m)}),
    (rf"this attack also does (\d+) damage to 1 of your {_POK}",
     "splash_bench_own",
     lambda m: {"amount": _int(m)}),
    (rf"this attack also does (\d+) damage to 1 of your benched {_POK}",
     "splash_bench_own",
     lambda m: {"amount": _int(m)}),
    (rf"this attack does (\d+) damage to each of your opponent'?s {_POK}",
     "splash_all_opponent",
     lambda m: {"amount": _int(m)}),
    (rf"this attack does (\d+) damage to 1 of your opponent'?s benched {_POK}",
     "bench_hit_opponent",
     lambda m: {"amount": _int(m)}),
    (rf"this attack does (\d+) damage to 1 of your opponent'?s {_POK}",
     "bench_hit_opponent",
     lambda m: {"amount": _int(m)}),
    (rf"1 of your opponent'?s {_POK} is chosen at random\. do (\d+) damage to it",
     "random_hit_one",
     lambda m: {"amount": _int(m)}),
    (rf"1 of your opponent'?s {_POK} is chosen at random (\d+) times?\. for each time.*do (\d+) damage",
     "random_multi_hit",
     lambda m: {"times": _int(m, 1), "amount": _int(m, 2)}),
    (rf"before doing damage, discard all {_POK} tools from your opponent'?s active {_POK}",
     "discard_opponent_tools_before_damage", lambda m: {}),

    # ---- next-turn self effects ----------------------------------------
    (rf"during your next turn, this {_POK} can'?t attack", "self_cant_attack_next_turn",
     lambda m: {}),
    (rf"flip a coin\. if tails, during your next turn, this {_POK} can'?t attack",
     "coin_flip_self_cant_attack_next_turn", lambda m: {}),
    (rf"during your next turn, this {_POK} can'?t use (\w[\w ]*\w)", "self_cant_use_specific_attack",
     lambda m: {"attack_name": m.group(1).strip()}),
    (rf"during your next turn, this {_POK}'?s (\w[\w ]*\w) attack does \+(\d+) damage",
     "self_attack_buff_next_turn",
     lambda m: {"attack_name": m.group(1).strip(), "amount": _int(m, 2)}),

    # ---- next-turn opponent effects ------------------------------------
    (rf"defending {_POK} can'?t attack",
     "cant_attack_next_turn",
     lambda m: {}),
    (rf"during your opponent'?s next turn,.*defending {_POK}.*can'?t attack",
     "cant_attack_next_turn",
     lambda m: {}),
    (rf"flip a coin\. if heads, the defending {_POK} can'?t attack",
     "cant_attack_next_turn",
     lambda m: {}),
    (rf"during your opponent'?s next turn, the defending {_POK} can'?t retreat",
     "cant_retreat_next_turn",
     lambda m: {}),
    (rf"during your opponent'?s next turn, attacks used by the defending {_POK} do {_DASH}(\d+) damage",
     "defender_attacks_do_less_damage",
     lambda m: {"amount": _int(m)}),
    (rf"during your opponent'?s next turn, attacks used by the defending {_POK} cost 1 colorless more.*retreat cost is 1 colorless more",
     "opponent_cost_increase_next_turn",
     lambda m: {}),
    (rf"during your opponent'?s next turn, this {_POK} takes {_DASH}(\d+) damage",
     "take_less_damage_next_turn",
     lambda m: {"amount": _int(m)}),
    (rf"during your opponent'?s next turn, this {_POK} takes \+(\d+) damage",
     "take_more_damage_next_turn",
     lambda m: {"amount": _int(m)}),
    (rf"flip a coin\. if heads, during your opponent'?s next turn, prevent all damage",
     "prevent_damage_next_turn",
     lambda m: {}),
    (r"your opponent can'?t use any supporter cards from their hand during their next turn",
     "opponent_no_supporter_next_turn",
     lambda m: {}),
    (rf"during your opponent'?s next turn, if the defending {_POK} tries to use an attack.*your opponent flips a coin\. if tails.*that attack doesn'?t happen",
     "coin_flip_attack_block_next_turn",
     lambda m: {}),
    (r"during your opponent'?s next turn, they can'?t play any item cards from their hand",
     "opponent_no_items_next_turn",
     lambda m: {}),
    (r"during your opponent'?s next turn, they can'?t take any energy from their energy zone",
     "opponent_no_energy_next_turn",
     lambda m: {}),
    (r"flip a coin\. if heads, discard a random card from your opponent'?s hand",
     "discard_random_card_opponent",
     lambda m: {}),

    # ---- coin flip bounce/shuffle/etc ----------------------------------
    (rf"flip a coin\. if heads, put your opponent'?s active {_POK} into their hand",
     "coin_flip_bounce_opponent", lambda m: {}),
    (rf"flip a coin\. if heads, your opponent reveals a random card from their hand and shuffles it into their deck",
     "coin_flip_shuffle_opponent_card", lambda m: {}),
    (rf"flip 3 coins\. for each heads, a card is chosen at random from your opponent'?s hand.*shuffles it into their deck",
     "multi_coin_shuffle_opponent_cards", lambda m: {"count": 3}),

    # ---- switching ----------------------------------------------------
    (rf"switch out your opponent.*active {_POK} to the bench", "switch_opponent_active",
     lambda m: {}),
    (rf"switch this {_POK} with 1 of your benched (\w+) {_POK}", "switch_self_to_bench_typed",
     lambda m: {"element": m.group(1).capitalize()}),
    (rf"switch this {_POK} with 1 of your benched {_POK}", "switch_self_to_bench",
     lambda m: {}),
    (rf"switch in 1 of your opponent'?s benched basic {_POK} to the active",
     "switch_opponent_basic_to_active",
     lambda m: {}),
    (rf"flip a coin\. if heads, your opponent shuffles their active {_POK} back into their deck",
     "shuffle_opponent_active_into_deck",
     lambda m: {}),
    (rf"put your (\w+) or (\w+) in the active spot into your hand",
     "return_active_to_hand_named",
     lambda m: {"names": (m.group(1), m.group(2))}),
    (rf"if this {_POK} is on your bench, (?:you )?(?:may )?switch (?:it|this {_POK}) with your active {_POK}",
     "ability_bench_to_active", lambda m: {}),
    (r"switch your active ultra beast with 1 of your benched ultra beast",
     "switch_ultra_beast", lambda m: {}),

    # ---- copy attack --------------------------------------------------
    (rf"choose 1 of your opponent'?s (?:active )?{_POK}'?s attacks and use it",
     "copy_opponent_attack",
     lambda m: {}),

    # ---- trainer-card-only effects ------------------------------------
    (rf"during this turn, attacks used by your (\w+), (\w+), or (\w+) do \+(\d+) damage",
     "supporter_damage_aura",
     lambda m: {"amount": _int(m, 4), "names": (m.group(1), m.group(2), m.group(3))}),
    (rf"during this turn, attacks used by your {_POK} do \+(\d+) damage",
     "supporter_damage_aura",
     lambda m: {"amount": _int(m), "names": ()}),
    (r"retreat cost.*-(\d+)", "reduce_retreat_cost",
     lambda m: {"amount": _int(m)}),
    (r"your opponent shuffles their hand into their deck.*draws (\d+)", "opponent_shuffle_hand_draw",
     lambda m: {"count": _int(m)}),
    (r"look at your opponent'?s hand", "look_opponent_hand",
     lambda m: {}),

    # ---- supporter: two-named damage aura --------------------------------
    (rf"during this turn, attacks used by your (\w+) or (\w+) do \+(\d+) damage",
     "supporter_damage_aura",
     lambda m: {"amount": _int(m, 3), "names": (m.group(1), m.group(2))}),

    # ---- supporter: damage aura vs ex only --------------------------------
    (rf"during this turn, attacks used by your {_POK} do \+(\d+) damage to your opponent'?s active {_POK} ex",
     "supporter_damage_aura_vs_ex",
     lambda m: {"amount": _int(m)}),

    # ---- Iono: both players shuffle and redraw ----------------------------
    (r"each player shuffles the cards in their hand into their deck, then draws that many cards",
     "iono_hand_shuffle", lambda m: {}),

    # ---- Mars: opponent shuffle hand, draw remaining points ---------------
    (r"your opponent shuffles their hand into their deck and draws a card for each of their remaining points",
     "mars_hand_shuffle", lambda m: {}),

    # ---- heal and cure status (Pokemon Center Lady) -----------------------
    (rf"heal (\d+) damage from 1 of your {_POK}, and it recovers from all special conditions",
     "heal_and_cure_status", lambda m: {"amount": _int(m)}),

    # ---- Coin flip until tails discard energy (Team Rocket Grunt) ---------
    (rf"flip a coin until you get tails\. for each heads, discard a random energy from your opponent'?s active",
     "coin_flip_until_tails_discard_energy", lambda m: {}),

    # ---- Heal water pokemon (Irida) ---------------------------------------
    (rf"heal (\d+) damage from each of your {_POK} that has any water energy",
     "heal_water_pokemon", lambda m: {"amount": _int(m)}),

    # ---- reduce attack cost named (Barry) ---------------------------------
    (rf"during this turn, attacks used by your (\w+), (\w+),? and (\w+) cost (\d+) less energy",
     "reduce_attack_cost_named",
     lambda m: {"names": (m.group(1), m.group(2), m.group(3)), "amount": _int(m, 4)}),

    # ---- next-turn metal damage reduction (Adaman) ------------------------
    (rf"during your opponent'?s next turn, all of your metal {_POK} take {_DASH}(\d+) damage",
     "next_turn_metal_damage_reduction", lambda m: {"amount": _int(m)}),

    # ---- next-turn all damage reduction (Blue) ----------------------------
    (rf"during your opponent'?s next turn, all of your {_POK} take {_DASH}(\d+) damage from attacks",
     "next_turn_all_damage_reduction", lambda m: {"amount": _int(m)}),

    # ---- retreat cost reduction (Leaf) ------------------------------------
    (rf"retreat cost of your active {_POK} is (\d+) less", "reduce_retreat_cost",
     lambda m: {"amount": _int(m)}),

    # ---- return Mew ex to hand (Budding Expeditioner) ---------------------
    (rf"put your (\w+ ex) in the active spot into your hand",
     "return_active_to_hand_named",
     lambda m: {"names": (m.group(1),)}),

    # ---- place opponent basic from discard (Pokemon Flute) ----------------
    (rf"put 1 basic {_POK} from your opponent'?s discard pile onto your opponent'?s bench",
     "place_opponent_basic_from_discard", lambda m: {}),

    # ---- mythical slab: look top, psychic to hand -------------------------
    (rf"if that card is a psychic {_POK}, put it into your hand",
     "mythical_slab", lambda m: {}),

    # ---- pokemon communication: swap hand/deck ----------------------------
    (rf"choose a {_POK} in your hand and switch it with a random {_POK} in your deck",
     "pokemon_communication", lambda m: {}),

    # ---- Lum Berry (passive tool) -----------------------------------------
    (r"at the end of each turn.*affected by any special conditions.*recovers from all of them",
     "passive_lum_berry", lambda m: {}),

    # ---- fishing net: random basic water from discard ---------------------
    (rf"put a random basic water {_POK} from your discard pile into your hand",
     "fishing_net", lambda m: {}),

    # ---- Big Malasada: heal 10 + remove random status ---------------------
    (rf"heal (\d+) damage and remove a random special condition from your active",
     "big_malasada", lambda m: {"amount": _int(m)}),

    # ---- Poison Barb (passive tool) ---------------------------------------
    (r"the attacking {_POK} is now poisoned".replace("{_POK}", _POK),
     "passive_retaliate_poison", lambda m: {}),

    # ---- Leaf Cape: Grass +30 HP ------------------------------------------
    (rf"the grass {_POK} this card is attached to gets \+(\d+) hp",
     "hp_bonus", lambda m: {"amount": _int(m)}),

    # ---- Beastite (passive tool) ------------------------------------------
    (r"do \+(\d+) damage.*for each point you have gotten",
     "passive_beastite_damage", lambda m: {}),

    # ---- Beast Wall -------------------------------------------------------
    (r"all of your ultra beasts take {_DASH}(\d+) damage".replace("{_DASH}", _DASH),
     "beast_wall_protection", lambda m: {}),

    # ---- Electrical Cord (passive tool) -----------------------------------
    (r"move 2 lightning energy from that {_POK}.*attach 1 energy each to 2".replace("{_POK}", _POK),
     "passive_electrical_cord", lambda m: {}),

    # ---- Gladion: search deck for Type: Null or Silvally ------------------
    (r"put 1 random type: null or silvally from your deck into your hand",
     "search_deck_named", lambda m: {"names": ("Type: Null", "Silvally")}),

    # ---- Looker: reveal opponent supporters (info-only) -------------------
    (r"your opponent reveals all of the supporter cards in their deck",
     "reveal_opponent_supporters", lambda m: {}),

    # ---- Lusamine: conditional + attach from discard ----------------------
    (r"choose 1 of your ultra beasts\. attach 2 random energy from your discard pile",
     "lusamine_attach", lambda m: {}),

    # ---- Repel: switch opponent's active Basic ----------------------------
    (rf"switch out your opponent'?s active basic {_POK} to the bench",
     "switch_opponent_basic_to_active", lambda m: {}),

    # ---- Discard all opponent tools (Guzma) -------------------------------
    (rf"discard all {_POK} tool cards attached to each of your opponent'?s {_POK}",
     "discard_all_opponent_tools", lambda m: {}),

    # ---- Heal stage 2 target (Lillie) ------------------------------------
    (rf"heal (\d+) damage from 1 of your stage 2 {_POK}",
     "heal_stage2_target", lambda m: {"amount": _int(m)}),

    # ---- Heal all named, discard energy (Mallow) --------------------------
    (rf"heal all damage from 1 of your (\w+) or (\w+)\. if you do, discard all energy",
     "heal_all_named_discard_energy",
     lambda m: {"names": (m.group(1), m.group(2))}),

    # ---- Move damage to opponent (Acerola) --------------------------------
    (rf"choose 1 of your (\w+) or (\w+) that has damage on it, and move (\d+) of its damage to your opponent",
     "move_damage_to_opponent",
     lambda m: {"names": (m.group(1), m.group(2)), "amount": _int(m, 3)}),

    # ---- Return colorless to hand (Ilima) ---------------------------------
    (rf"put 1 of your colorless {_POK} that has damage on it into your hand",
     "return_colorless_to_hand", lambda m: {}),

    # ---- Lana: conditional switch opponent --------------------------------
    (rf"you can use this card only if you have (\w+) in play\. switch in 1 of your opponent'?s benched {_POK} to the active",
     "switch_opponent_active", lambda m: {}),

    # ---- Kiawe: attach fire energy, end turn ------------------------------
    (rf"choose 1 of your ([\w ]+) or ([\w ]+)\. take (\d+) fire energy from your energy zone and attach it to that {_POK}\. your turn ends",
     "attach_energy_named_end_turn",
     lambda m: {"names": (m.group(1).strip(), m.group(2).strip()), "count": _int(m, 3), "energy_type": "Fire"}),

    # ---- Sophocles: multi-word named damage aura ---------------------------
    (rf"during this turn, attacks used by your ([\w ]+), ([\w ]+),? or ([\w ]+) do \+(\d+) damage",
     "supporter_damage_aura",
     lambda m: {"amount": _int(m, 4), "names": (m.group(1).strip(), m.group(2).strip(), m.group(3).strip())}),

    # ---- search deck named (multi): Team Galactic Grunt, Poke Ball --------
    (rf"put 1 random (\w+), (\w+), or (\w+) from your deck into your hand",
     "search_deck_named",
     lambda m: {"names": (m.group(1), m.group(2), m.group(3))}),

    # ---- Poke Ball: search deck for random basic pokemon ------------------
    (rf"put 1 random basic {_POK} from your deck into your hand",
     "search_deck_random_basic", lambda m: {}),

    # ---- Celestic Town Elder: random basic from discard -------------------
    (rf"put 1 random basic {_POK} from your discard pile into your hand",
     "search_discard_random_basic", lambda m: {}),

    # ---- Volkner: attach energy from discard to named ---------------------
    (rf"choose 1 of your (\w+) or (\w+)\. attach (\d+) (\w+) energy from your discard pile to that {_POK}",
     "attach_energy_discard_named",
     lambda m: {"names": (m.group(1), m.group(2)), "count": _int(m, 3), "energy_type": m.group(4).capitalize()}),

    # ---- Cyrus: switch opponent damaged to active --------------------------
    (rf"switch in 1 of your opponent'?s benched {_POK} that has damage on it to the active",
     "switch_opponent_damaged_to_active", lambda m: {}),

    # ---- Dawn: move energy bench to active (already have pattern) ----------

    # ---- tool: HP bonus -----------------------------------------------
    (rf"{_POK} this card is attached to has \+(\d+) hp", "hp_bonus",
     lambda m: {"amount": _int(m)}),
    (rf"{_POK} this card is attached to gets \+(\d+) hp", "hp_bonus",
     lambda m: {"amount": _int(m)}),
    (rf"evolve a basic {_POK} directly to a stage 2", "rare_candy_evolve", lambda m: {}),
    (rf"put that card onto the basic {_POK} to evolve it, skipping the stage 1",
     "rare_candy_evolve", lambda m: {}),
    (rf"rare candy", "rare_candy_evolve", lambda m: {}),

    # ---- ability effects (activated) -----------------------------------
    (rf"once during your turn.*make your opponent'?s active {_POK} poisoned",
     "apply_poison", lambda m: {}),
    (rf"once during your turn.*flip a coin\. if heads, your opponent'?s active {_POK} is now asleep",
     "coin_flip_apply_sleep", lambda m: {}),
    (rf"once during your turn.*switch out your opponent'?s active {_POK} to the bench",
     "switch_opponent_active", lambda m: {}),
    (rf"once during your turn.*look at the top card of (?:your|that player'?s) deck",
     "look_top_of_deck", lambda m: {"count": 1}),
    (rf"once during your turn.*heal (\d+) damage from each of your (\w+) {_POK}",
     "heal_all_typed", lambda m: {"amount": _int(m), "energy_type": m.group(2).capitalize()}),
    (rf"once during your turn.*heal (\d+) damage from each of your {_POK}",
     "heal_all_own", lambda m: {"amount": _int(m)}),
    (rf"once during your turn.*heal (\d+) damage from your active {_POK}",
     "heal_active", lambda m: {"amount": _int(m)}),
    (rf"once during your turn.*take a lightning energy.*attach it to this",
     "attach_energy_zone_self",
     lambda m: {"count": 1, "energy_type": "Lightning"}),
    (rf"once during your turn.*take 1 psychic energy.*attach it to the psychic {_POK} in the active",
     "attach_energy_zone_self",
     lambda m: {"count": 1, "energy_type": "Psychic"}),
    (rf"once during your turn.*take a grass energy.*attach it to 1 of your grass {_POK}",
     "attach_energy_zone_to_grass", lambda m: {}),
    (rf"once during your turn.*take a psychic energy.*attach it to this {_POK}\. if you use this ability, your turn ends",
     "ability_attach_energy_end_turn", lambda m: {}),
    (rf"once during your turn.*do (\d+) damage to 1 of your opponent'?s {_POK}",
     "bench_hit_opponent", lambda m: {"amount": _int(m)}),
    (rf"once during your turn.*do (\d+) damage to your opponent'?s active {_POK}",
     "bench_hit_opponent", lambda m: {"amount": _int(m)}),
    (rf"once during your turn.*put a random {_POK} from your deck into your hand",
     "search_deck_random_pokemon", lambda m: {}),
    (rf"once during your turn.*if you have arceus or arceus ex in play.*do (\d+) damage to your opponent'?s active",
     "bench_hit_opponent", lambda m: {"amount": _int(m)}),
    (rf"once during your turn.*move all (\w+) energy from 1 of your benched (\w+) {_POK} to your active {_POK}",
     "move_all_typed_energy_bench_to_active",
     lambda m: {"energy_type": m.group(1).capitalize(), "element_filter": m.group(2).capitalize()}),
    (rf"once during your turn.*switch your active ultra beast with 1 of your benched ultra beast",
     "switch_ultra_beast", lambda m: {}),
    # Discard-to-draw ability
    (r"you must discard a card from your hand.*once during your turn.*draw a card",
     "discard_to_draw", lambda m: {}),
    # Move all damage to self
    (rf"move all of its damage to this {_POK}",
     "passive_move_damage_to_self", lambda m: {}),
    # Change opponent energy type
    (r"change the type of the next energy", "change_opponent_energy_type", lambda m: {}),

    # ---- passive abilities (damage reduction / retaliate / supporter denial) ---
    (rf"this {_POK} takes {_DASH}(\d+) damage from attacks from (\w+) or (\w+) {_POK}",
     "passive_type_damage_reduction",
     lambda m: {"amount": _int(m), "types": (m.group(2).capitalize(), m.group(3).capitalize())}),
    (rf"this {_POK} takes {_DASH}(\d+) damage from attacks",
     "passive_damage_reduction", lambda m: {"amount": _int(m)}),
    (rf"is damaged by an attack.*do (\d+) damage to the attacking {_POK}",
     "passive_retaliate", lambda m: {"amount": _int(m)}),
    (rf"as long as this {_POK} is in the active spot,? your opponent can'?t use any supporter",
     "passive_block_supporters", lambda m: {}),
    (rf"play this card as if it were a (\d+)-hp basic colorless",
     "passive_ditto_impostor", lambda m: {"hp": _int(m)}),
    (rf"if this {_POK} is in the active spot.*switch in 1 of your opponent'?s benched basic {_POK}",
     "switch_opponent_basic_to_active", lambda m: {}),

    # ---- passive abilities: immunity / prevention ----------------------
    (rf"this {_POK} can'?t be affected by any special condition",
     "passive_immune_status", lambda m: {}),
    (rf"prevent all damage done to this {_POK} by attacks from your opponent'?s {_POK} ex",
     "passive_prevent_ex_damage", lambda m: {}),
    (rf"prevent all effects of attacks used by your opponent'?s {_POK} done to this {_POK}",
     "passive_prevent_attack_effects", lambda m: {}),
    (rf"if any damage is done.*flip a coin\. if heads.*{_DASH}(\d+) damage from that attack",
     "passive_coin_flip_damage_reduction", lambda m: {"amount": _int(m)}),
    (rf"if this {_POK} would be knocked out by damage from an attack, flip a coin\. if heads.*remaining hp becomes (\d+)",
     "passive_survive_ko_coin_flip", lambda m: {"remaining_hp": _int(m)}),

    # ---- passive abilities: bench/field effects ------------------------
    (rf"as long as this {_POK} is on your bench.*retreat cost is (\d+) less",
     "passive_bench_retreat_reduction", lambda m: {}),
    (rf"each grass energy attached to your grass {_POK} provides 2 grass energy",
     "passive_double_grass_energy", lambda m: {}),
    (rf"if this {_POK} has any energy attached, it has no retreat cost",
     "passive_free_retreat_with_energy", lambda m: {}),
    (rf"each of your {_POK} that has.*psychic energy.*recovers from all special conditions",
     "passive_psychic_cleanse", lambda m: {}),
    (rf"if this {_POK} is in the active spot and is knocked out.*move all fighting energy.*bench",
     "passive_ko_energy_transfer", lambda m: {}),
    (rf"if this {_POK} is in the active spot and is knocked out.*do (\d+) damage to the attacking",
     "passive_ko_retaliate", lambda m: {"amount": _int(m)}),
    (r"your active dondozo has no retreat cost",
     "passive_named_no_retreat", lambda m: {}),
    (r"whenever you attach a darkness energy.*do (\d+) damage to your opponent",
     "passive_dark_energy_ping", lambda m: {"amount": _int(m)}),
    (rf"during {_POK} checkup.*do (\d+) damage to your opponent",
     "passive_checkup_damage", lambda m: {"amount": _int(m)}),
    (rf"your opponent can'?t play any {_POK} from their hand to evolve their active {_POK}",
     "passive_block_evolution", lambda m: {}),
    (rf"{_POK} \(both yours and your opponent'?s\) can'?t be healed",
     "passive_no_healing", lambda m: {}),
    (r"if you have arceus or arceus ex in play, this {_POK} has no retreat cost".replace("{_POK}", _POK),
     "passive_arceus_no_retreat", lambda m: {}),
    (rf"if you have arceus or arceus ex in play, this {_POK} takes {_DASH}(\d+) damage",
     "passive_arceus_damage_reduction", lambda m: {"amount": _int(m)}),
    (rf"if you have arceus or arceus ex in play, attacks used by this {_POK} cost 1 less colorless",
     "passive_arceus_cost_reduction", lambda m: {}),
    (rf"during your first turn, this {_POK} has no retreat cost",
     "passive_first_turn_no_retreat", lambda m: {}),
    (rf"as long as this {_POK} is in the active spot, whenever you attach an energy.*it is now asleep",
     "passive_energy_sleep", lambda m: {}),
    (rf"attacks used by your (\w+) {_POK} do \+(\d+) damage",
     "passive_type_damage_boost",
     lambda m: {"element": m.group(1).capitalize(), "amount": _int(m, 2)}),
    (rf"as long as this {_POK} is in the active spot, attacks used by your opponent'?s active {_POK} cost 1 colorless more",
     "passive_opponent_attack_cost_increase", lambda m: {}),
    (rf"as long as this {_POK} is in the active spot, attacks used by your opponent'?s active {_POK} do {_DASH}(\d+) damage",
     "passive_opponent_damage_reduction", lambda m: {"amount": _int(m)}),
]


def parse_effect_text(text: str) -> list[Effect]:
    """Parse a card's effect text into a list of Effect tokens.

    Every recognized pattern contributes one token. Unmatched text yields a
    single UnknownEffect for diagnostics.
    """
    if not text or not text.strip():
        return []

    text_lower = text.strip().lower()
    effects: list[Effect] = []
    matched_spans: list[tuple[int, int]] = []

    for pattern, name, extractor in PATTERNS:
        for m in re.finditer(pattern, text_lower, re.IGNORECASE):
            # Skip if this span was already consumed by a more-specific rule.
            if _overlaps_existing(m.span(), matched_spans):
                continue
            try:
                params = extractor(m)
            except Exception:
                continue
            effects.append(Effect(name=name, params=params))
            matched_spans.append(m.span())

    if not effects:
        return [UnknownEffect(name="unknown", raw_text=text)]

    return effects


def _overlaps_existing(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    s, e = span
    for ts, te in taken:
        if s < te and ts < e:
            return True
    return False


def get_effect_names(text: str) -> list[str]:
    """Return just the effect names parsed from text."""
    return [e.name for e in parse_effect_text(text)]


def is_effect_text_known(text: str) -> bool:
    """Return True if ALL effects in text are recognized (no UnknownEffect)."""
    if not text or not text.strip():
        return True
    effects = parse_effect_text(text)
    return all(not isinstance(e, UnknownEffect) for e in effects)
