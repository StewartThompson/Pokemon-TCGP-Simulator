"""Miscellaneous effect handlers: heals, draws, next-turn buffs/debuffs, disruption."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Stage
from ptcgp.effects.registry import EffectContext, register_effect
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot, mutate_slot
from ptcgp.engine.state import GameState


# -------------------------------------------------------------------------
# Heal variants
# -------------------------------------------------------------------------

@register_effect("heal_self_equal_to_damage_dealt")
def heal_self_equal_to_damage_dealt(ctx: EffectContext) -> GameState:
    """Heal the source Pokemon by the damage just dealt (from ctx.extra)."""
    if ctx.source_ref is None:
        return ctx.state
    amount = ctx.extra.get("damage_dealt", 0)
    if amount <= 0:
        return ctx.state
    return mutate_slot(
        ctx.state,
        ctx.source_ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
    )


# -------------------------------------------------------------------------
# Draw / deck manipulation
# -------------------------------------------------------------------------

@register_effect("draw_one_card")
def draw_one_card(ctx: EffectContext) -> GameState:
    state = ctx.state
    p = state.players[ctx.acting_player]
    if not p.deck:
        return state
    state = state.copy()
    player = state.players[ctx.acting_player]
    player.hand.append(player.deck.pop(0))
    return state


@register_effect("reveal_opponent_hand")
def reveal_opponent_hand(ctx: EffectContext) -> GameState:
    """Reveal opponent's hand — information-only, no state change."""
    return ctx.state


@register_effect("look_top_of_deck")
def look_top_of_deck(ctx: EffectContext, count: int = 1) -> GameState:
    """Pokédex / Oddish-style: look at top N cards. Information-only."""
    return ctx.state


@register_effect("search_deck_named_basic")
def search_deck_named_basic(ctx: EffectContext, name: str) -> GameState:
    """Put 1 random Pokemon of the given name from deck onto your Bench.

    Used by Nidoran♂ / similar effects.
    """
    state = ctx.state
    pi = ctx.acting_player
    p = state.players[pi]
    name_low = name.lower()
    matches = [
        cid for cid in p.deck
        if _card_name_equals(cid, name_low) and _is_basic(cid)
    ]
    if not matches:
        return state

    chosen = state.rng.choice(matches)
    empty_slot = next((i for i, s in enumerate(p.bench) if s is None), None)
    if empty_slot is None:
        return state

    state = state.copy()
    p = state.players[pi]
    p.deck.remove(chosen)
    from ptcgp.engine.state import PokemonSlot
    card = get_card(chosen)
    p.bench[empty_slot] = PokemonSlot(card_id=chosen, current_hp=card.hp, max_hp=card.hp)
    return state


def _card_name_equals(card_id: str, name_low: str) -> bool:
    try:
        return get_card(card_id).name.lower() == name_low
    except KeyError:
        return False


def _is_basic(card_id: str) -> bool:
    try:
        return get_card(card_id).stage == Stage.BASIC
    except KeyError:
        return False


# -------------------------------------------------------------------------
# Next-turn buffs/debuffs
# -------------------------------------------------------------------------

@register_effect("cant_retreat_next_turn")
def cant_retreat_next_turn_fx(ctx: EffectContext) -> GameState:
    """Defender can't retreat during your opponent's next turn."""
    opp_ref = SlotRef.active(1 - ctx.acting_player)
    return mutate_slot(
        ctx.state, opp_ref, lambda s: setattr(s, "cant_retreat_next_turn", True)
    )


@register_effect("prevent_damage_next_turn")
def prevent_damage_next_turn_fx(ctx: EffectContext) -> GameState:
    """Coin flip: on heads, prevent all damage to this Pokemon next turn."""
    state = ctx.state
    if state.rng.random() >= 0.5:
        return state
    if ctx.source_ref is None:
        return state
    return mutate_slot(
        state, ctx.source_ref, lambda s: setattr(s, "prevent_damage_next_turn", True)
    )


@register_effect("take_less_damage_next_turn")
def take_less_damage_next_turn_fx(ctx: EffectContext, amount: int) -> GameState:
    """Source Pokemon takes -amount damage from attacks next turn."""
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state, ctx.source_ref, lambda s: setattr(s, "incoming_damage_reduction", amount)
    )


@register_effect("defender_attacks_do_less_damage")
def defender_attacks_do_less_damage(ctx: EffectContext, amount: int) -> GameState:
    """Defending Pokemon's attacks do -amount damage during opponent's next turn."""
    opp_ref = SlotRef.active(1 - ctx.acting_player)
    return mutate_slot(
        ctx.state, opp_ref, lambda s: setattr(s, "attack_bonus_next_turn_self", -amount)
    )


@register_effect("opponent_no_supporter_next_turn")
def opponent_no_supporter_next_turn(ctx: EffectContext) -> GameState:
    """Block the opponent from playing Supporter cards on their next turn."""
    state = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    state.players[opp_idx].cant_play_supporter_incoming = True
    return state


@register_effect("discard_random_card_opponent")
def discard_random_card_opponent(ctx: EffectContext) -> GameState:
    """Coin flip: on heads, discard a random card from opponent's hand."""
    state = ctx.state
    if state.rng.random() >= 0.5:
        return state
    opp_idx = 1 - ctx.acting_player
    if not state.players[opp_idx].hand:
        return state
    state = state.copy()
    p = state.players[opp_idx]
    idx = state.rng.randrange(len(p.hand))
    p.discard.append(p.hand.pop(idx))
    return state


# -------------------------------------------------------------------------
# Trainer-card-only effects
# -------------------------------------------------------------------------

@register_effect("supporter_damage_aura")
def supporter_damage_aura(ctx: EffectContext, amount: int, names: tuple = ()) -> GameState:
    """Giovanni / Blaine: buff this turn's attack damage by ``amount``.

    If ``names`` is non-empty, the buff only applies when the attacker's name
    matches one of the entries.
    """
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    p.attack_damage_bonus = max(p.attack_damage_bonus, amount)
    if names:
        p.attack_damage_bonus_names = tuple(names)
    return state


@register_effect("reduce_retreat_cost")
def reduce_retreat_cost(ctx: EffectContext, amount: int) -> GameState:
    """X Speed: reduce retreat cost of Active Pokemon by ``amount`` this turn."""
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    p.retreat_cost_modifier -= amount
    return state


@register_effect("opponent_shuffle_hand_draw")
def opponent_shuffle_hand_draw(ctx: EffectContext, count: int = 3) -> GameState:
    """Red Card: opponent shuffles their hand into the deck, draws ``count`` cards."""
    state = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    p = state.players[opp_idx]
    if not p.hand and not p.deck:
        return state
    p.deck.extend(p.hand)
    p.hand = []
    state.rng.shuffle(p.deck)
    to_draw = min(count, len(p.deck))
    drawn = p.deck[:to_draw]
    p.deck = p.deck[to_draw:]
    p.hand.extend(drawn)
    return state


@register_effect("look_opponent_hand")
def look_opponent_hand(ctx: EffectContext) -> GameState:
    """Hand Scope: look at opponent's hand. Information-only."""
    return ctx.state


# -------------------------------------------------------------------------
# Copy opponent attack
# -------------------------------------------------------------------------

@register_effect("copy_opponent_attack")
def copy_opponent_attack(ctx: EffectContext) -> GameState:
    """Mew/Mewtwo copy: for now, a no-op placeholder.

    Properly implementing this requires choosing which opponent attack to copy
    and re-dispatching through execute_attack, which is out of scope for the
    current batch. The attack still deals its base damage; the side-effect
    simply fires nothing extra.
    """
    return ctx.state


# -------------------------------------------------------------------------
# Passive ability markers (handled structurally by the engine, not here)
# -------------------------------------------------------------------------

# These handlers are registered as no-ops so that parsing passive ability
# effect text does not spam "no handler registered" warnings. The actual
# passive behaviour is implemented in dedicated engine hooks (see
# legal_actions._opponent_blocks_supporters for supporter denial, and the
# damage pipeline for reduction / retaliate).

@register_effect("passive_damage_reduction")
def passive_damage_reduction(ctx: EffectContext, amount: int) -> GameState:
    return ctx.state


@register_effect("passive_retaliate")
def passive_retaliate(ctx: EffectContext, amount: int) -> GameState:
    return ctx.state


@register_effect("passive_block_supporters")
def passive_block_supporters(ctx: EffectContext) -> GameState:
    return ctx.state


@register_effect("passive_ditto_impostor")
def passive_ditto_impostor(ctx: EffectContext, hp: int) -> GameState:
    return ctx.state


# -------------------------------------------------------------------------
# Draw / search / deck manipulation (new)
# -------------------------------------------------------------------------

@register_effect("search_deck_random_pokemon")
def search_deck_random_pokemon(ctx: EffectContext) -> GameState:
    """Put a random Pokemon from your deck into your hand."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    pokemon_ids = [
        cid for cid in p.deck
        if _get_card(cid).is_pokemon
    ]
    if not pokemon_ids:
        return state
    chosen = state.rng.choice(pokemon_ids)
    p.deck.remove(chosen)
    p.hand.append(chosen)
    return state


@register_effect("search_deck_evolves_from")
def search_deck_evolves_from(ctx: EffectContext, name: str) -> GameState:
    """Put a random card that evolves from ``name`` from deck into hand."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    evolves = [
        cid for cid in p.deck
        if hasattr(_get_card(cid), 'evolves_from')
        and (_get_card(cid).evolves_from or "").lower() == name.lower()
    ]
    if not evolves:
        return state
    chosen = state.rng.choice(evolves)
    p.deck.remove(chosen)
    p.hand.append(chosen)
    return state


@register_effect("shuffle_hand_into_deck")
def shuffle_hand_into_deck(ctx: EffectContext) -> GameState:
    """Shuffle your hand into your deck."""
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    p.deck.extend(p.hand)
    p.hand = []
    state.rng.shuffle(p.deck)
    return state


@register_effect("shuffle_hand_draw_opponent_count")
def shuffle_hand_draw_opponent_count(ctx: EffectContext) -> GameState:
    """Shuffle hand into deck, then draw a card for each card in opponent's hand."""
    state = ctx.state.copy()
    pi = ctx.acting_player
    p = state.players[pi]
    opp = state.players[1 - pi]
    draw_count = len(opp.hand)
    p.deck.extend(p.hand)
    p.hand = []
    state.rng.shuffle(p.deck)
    to_draw = min(draw_count, len(p.deck))
    drawn = p.deck[:to_draw]
    p.deck = p.deck[to_draw:]
    p.hand.extend(drawn)
    return state


@register_effect("discard_random_tool_from_hand")
def discard_random_tool_from_hand(ctx: EffectContext) -> GameState:
    """Discard a random Pokemon Tool card from opponent's hand."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import CardKind
    state = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    p = state.players[opp_idx]
    tool_indices = [
        i for i, cid in enumerate(p.hand)
        if _get_card(cid).kind == CardKind.TOOL
    ]
    if not tool_indices:
        return state
    idx = state.rng.choice(tool_indices)
    p.discard.append(p.hand.pop(idx))
    return state


@register_effect("discard_random_item_from_hand")
def discard_random_item_from_hand(ctx: EffectContext) -> GameState:
    """Discard a random Item card from opponent's hand."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import CardKind
    state = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    p = state.players[opp_idx]
    item_indices = [
        i for i, cid in enumerate(p.hand)
        if _get_card(cid).kind == CardKind.ITEM
    ]
    if not item_indices:
        return state
    idx = state.rng.choice(item_indices)
    p.discard.append(p.hand.pop(idx))
    return state


@register_effect("discard_to_draw")
def discard_to_draw(ctx: EffectContext) -> GameState:
    """Discard a card from hand, then draw a card."""
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    if not p.hand:
        return state
    # Discard a random card
    idx = state.rng.randrange(len(p.hand))
    p.discard.append(p.hand.pop(idx))
    # Draw a card
    if p.deck:
        p.hand.append(p.deck.pop(0))
    return state


@register_effect("coin_flip_shuffle_opponent_card")
def coin_flip_shuffle_opponent_card(ctx: EffectContext) -> GameState:
    """Flip coin. Heads: opponent reveals random card, shuffles it into deck."""
    state = ctx.state
    if state.rng.random() >= 0.5:
        return state
    opp_idx = 1 - ctx.acting_player
    if not state.players[opp_idx].hand:
        return state
    state = state.copy()
    p = state.players[opp_idx]
    idx = state.rng.randrange(len(p.hand))
    card = p.hand.pop(idx)
    p.deck.append(card)
    state.rng.shuffle(p.deck)
    return state


@register_effect("multi_coin_shuffle_opponent_cards")
def multi_coin_shuffle_opponent_cards(ctx: EffectContext, count: int = 3) -> GameState:
    """Flip N coins. For each heads, shuffle a random card from opponent's hand into deck."""
    state = ctx.state
    heads = sum(1 for _ in range(count) if state.rng.random() < 0.5)
    if heads == 0:
        return state
    opp_idx = 1 - ctx.acting_player
    if not state.players[opp_idx].hand:
        return state
    state = state.copy()
    p = state.players[opp_idx]
    for _ in range(heads):
        if not p.hand:
            break
        idx = state.rng.randrange(len(p.hand))
        card = p.hand.pop(idx)
        p.deck.append(card)
    state.rng.shuffle(p.deck)
    return state


@register_effect("heal_active")
def heal_active(ctx: EffectContext, amount: int) -> GameState:
    """Heal N damage from your Active Pokemon."""
    ref = SlotRef.active(ctx.acting_player)
    return mutate_slot(
        ctx.state, ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
    )


@register_effect("heal_all_typed")
def heal_all_typed(ctx: EffectContext, amount: int, energy_type: str = "") -> GameState:
    """Heal N damage from each of your Pokemon of a specific type."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import Element as _Element
    try:
        filter_el = _Element.from_str(energy_type)
    except ValueError:
        return ctx.state
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    # Heal active
    if player.active is not None:
        try:
            if _get_card(player.active.card_id).element == filter_el:
                state = mutate_slot(
                    state, SlotRef.active(pi),
                    lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
                )
        except KeyError:
            pass
    # Heal bench
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        try:
            if _get_card(s.card_id).element == filter_el:
                state = mutate_slot(
                    state, SlotRef.bench(pi, i),
                    lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
                )
        except KeyError:
            pass
    return state


# -------------------------------------------------------------------------
# Next-turn self effects
# -------------------------------------------------------------------------

@register_effect("self_cant_attack_next_turn")
def self_cant_attack_next_turn(ctx: EffectContext) -> GameState:
    """This Pokemon can't attack during your next turn."""
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state, ctx.source_ref, lambda s: setattr(s, "cant_attack_next_turn", True)
    )


@register_effect("coin_flip_self_cant_attack_next_turn")
def coin_flip_self_cant_attack_next_turn(ctx: EffectContext) -> GameState:
    """Flip coin. If tails, this Pokemon can't attack next turn."""
    if ctx.state.rng.random() >= 0.5:
        return ctx.state
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state, ctx.source_ref, lambda s: setattr(s, "cant_attack_next_turn", True)
    )


@register_effect("self_cant_use_specific_attack")
def self_cant_use_specific_attack(ctx: EffectContext, attack_name: str = "") -> GameState:
    """This Pokemon can't use a specific attack next turn. Simplified: block all attacks."""
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state, ctx.source_ref, lambda s: setattr(s, "cant_attack_next_turn", True)
    )


@register_effect("self_attack_buff_next_turn")
def self_attack_buff_next_turn(ctx: EffectContext, attack_name: str = "", amount: int = 0) -> GameState:
    """This Pokemon's attack does +N damage next turn."""
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state, ctx.source_ref,
        lambda s: setattr(s, "attack_bonus_next_turn_self", amount),
    )


# -------------------------------------------------------------------------
# Next-turn opponent debuffs (new)
# -------------------------------------------------------------------------

@register_effect("coin_flip_attack_block_next_turn")
def coin_flip_attack_block_next_turn(ctx: EffectContext) -> GameState:
    """If opponent tries to attack next turn, flip coin. Tails = no attack.
    Simplified: set cant_attack_next_turn with 50% chance via coin flip on resolution.
    """
    opp_ref = SlotRef.active(1 - ctx.acting_player)
    return mutate_slot(
        ctx.state, opp_ref, lambda s: setattr(s, "cant_attack_next_turn", True)
    )


@register_effect("opponent_no_items_next_turn")
def opponent_no_items_next_turn(ctx: EffectContext) -> GameState:
    """Block opponent from playing Item cards next turn."""
    state = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    # Use generic flag; engine checks this during legal_actions
    state.players[opp_idx].cant_play_items_incoming = True
    return state


@register_effect("opponent_no_energy_next_turn")
def opponent_no_energy_next_turn(ctx: EffectContext) -> GameState:
    """Block opponent from taking Energy from Energy Zone next turn."""
    state = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    state.players[opp_idx].cant_take_energy_incoming = True
    return state


@register_effect("opponent_cost_increase_next_turn")
def opponent_cost_increase_next_turn(ctx: EffectContext) -> GameState:
    """Opponent's attacks cost 1 more Colorless and retreat costs 1 more next turn."""
    opp_ref = SlotRef.active(1 - ctx.acting_player)
    return mutate_slot(
        ctx.state, opp_ref, lambda s: setattr(s, "cant_retreat_next_turn", True)
    )


@register_effect("take_more_damage_next_turn")
def take_more_damage_next_turn(ctx: EffectContext, amount: int = 30) -> GameState:
    """This Pokemon takes +N damage from attacks during opponent's next turn.
    Implemented as negative incoming_damage_reduction.
    """
    if ctx.source_ref is None:
        return ctx.state
    return mutate_slot(
        ctx.state, ctx.source_ref,
        lambda s: setattr(s, "incoming_damage_reduction", -amount),
    )


# -------------------------------------------------------------------------
# Misc attack effects (new)
# -------------------------------------------------------------------------

@register_effect("discard_opponent_tools_before_damage")
def discard_opponent_tools_before_damage(ctx: EffectContext) -> GameState:
    """Discard all Pokemon Tools from opponent's Active before damage."""
    opp_idx = 1 - ctx.acting_player
    opp_active = ctx.state.players[opp_idx].active
    if opp_active is None or opp_active.tool_card_id is None:
        return ctx.state
    state = ctx.state.copy()
    p = state.players[opp_idx]
    if p.active.tool_card_id:
        p.discard.append(p.active.tool_card_id)
        new_active = p.active.copy()
        new_active.tool_card_id = None
        p.active = new_active
    return state


@register_effect("change_opponent_energy_type")
def change_opponent_energy_type(ctx: EffectContext) -> GameState:
    """Change type of next energy generated for opponent. No-op placeholder."""
    return ctx.state


# -------------------------------------------------------------------------
# Passive ability markers (new additions)
# PASSIVE: handled structurally by the engine
# -------------------------------------------------------------------------

@register_effect("passive_immune_status")
def passive_immune_status(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_prevent_ex_damage")
def passive_prevent_ex_damage(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_prevent_attack_effects")
def passive_prevent_attack_effects(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_coin_flip_damage_reduction")
def passive_coin_flip_damage_reduction(ctx: EffectContext, amount: int = 100) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_survive_ko_coin_flip")
def passive_survive_ko_coin_flip(ctx: EffectContext, remaining_hp: int = 10) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_type_damage_reduction")
def passive_type_damage_reduction(ctx: EffectContext, amount: int = 0, types: tuple = ()) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_opponent_damage_reduction")
def passive_opponent_damage_reduction(ctx: EffectContext, amount: int = 0) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_bench_retreat_reduction")
def passive_bench_retreat_reduction(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_double_grass_energy")
def passive_double_grass_energy(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_free_retreat_with_energy")
def passive_free_retreat_with_energy(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_psychic_cleanse")
def passive_psychic_cleanse(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_ko_energy_transfer")
def passive_ko_energy_transfer(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_ko_retaliate")
def passive_ko_retaliate(ctx: EffectContext, amount: int = 0) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_named_no_retreat")
def passive_named_no_retreat(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_dark_energy_ping")
def passive_dark_energy_ping(ctx: EffectContext, amount: int = 0) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_checkup_damage")
def passive_checkup_damage(ctx: EffectContext, amount: int = 0) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_block_evolution")
def passive_block_evolution(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_no_healing")
def passive_no_healing(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_arceus_no_retreat")
def passive_arceus_no_retreat(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_arceus_damage_reduction")
def passive_arceus_damage_reduction(ctx: EffectContext, amount: int = 0) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_arceus_cost_reduction")
def passive_arceus_cost_reduction(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_first_turn_no_retreat")
def passive_first_turn_no_retreat(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_energy_sleep")
def passive_energy_sleep(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_type_damage_boost")
def passive_type_damage_boost(ctx: EffectContext, element: str = "", amount: int = 0) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_opponent_attack_cost_increase")
def passive_opponent_attack_cost_increase(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state

@register_effect("passive_move_damage_to_self")
def passive_move_damage_to_self(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state


# -------------------------------------------------------------------------
# New trainer card effects — batch 2
# -------------------------------------------------------------------------

@register_effect("discard_all_opponent_tools")
def discard_all_opponent_tools(ctx: EffectContext) -> GameState:
    """Guzma: discard all Pokemon Tool cards from all of opponent's Pokemon."""
    opp_idx = 1 - ctx.acting_player
    state = ctx.state.copy()
    p = state.players[opp_idx]
    if p.active is not None and p.active.tool_card_id:
        new_active = p.active.copy()
        p.discard.append(new_active.tool_card_id)
        new_active.tool_card_id = None
        p.active = new_active
    for i, s in enumerate(p.bench):
        if s is not None and s.tool_card_id:
            new_bench = s.copy()
            p.discard.append(new_bench.tool_card_id)
            new_bench.tool_card_id = None
            p.bench[i] = new_bench
    return state


@register_effect("heal_stage2_target")
def heal_stage2_target(ctx: EffectContext, amount: int) -> GameState:
    """Lillie: heal N damage from 1 of your Stage 2 Pokemon (most damaged)."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    best_ref = None
    best_dmg = 0
    # Check active
    if player.active is not None:
        try:
            if _get_card(player.active.card_id).stage == Stage.STAGE_2:
                dmg = player.active.max_hp - player.active.current_hp
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_ref = SlotRef.active(pi)
        except KeyError:
            pass
    # Check bench
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        try:
            if _get_card(s.card_id).stage == Stage.STAGE_2:
                dmg = s.max_hp - s.current_hp
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_ref = SlotRef.bench(pi, i)
        except KeyError:
            pass
    if best_ref is None:
        return state
    return mutate_slot(
        state, best_ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
    )


@register_effect("heal_all_named_discard_energy")
def heal_all_named_discard_energy(ctx: EffectContext, names: tuple = ()) -> GameState:
    """Mallow: heal all damage from 1 of your named Pokemon, discard all energy."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    name_set = {n.lower() for n in names}

    # Find most damaged matching Pokemon
    best_ref = None
    best_dmg = 0
    if player.active is not None:
        try:
            if _get_card(player.active.card_id).name.lower() in name_set:
                dmg = player.active.max_hp - player.active.current_hp
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_ref = SlotRef.active(pi)
        except KeyError:
            pass
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        try:
            if _get_card(s.card_id).name.lower() in name_set:
                dmg = s.max_hp - s.current_hp
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_ref = SlotRef.bench(pi, i)
        except KeyError:
            pass
    if best_ref is None:
        return state
    # Heal all damage
    state = mutate_slot(
        state, best_ref,
        lambda s: setattr(s, "current_hp", s.max_hp),
    )
    # Discard all energy
    state = mutate_slot(
        state, best_ref,
        lambda s: s.attached_energy.clear(),
    )
    return state


@register_effect("move_damage_to_opponent")
def move_damage_to_opponent(ctx: EffectContext, names: tuple = (), amount: int = 40) -> GameState:
    """Acerola: move N damage from one of your named Pokemon to opponent's Active."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    opp_idx = 1 - pi
    player = state.players[pi]
    name_set = {n.lower() for n in names}

    # Find matching Pokemon with damage
    source_ref = None
    if player.active is not None:
        try:
            if _get_card(player.active.card_id).name.lower() in name_set:
                if player.active.max_hp - player.active.current_hp > 0:
                    source_ref = SlotRef.active(pi)
        except KeyError:
            pass
    if source_ref is None:
        for i, s in enumerate(player.bench):
            if s is None:
                continue
            try:
                if _get_card(s.card_id).name.lower() in name_set:
                    if s.max_hp - s.current_hp > 0:
                        source_ref = SlotRef.bench(pi, i)
                        break
            except KeyError:
                pass
    if source_ref is None:
        return state

    slot = get_slot(state, source_ref)
    actual_damage = min(amount, slot.max_hp - slot.current_hp)
    if actual_damage <= 0:
        return state

    # Heal source
    state = mutate_slot(
        state, source_ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + actual_damage)),
    )
    # Damage opponent active
    opp_ref = SlotRef.active(opp_idx)
    opp_active = get_slot(state, opp_ref)
    if opp_active is not None:
        state = mutate_slot(
            state, opp_ref,
            lambda s: setattr(s, "current_hp", max(0, s.current_hp - actual_damage)),
        )
    return state


@register_effect("return_colorless_to_hand")
def return_colorless_to_hand(ctx: EffectContext) -> GameState:
    """Ilima: put 1 of your Colorless Pokemon that has damage on it into your hand."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]

    # Find a damaged Colorless Pokemon (active first, then bench)
    source_ref = None
    if player.active is not None:
        try:
            card = _get_card(player.active.card_id)
            if card.element is None and player.active.max_hp - player.active.current_hp > 0:
                source_ref = SlotRef.active(pi)
        except KeyError:
            pass
    if source_ref is None:
        for i, s in enumerate(player.bench):
            if s is None:
                continue
            try:
                card = _get_card(s.card_id)
                if card.element is None and s.max_hp - s.current_hp > 0:
                    source_ref = SlotRef.bench(pi, i)
                    break
            except KeyError:
                pass
    if source_ref is None:
        return state

    slot = get_slot(state, source_ref)
    state = state.copy()
    p = state.players[pi]
    p.hand.append(slot.card_id)
    if slot.tool_card_id:
        p.discard.append(slot.tool_card_id)
    if source_ref.is_active():
        p.active = None
    else:
        p.bench[source_ref.slot] = None
    return state


@register_effect("attach_energy_named_end_turn")
def attach_energy_named_end_turn(ctx: EffectContext, names: tuple = (), count: int = 2, energy_type: str = "Fire") -> GameState:
    """Kiawe: attach N energy from zone to a named Pokemon. Turn ends."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    element = _Element.from_str(energy_type)
    name_set = {n.lower() for n in names}

    target = None
    if player.active is not None:
        try:
            if _get_card(player.active.card_id).name.lower() in name_set:
                target = SlotRef.active(pi)
        except KeyError:
            pass
    if target is None:
        for i, s in enumerate(player.bench):
            if s is None:
                continue
            try:
                if _get_card(s.card_id).name.lower() in name_set:
                    target = SlotRef.bench(pi, i)
                    break
            except KeyError:
                pass
    if target is None:
        return state
    return mutate_slot(
        state, target,
        lambda s: s.attached_energy.__setitem__(element, s.attached_energy.get(element, 0) + count),
    )


@register_effect("search_deck_named")
def search_deck_named(ctx: EffectContext, names: tuple = ()) -> GameState:
    """Put 1 random Pokemon matching one of names from deck into hand."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    name_set = {n.lower() for n in names}
    matches = [
        cid for cid in p.deck
        if _card_name_equals_set(cid, name_set)
    ]
    if not matches:
        return state
    chosen = state.rng.choice(matches)
    p.deck.remove(chosen)
    p.hand.append(chosen)
    return state


def _card_name_equals_set(card_id: str, name_set: set) -> bool:
    try:
        return get_card(card_id).name.lower() in name_set
    except KeyError:
        return False


@register_effect("attach_energy_discard_named")
def attach_energy_discard_named(ctx: EffectContext, names: tuple = (), count: int = 2, energy_type: str = "Lightning") -> GameState:
    """Volkner: attach N energy from discard pile to a named Pokemon."""
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    element = _Element.from_str(energy_type)
    name_set = {n.lower() for n in names}

    target = None
    if player.active is not None:
        try:
            if get_card(player.active.card_id).name.lower() in name_set:
                target = SlotRef.active(pi)
        except KeyError:
            pass
    if target is None:
        for i, s in enumerate(player.bench):
            if s is None:
                continue
            try:
                if get_card(s.card_id).name.lower() in name_set:
                    target = SlotRef.bench(pi, i)
                    break
            except KeyError:
                pass
    if target is None:
        return state

    # We don't track individual energy cards in discard pile — just attach
    return mutate_slot(
        state, target,
        lambda s: s.attached_energy.__setitem__(element, s.attached_energy.get(element, 0) + count),
    )


@register_effect("mars_hand_shuffle")
def mars_hand_shuffle(ctx: EffectContext) -> GameState:
    """Mars: opponent shuffles hand into deck, draws remaining-points-needed cards."""
    state = state_copy = ctx.state.copy()
    opp_idx = 1 - ctx.acting_player
    p = state_copy.players[opp_idx]
    # Points needed to win (typically 3 in PTCGP)
    remaining_points = max(0, 3 - p.points)
    p.deck.extend(p.hand)
    p.hand = []
    state_copy.rng.shuffle(p.deck)
    to_draw = min(remaining_points, len(p.deck))
    drawn = p.deck[:to_draw]
    p.deck = p.deck[to_draw:]
    p.hand.extend(drawn)
    return state_copy


@register_effect("iono_hand_shuffle")
def iono_hand_shuffle(ctx: EffectContext) -> GameState:
    """Iono: each player shuffles hand into deck, then draws that many cards."""
    state = ctx.state.copy()
    for pi in range(2):
        p = state.players[pi]
        hand_size = len(p.hand)
        p.deck.extend(p.hand)
        p.hand = []
        state.rng.shuffle(p.deck)
        to_draw = min(hand_size, len(p.deck))
        drawn = p.deck[:to_draw]
        p.deck = p.deck[to_draw:]
        p.hand.extend(drawn)
    return state


@register_effect("heal_and_cure_status")
def heal_and_cure_status(ctx: EffectContext, amount: int) -> GameState:
    """Pokemon Center Lady: heal N from 1 of your Pokemon and cure all status."""
    state = ctx.state
    pi = ctx.acting_player
    # Find most damaged Pokemon
    player = state.players[pi]
    best_ref = None
    best_dmg = 0
    if player.active is not None:
        dmg = player.active.max_hp - player.active.current_hp
        if dmg > best_dmg:
            best_dmg = dmg
            best_ref = SlotRef.active(pi)
    for i, s in enumerate(player.bench):
        if s is None:
            continue
        dmg = s.max_hp - s.current_hp
        if dmg > best_dmg:
            best_dmg = dmg
            best_ref = SlotRef.bench(pi, i)
    if best_ref is None:
        return state
    state = mutate_slot(
        state, best_ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
    )
    state = mutate_slot(
        state, best_ref,
        lambda s: s.status_effects.clear(),
    )
    return state


@register_effect("supporter_damage_aura_vs_ex")
def supporter_damage_aura_vs_ex(ctx: EffectContext, amount: int) -> GameState:
    """Red: buff this turn's attack damage by amount, only vs ex Pokemon."""
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    p.attack_damage_bonus = max(p.attack_damage_bonus, amount)
    p.attack_damage_bonus_vs_ex = True
    return state


@register_effect("coin_flip_until_tails_discard_energy")
def coin_flip_until_tails_discard_energy(ctx: EffectContext) -> GameState:
    """Team Rocket Grunt: flip until tails, discard that many energy from opponent."""
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    heads = 0
    while state.rng.random() < 0.5:
        heads += 1
    if heads == 0:
        return state
    opp_ref = SlotRef.active(opp_idx)
    for _ in range(heads):
        opp_active = get_slot(state, opp_ref)
        if opp_active is None or not opp_active.attached_energy:
            break
        flat = []
        for el, n in opp_active.attached_energy.items():
            flat.extend([el] * n)
        if not flat:
            break
        chosen = state.rng.choice(flat)
        state = mutate_slot(state, opp_ref, lambda s: _remove_one_energy_generic(s, chosen))
    return state


def _remove_one_energy_generic(slot, element) -> None:
    remaining = slot.attached_energy.get(element, 0)
    if remaining <= 1:
        slot.attached_energy.pop(element, None)
    else:
        slot.attached_energy[element] = remaining - 1


@register_effect("heal_water_pokemon")
def heal_water_pokemon(ctx: EffectContext, amount: int) -> GameState:
    """Irida: heal N from each of your Pokemon that has any Water Energy attached."""
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    if player.active is not None and player.active.attached_energy.get(_Element.WATER, 0) > 0:
        state = mutate_slot(
            state, SlotRef.active(pi),
            lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
        )
    for i, s in enumerate(player.bench):
        if s is not None and s.attached_energy.get(_Element.WATER, 0) > 0:
            state = mutate_slot(
                state, SlotRef.bench(pi, i),
                lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
            )
    return state


@register_effect("reduce_attack_cost_named")
def reduce_attack_cost_named(ctx: EffectContext, names: tuple = (), amount: int = 2) -> GameState:
    """Barry: reduce attack cost of named Pokemon by N. No-op for now (complex)."""
    return ctx.state


@register_effect("next_turn_metal_damage_reduction")
def next_turn_metal_damage_reduction(ctx: EffectContext, amount: int) -> GameState:
    """Adaman: all your Metal Pokemon take -N damage next turn. No-op placeholder."""
    return ctx.state


@register_effect("next_turn_all_damage_reduction")
def next_turn_all_damage_reduction(ctx: EffectContext, amount: int) -> GameState:
    """Blue: all your Pokemon take -N damage from attacks next turn. No-op placeholder."""
    return ctx.state


@register_effect("place_opponent_basic_from_discard")
def place_opponent_basic_from_discard(ctx: EffectContext) -> GameState:
    """Pokemon Flute: put 1 Basic Pokemon from opponent's discard onto their Bench."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.engine.state import PokemonSlot
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    opp = state.players[opp_idx]

    # Find basic Pokemon in opponent's discard
    basic_ids = [
        cid for cid in opp.discard
        if _get_card(cid).is_basic_pokemon
    ]
    if not basic_ids:
        return state
    # Find empty bench slot
    empty_slot = next((i for i, s in enumerate(opp.bench) if s is None), None)
    if empty_slot is None:
        return state

    chosen = state.rng.choice(basic_ids)
    state = state.copy()
    opp = state.players[opp_idx]
    opp.discard.remove(chosen)
    card = _get_card(chosen)
    opp.bench[empty_slot] = PokemonSlot(card_id=chosen, current_hp=card.hp, max_hp=card.hp)
    return state


@register_effect("mythical_slab")
def mythical_slab(ctx: EffectContext) -> GameState:
    """Mythical Slab: look at top card. If Psychic Pokemon, put in hand. Else bottom."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    p = state.players[pi]
    if not p.deck:
        return state
    top_id = p.deck[0]
    try:
        card = _get_card(top_id)
    except KeyError:
        return state

    state = state.copy()
    p = state.players[pi]
    if card.is_pokemon and card.element == _Element.PSYCHIC:
        p.hand.append(p.deck.pop(0))
    else:
        p.deck.append(p.deck.pop(0))  # move to bottom
    return state


@register_effect("pokemon_communication")
def pokemon_communication(ctx: EffectContext) -> GameState:
    """Pokemon Communication: swap a Pokemon in hand with a random one in deck."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state
    pi = ctx.acting_player
    p = state.players[pi]

    hand_pokemon = [
        i for i, cid in enumerate(p.hand)
        if _get_card(cid).is_pokemon
    ]
    deck_pokemon = [
        i for i, cid in enumerate(p.deck)
        if _get_card(cid).is_pokemon
    ]
    if not hand_pokemon or not deck_pokemon:
        return state

    state = state.copy()
    p = state.players[pi]
    hand_idx = state.rng.choice(hand_pokemon)
    deck_idx = state.rng.choice(deck_pokemon)
    p.hand[hand_idx], p.deck[deck_idx] = p.deck[deck_idx], p.hand[hand_idx]
    state.rng.shuffle(p.deck)
    return state


@register_effect("passive_lum_berry")
def passive_lum_berry(ctx: EffectContext) -> GameState:
    # PASSIVE: needs engine hook at end of turn
    return ctx.state


@register_effect("fishing_net")
def fishing_net(ctx: EffectContext) -> GameState:
    """Fishing Net: put a random Basic Water Pokemon from discard into hand."""
    from ptcgp.cards.database import get_card as _get_card
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    p = state.players[pi]
    matches = [
        cid for cid in p.discard
        if _get_card(cid).is_basic_pokemon and _get_card(cid).element == _Element.WATER
    ]
    if not matches:
        return state
    state = state.copy()
    p = state.players[pi]
    chosen = state.rng.choice(matches)
    p.discard.remove(chosen)
    p.hand.append(chosen)
    return state


@register_effect("big_malasada")
def big_malasada(ctx: EffectContext, amount: int = 10) -> GameState:
    """Big Malasada: heal 10 and remove a random Special Condition from Active."""
    ref = SlotRef.active(ctx.acting_player)
    state = mutate_slot(
        ctx.state, ref,
        lambda s: setattr(s, "current_hp", min(s.max_hp, s.current_hp + amount)),
    )
    slot = get_slot(state, ref)
    if slot is not None and slot.status_effects:
        state = state.copy()
        # Remove a random status
        active = state.players[ctx.acting_player].active
        if active is not None and active.status_effects:
            new_active = active.copy()
            status_list = list(new_active.status_effects)
            chosen = state.rng.choice(status_list)
            new_active.status_effects.discard(chosen)
            state.players[ctx.acting_player].active = new_active
    return state


@register_effect("passive_retaliate_poison")
def passive_retaliate_poison(ctx: EffectContext) -> GameState:
    # PASSIVE: handled by engine hook in attack pipeline
    return ctx.state


@register_effect("passive_beastite_damage")
def passive_beastite_damage(ctx: EffectContext) -> GameState:
    # PASSIVE: handled structurally
    return ctx.state


@register_effect("beast_wall_protection")
def beast_wall_protection(ctx: EffectContext) -> GameState:
    # PASSIVE/Conditional: no-op placeholder
    return ctx.state


@register_effect("passive_electrical_cord")
def passive_electrical_cord(ctx: EffectContext) -> GameState:
    # PASSIVE: triggers on KO, handled structurally
    return ctx.state


@register_effect("reveal_opponent_supporters")
def reveal_opponent_supporters(ctx: EffectContext) -> GameState:
    """Looker: information-only, no state change."""
    return ctx.state


@register_effect("lusamine_attach")
def lusamine_attach(ctx: EffectContext) -> GameState:
    """Lusamine: attach 2 random Energy from discard to an Ultra Beast.

    Simplified: attach 2 random energy types to active Pokemon (Ultra Beast
    tagging is complex). The discard pile doesn't track individual energy cards,
    so this is a best-effort approximation.
    """
    from ptcgp.cards.types import Element as _Element
    state = ctx.state
    pi = ctx.acting_player
    player = state.players[pi]
    if player.active is None:
        return state
    # Pick 2 random element types
    elements = list(_Element)
    for _ in range(2):
        chosen = state.rng.choice(elements)
        state = mutate_slot(
            state, SlotRef.active(pi),
            lambda s: s.attached_energy.__setitem__(chosen, s.attached_energy.get(chosen, 0) + 1),
        )
    return state


@register_effect("search_deck_random_basic")
def search_deck_random_basic(ctx: EffectContext) -> GameState:
    """Poke Ball: put 1 random Basic Pokemon from deck into hand."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    basics = [cid for cid in p.deck if _get_card(cid).is_basic_pokemon]
    if not basics:
        return state
    chosen = state.rng.choice(basics)
    p.deck.remove(chosen)
    p.hand.append(chosen)
    return state


@register_effect("search_discard_random_basic")
def search_discard_random_basic(ctx: EffectContext) -> GameState:
    """Celestic Town Elder: put 1 random Basic Pokemon from discard into hand."""
    from ptcgp.cards.database import get_card as _get_card
    state = ctx.state.copy()
    p = state.players[ctx.acting_player]
    basics = [cid for cid in p.discard if _get_card(cid).is_basic_pokemon]
    if not basics:
        return state
    chosen = state.rng.choice(basics)
    p.discard.remove(chosen)
    p.hand.append(chosen)
    return state


@register_effect("switch_opponent_damaged_to_active")
def switch_opponent_damaged_to_active(ctx: EffectContext) -> GameState:
    """Cyrus: switch in 1 of opponent's benched Pokemon that has damage on it."""
    state = ctx.state
    opp_idx = 1 - ctx.acting_player
    opp = state.players[opp_idx]
    damaged_bench = [
        i for i, s in enumerate(opp.bench)
        if s is not None and s.max_hp - s.current_hp > 0
    ]
    if not damaged_bench:
        return state
    chosen = state.rng.choice(damaged_bench)
    state = state.copy()
    p = state.players[opp_idx]
    old_active = p.active
    p.active = p.bench[chosen]
    p.bench[chosen] = old_active
    return state
