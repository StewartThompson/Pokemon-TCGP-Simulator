"""Legal action generation for the battle engine."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.cards.types import CardKind, Stage
from ptcgp.effects.targeting import get_attack_sub_targets, get_play_targets
from ptcgp.engine.actions import Action, ActionKind, SlotRef
from ptcgp.engine.attack import can_pay_cost
from ptcgp.engine.slot_utils import get_slot
from ptcgp.engine.state import GamePhase, GameState, StatusEffect


def get_legal_actions(state: GameState) -> list[Action]:
    """Return all legal actions for the current player when phase == MAIN."""
    if state.phase != GamePhase.MAIN or state.winner is not None:
        return []

    actions: list[Action] = []
    player = state.current
    cp = state.current_player

    # ------------------------------------------------------------------ #
    # PLAY_CARD
    # ------------------------------------------------------------------ #
    for i, card_id in enumerate(player.hand):
        card = get_card(card_id)

        if card.kind == CardKind.POKEMON and card.stage == Stage.BASIC:
            # Play basic to each empty bench slot
            for j, slot in enumerate(player.bench):
                if slot is None:
                    actions.append(
                        Action(kind=ActionKind.PLAY_CARD, hand_index=i,
                               target=SlotRef.bench(cp, j))
                    )

        elif card.kind == CardKind.ITEM:
            if card.name == "Rare Candy":
                # Special-cased: enumerate (basic in play, stage 2 in hand) pairs.
                for rc_action in _rare_candy_actions(state, i):
                    actions.append(rc_action)
                continue
            for target in get_play_targets(card, cp, player):
                actions.append(
                    Action(kind=ActionKind.PLAY_CARD, hand_index=i, target=target)
                )

        elif card.kind == CardKind.SUPPORTER:
            if player.has_played_supporter:
                continue
            if player.cant_play_supporter_this_turn:
                continue
            if _opponent_blocks_supporters(state):
                continue
            for target in get_play_targets(card, cp, player):
                actions.append(
                    Action(kind=ActionKind.PLAY_CARD, hand_index=i, target=target)
                )

        elif card.kind == CardKind.TOOL:
            # Can attach to active (if not None) or any bench slot that has no tool
            if player.active is not None and player.active.tool_card_id is None:
                actions.append(
                    Action(kind=ActionKind.PLAY_CARD, hand_index=i,
                           target=SlotRef.active(cp))
                )
            for j, slot in enumerate(player.bench):
                if slot is not None and slot.tool_card_id is None:
                    actions.append(
                        Action(kind=ActionKind.PLAY_CARD, hand_index=i,
                               target=SlotRef.bench(cp, j))
                    )

    # ------------------------------------------------------------------ #
    # ATTACH_ENERGY
    # ------------------------------------------------------------------ #
    if player.energy_available is not None and not player.has_attached_energy:
        if player.active is not None:
            actions.append(
                Action(kind=ActionKind.ATTACH_ENERGY, target=SlotRef.active(cp))
            )
        for j, slot in enumerate(player.bench):
            if slot is not None:
                actions.append(
                    Action(kind=ActionKind.ATTACH_ENERGY, target=SlotRef.bench(cp, j))
                )

    # ------------------------------------------------------------------ #
    # EVOLVE  (not on turn 0 or 1)
    # ------------------------------------------------------------------ #
    if state.turn_number >= 2:
        for i, card_id in enumerate(player.hand):
            evo_card = get_card(card_id)
            if evo_card.kind != CardKind.POKEMON:
                continue
            if evo_card.stage not in (Stage.STAGE_1, Stage.STAGE_2):
                continue

            # Check active
            if player.active is not None:
                active_slot = player.active
                active_card = get_card(active_slot.card_id)
                if (evo_card.evolves_from == active_card.name
                        and active_slot.turns_in_play >= 1
                        and not active_slot.evolved_this_turn):
                    actions.append(
                        Action(kind=ActionKind.EVOLVE, hand_index=i,
                               target=SlotRef.active(cp))
                    )
            # Check bench
            for j, slot in enumerate(player.bench):
                if slot is None:
                    continue
                slot_card = get_card(slot.card_id)
                if (evo_card.evolves_from == slot_card.name
                        and slot.turns_in_play >= 1
                        and not slot.evolved_this_turn):
                    actions.append(
                        Action(kind=ActionKind.EVOLVE, hand_index=i,
                               target=SlotRef.bench(cp, j))
                    )

    # ------------------------------------------------------------------ #
    # USE_ABILITY
    # ------------------------------------------------------------------ #
    if player.active is not None:
        active_card = get_card(player.active.card_id)
        if (active_card.ability is not None
                and not active_card.ability.is_passive
                and not player.active.ability_used_this_turn):
            actions.append(
                Action(kind=ActionKind.USE_ABILITY, target=SlotRef.active(cp))
            )
    for j, slot in enumerate(player.bench):
        if slot is None:
            continue
        slot_card = get_card(slot.card_id)
        if (slot_card.ability is not None
                and not slot_card.ability.is_passive
                and not slot.ability_used_this_turn):
            actions.append(
                Action(kind=ActionKind.USE_ABILITY, target=SlotRef.bench(cp, j))
            )

    # ------------------------------------------------------------------ #
    # RETREAT
    # ------------------------------------------------------------------ #
    if (not player.has_retreated
            and player.active is not None
            and StatusEffect.PARALYZED not in player.active.status_effects
            and StatusEffect.ASLEEP not in player.active.status_effects):
        active_card = get_card(player.active.card_id)
        retreat_cost = active_card.retreat_cost
        if player.active.total_energy() >= retreat_cost:
            # Must have at least one bench Pokemon to swap in
            for j, slot in enumerate(player.bench):
                if slot is not None:
                    actions.append(
                        Action(kind=ActionKind.RETREAT,
                               target=SlotRef.bench(cp, j))
                    )

    # ------------------------------------------------------------------ #
    # ATTACK  (not on turn 0 or 1)
    # ------------------------------------------------------------------ #
    if (state.turn_number >= 2
            and player.active is not None
            and not player.active.cant_attack_next_turn
            and StatusEffect.PARALYZED not in player.active.status_effects
            and StatusEffect.ASLEEP not in player.active.status_effects):
        active_card = get_card(player.active.card_id)
        for i, attack in enumerate(active_card.attacks):
            if not can_pay_cost(player.active, attack.cost):
                continue
            # Attacks with a targeted side-effect (e.g. Lilligant Leaf Supply)
            # emit one Action per legal sub-target. Untargeted attacks emit a
            # single Action with target=None.
            for sub_target in get_attack_sub_targets(attack.effect_text, cp, player, handler_str=attack.handler, cached_effects=attack.cached_effects):
                actions.append(
                    Action(kind=ActionKind.ATTACK, attack_index=i, target=sub_target)
                )

    # ------------------------------------------------------------------ #
    # END_TURN — always available
    # ------------------------------------------------------------------ #
    actions.append(Action(kind=ActionKind.END_TURN))

    return actions


def _rare_candy_actions(state: GameState, rare_candy_hand_idx: int) -> list[Action]:
    """Enumerate legal Rare Candy plays for the current player.

    For each Basic Pokemon in play (that has been in play at least one turn
    and hasn't evolved this turn), find every Stage 2 card in hand whose
    evolution chain's Basic name matches, and emit one PLAY_CARD action per
    (basic target, stage 2 hand index) pair. Rare Candy itself is banned on
    the very first turn of the game — mirrors regular evolve timing.
    """
    from ptcgp.cards.database import get_basic_to_stage2
    cp = state.current_player
    player = state.current
    actions: list[Action] = []

    # Turn restriction: no evolving on turn 0 / 1 (same as regular evolve).
    if state.turn_number < 2:
        return actions

    # Use the DB-level cached map (built once at load_defaults) instead of
    # rebuilding it from scratch on every call.
    basic_to_stage2 = get_basic_to_stage2()

    def _enumerate_for_slot(slot_ref: SlotRef):
        slot = get_slot(state, slot_ref)
        if slot is None:
            return
        if slot.turns_in_play < 1 or slot.evolved_this_turn:
            return
        basic_card = get_card(slot.card_id)
        if basic_card.stage != Stage.BASIC:
            return
        reachable = basic_to_stage2.get(basic_card.name, set())
        if not reachable:
            return
        for hidx, cid in enumerate(player.hand):
            if hidx == rare_candy_hand_idx:
                continue
            try:
                hand_card = get_card(cid)
            except KeyError:
                continue
            if hand_card.stage != Stage.STAGE_2:
                continue
            if hand_card.name in reachable:
                actions.append(
                    Action(
                        kind=ActionKind.PLAY_CARD,
                        hand_index=rare_candy_hand_idx,
                        target=slot_ref,
                        extra_hand_index=hidx,
                    )
                )

    if player.active is not None:
        _enumerate_for_slot(SlotRef.active(cp))
    for j, s in enumerate(player.bench):
        if s is not None:
            _enumerate_for_slot(SlotRef.bench(cp, j))

    return actions


_SUPPORTER_BLOCK_TEXT = "can't use any supporter cards"


def _opponent_blocks_supporters(state: GameState) -> bool:
    """True if the opponent's Active Pokemon has a passive supporter-denial ability."""
    opp = state.players[1 - state.current_player]
    if opp.active is None:
        return False
    try:
        card = get_card(opp.active.card_id)
    except KeyError:
        return False
    ab = card.ability
    if ab is None or not ab.effect_text:
        return False
    text = ab.effect_text.lower()
    return _SUPPORTER_BLOCK_TEXT in text and "active spot" in text


def get_legal_promotions(state: GameState, player_index: int) -> list[Action]:
    """Return PROMOTE actions for the given player during AWAITING_BENCH_PROMOTION."""
    if state.phase != GamePhase.AWAITING_BENCH_PROMOTION:
        return []

    actions: list[Action] = []
    player = state.players[player_index]
    for j, slot in enumerate(player.bench):
        if slot is not None:
            actions.append(
                Action(kind=ActionKind.PROMOTE,
                       target=SlotRef.bench(player_index, j))
            )
    return actions
