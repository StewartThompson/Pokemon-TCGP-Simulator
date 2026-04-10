"""Functions for playing cards from hand."""
from __future__ import annotations

from typing import Optional

from ptcgp.cards.card import Card
from ptcgp.cards.database import get_card
from ptcgp.cards.types import CardKind, Stage
from ptcgp.engine.actions import SlotRef
from ptcgp.engine.slot_utils import get_slot
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot


def _take_from_hand(
    player: PlayerState,
    hand_index: int,
    expected_kind: Optional[CardKind] = None,
) -> Card:
    """Validate ``hand_index`` and return the card at that slot.

    Does NOT mutate the hand. Use after validation succeeds via ``player.hand.pop``.
    """
    if hand_index < 0 or hand_index >= len(player.hand):
        raise ValueError(
            f"Invalid hand_index {hand_index}: hand has {len(player.hand)} cards"
        )
    card = get_card(player.hand[hand_index])
    if expected_kind is not None and card.kind != expected_kind:
        raise ValueError(
            f"Card {card.name!r} is not a {expected_kind.name} card (kind: {card.kind})"
        )
    return card


def play_basic(state: GameState, hand_index: int, bench_slot: int) -> GameState:
    """Play a Basic Pokemon from hand to a specific bench slot."""
    state = state.copy()
    player = state.players[state.current_player]

    card = _take_from_hand(player, hand_index, CardKind.POKEMON)
    if card.stage != Stage.BASIC:
        raise ValueError(f"Card {card.name!r} is not a Basic Pokemon (stage: {card.stage})")

    if bench_slot < 0 or bench_slot >= len(player.bench):
        raise ValueError(f"Invalid bench_slot {bench_slot}")
    if player.bench[bench_slot] is not None:
        raise ValueError(f"Bench slot {bench_slot} is already occupied")

    player.hand.pop(hand_index)
    player.bench[bench_slot] = PokemonSlot(
        card_id=card.id,
        current_hp=card.hp,
        max_hp=card.hp,
        turns_in_play=0,
    )
    return state


def play_item(
    state: GameState,
    hand_index: int,
    target: Optional[SlotRef] = None,
    extra_hand_index: Optional[int] = None,
) -> GameState:
    """Play an Item card: discard it and resolve its trainer effect text.

    ``target`` (if provided) is passed through as ``target_ref`` to the effect
    handler — used by Potion and other ``heal 1 of your Pokémon`` items.
    ``extra_hand_index`` lets items like Rare Candy reference a second card
    in hand (the Stage 2 card to be consumed).
    """
    state = state.copy()
    player = state.players[state.current_player]

    card = _take_from_hand(player, hand_index, CardKind.ITEM)
    # Capture the extra card's ID (if any) BEFORE we pop Rare Candy from hand,
    # so the indices in the player's hand stay stable while we look it up.
    extra_card_id: Optional[str] = None
    if extra_hand_index is not None and 0 <= extra_hand_index < len(player.hand):
        extra_card_id = player.hand[extra_hand_index]

    player.hand.pop(hand_index)
    player.discard.append(card.id)

    # After popping Rare Candy, the stage 2 card's hand index may shift down
    # by one if it came after Rare Candy in the original hand.
    adjusted_extra_idx: Optional[int] = None
    if extra_hand_index is not None:
        if extra_hand_index > hand_index:
            adjusted_extra_idx = extra_hand_index - 1
        else:
            adjusted_extra_idx = extra_hand_index

    if card.trainer_effect_text or card.trainer_handler:
        from ptcgp.effects.apply import apply_effects
        extra: dict = {}
        if extra_card_id is not None:
            extra["evo_card_id"] = extra_card_id
            extra["evo_hand_index"] = adjusted_extra_idx
        state = apply_effects(
            state,
            card.trainer_effect_text,
            acting_player=state.current_player,
            target_ref=target,
            extra=extra,
            handler_str=card.trainer_handler,
            cached_effects=card.cached_trainer_effects,
        )
    return state


def play_supporter(
    state: GameState,
    hand_index: int,
    target: Optional[SlotRef] = None,
) -> GameState:
    """Play a Supporter card: discard, mark flag, resolve its effect text."""
    state = state.copy()
    player = state.players[state.current_player]

    card = _take_from_hand(player, hand_index, CardKind.SUPPORTER)
    player.hand.pop(hand_index)
    player.discard.append(card.id)
    player.has_played_supporter = True

    if card.trainer_effect_text or card.trainer_handler:
        from ptcgp.effects.apply import apply_effects
        state = apply_effects(
            state,
            card.trainer_effect_text,
            acting_player=state.current_player,
            target_ref=target,
            handler_str=card.trainer_handler,
            cached_effects=card.cached_trainer_effects,
        )
    return state


def attach_tool(state: GameState, hand_index: int, target: SlotRef) -> GameState:
    """Attach a Tool card to a Pokemon and apply its passive effect."""
    state = state.copy()
    player = state.players[state.current_player]

    card = _take_from_hand(player, hand_index, CardKind.TOOL)

    slot = get_slot(state, target)
    if slot is None:
        raise ValueError(f"No Pokemon in target slot {target}")
    if slot.tool_card_id is not None:
        raise ValueError(f"Target Pokemon already has a tool attached ({slot.tool_card_id!r})")

    player.hand.pop(hand_index)
    slot.tool_card_id = card.id

    if card.trainer_effect_text or card.trainer_handler:
        from ptcgp.effects.apply import apply_effects
        state = apply_effects(
            state,
            card.trainer_effect_text,
            acting_player=state.current_player,
            target_ref=target,
            handler_str=card.trainer_handler,
            cached_effects=card.cached_trainer_effects,
        )
    return state
