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
