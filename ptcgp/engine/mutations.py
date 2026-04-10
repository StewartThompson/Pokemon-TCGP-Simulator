"""Action dispatcher — applies a single action to the game state."""
from __future__ import annotations

from ptcgp.cards.database import get_card
from ptcgp.cards.types import CardKind, Stage
from ptcgp.engine.abilities import use_ability
from ptcgp.engine.actions import Action, ActionKind, SlotRef
from ptcgp.engine.attack import execute_attack
from ptcgp.engine.energy import attach_energy
from ptcgp.engine.evolve import evolve_pokemon
from ptcgp.engine.ko import handle_ko, promote_bench
from ptcgp.engine.play_card import attach_tool, play_basic, play_item, play_supporter
from ptcgp.engine.retreat import retreat
from ptcgp.engine.state import GameState


def apply_action(state: GameState, action: Action) -> GameState:
    """Dispatch action to the appropriate engine function. Returns new state.

    Does NOT handle turn transitions (that is the runner's job).
    For ATTACK and END_TURN, the runner must call:
        resolve_between_turns -> end_turn -> (if phase MAIN and no winner) start_turn
    For PROMOTE, the runner must handle turn ending after promotion if needed.
    """
    if action.kind == ActionKind.PLAY_CARD:
        return _dispatch_play_card(state, action)

    if action.kind == ActionKind.ATTACH_ENERGY:
        return attach_energy(state, action.target)

    if action.kind == ActionKind.EVOLVE:
        return evolve_pokemon(state, action.hand_index, action.target)

    if action.kind == ActionKind.USE_ABILITY:
        return use_ability(state, action.target)

    if action.kind == ActionKind.RETREAT:
        # retreat() takes bench_slot: int, not SlotRef
        return retreat(state, action.target.slot)

    if action.kind == ActionKind.ATTACK:
        state = execute_attack(state, action.attack_index, sub_target=action.target)
        # Check KOs: opponent first, then current player (for recoil / future effects)
        opponent_idx = state.opponent_index
        current_idx = state.current_player
        opponent_active = state.players[opponent_idx].active
        if opponent_active is not None and opponent_active.current_hp <= 0:
            state = handle_ko(state, SlotRef.active(opponent_idx))
        # Re-check in case game ended after opponent KO
        if state.winner is None:
            current_active = state.players[current_idx].active
            if current_active is not None and current_active.current_hp <= 0:
                state = handle_ko(state, SlotRef.active(current_idx))
        return state

    if action.kind == ActionKind.END_TURN:
        # No-op: runner is responsible for turn transitions
        return state

    if action.kind == ActionKind.PROMOTE:
        return promote_bench(state, action.target.player, action.target.slot)

    raise ValueError(f"Unknown ActionKind: {action.kind!r}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _dispatch_play_card(state: GameState, action: Action) -> GameState:
    """Dispatch PLAY_CARD to the correct sub-function based on card kind."""
    player = state.players[state.current_player]
    card_id = player.hand[action.hand_index]
    card = get_card(card_id)

    if card.kind == CardKind.POKEMON and card.stage == Stage.BASIC:
        return play_basic(state, action.hand_index, action.target.slot)

    if card.kind == CardKind.ITEM:
        return play_item(
            state,
            action.hand_index,
            target=action.target,
            extra_hand_index=action.extra_hand_index,
        )

    if card.kind == CardKind.SUPPORTER:
        return play_supporter(state, action.hand_index, target=action.target)

    if card.kind == CardKind.TOOL:
        return attach_tool(state, action.hand_index, action.target)

    raise ValueError(
        f"Cannot dispatch PLAY_CARD for card kind {card.kind!r} "
        f"(stage={card.stage!r}) — card: {card.name!r}"
    )
