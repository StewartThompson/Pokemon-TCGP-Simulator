"""Draw effect handlers — draw_cards, draw_basic_pokemon, search_deck_grass_pokemon."""
from __future__ import annotations

from ptcgp.effects.registry import register_effect, EffectContext
from ptcgp.engine.state import GameState


@register_effect("draw_cards")
def draw_cards(ctx: EffectContext, count: int) -> GameState:
    """Draw `count` cards from deck to hand (Professor's Research).

    If fewer than `count` cards remain in deck, draw as many as available.
    """
    state = ctx.state
    player = state.players[ctx.acting_player]
    cards_to_draw = min(count, len(player.deck))
    if cards_to_draw == 0:
        return state
    state = state.copy()
    p = state.players[ctx.acting_player]
    drawn = p.deck[:cards_to_draw]
    p.deck = p.deck[cards_to_draw:]
    p.hand.extend(drawn)
    return state


@register_effect("search_deck_grass_pokemon")
def search_deck_grass_pokemon(ctx: EffectContext) -> GameState:
    """Put 1 random Grass Pokemon from deck into hand (Caterpie Find a Friend)."""
    from ptcgp.cards.database import get_card
    from ptcgp.cards.types import Element

    state = ctx.state
    state = state.copy()
    p = state.players[ctx.acting_player]

    grass_ids = [
        cid for cid in p.deck
        if get_card(cid).is_pokemon and get_card(cid).element == Element.GRASS
    ]
    if not grass_ids:
        return state

    chosen = state.rng.choice(grass_ids)
    p.deck.remove(chosen)
    p.hand.append(chosen)
    return state


@register_effect("draw_basic_pokemon")
def draw_basic_pokemon(ctx: EffectContext, count: int = 1) -> GameState:
    """Draw `count` random Basic Pokemon from deck to hand (Poke Ball)."""
    from ptcgp.cards.database import get_card
    from ptcgp.cards.types import Stage

    state = ctx.state
    state = state.copy()
    p = state.players[ctx.acting_player]

    # Find all Basic Pokemon in deck
    basic_ids = [
        cid for cid in p.deck
        if get_card(cid).is_pokemon and get_card(cid).stage == Stage.BASIC
    ]
    if not basic_ids:
        return state

    # Randomly pick `count` (or fewer if not enough)
    chosen = state.rng.sample(basic_ids, min(count, len(basic_ids)))
    for cid in chosen:
        p.deck.remove(cid)
        p.hand.append(cid)

    return state
