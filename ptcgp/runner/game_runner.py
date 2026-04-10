"""Game runner — orchestrates a complete game between two agents."""
from __future__ import annotations

from typing import Optional

from ptcgp.cards.database import get_card
from ptcgp.cards.types import Element
from ptcgp.engine import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    advance_turn,
    apply_action,
    check_winner,
    create_game,
    get_legal_actions,
    get_legal_promotions,
)
from ptcgp.engine.setup import apply_setup_placement, draw_opening_hands, finalize_setup


def run_game(
    agent1,
    agent2,
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[Element],
    energy_types2: list[Element],
    seed: Optional[int] = None,
    max_steps: int = 10_000,
) -> tuple[GameState, Optional[int]]:
    """Run a complete game between two agents.

    Agents implement ``choose_action`` and may optionally provide
    ``choose_promotion``, ``choose_setup_placement``, ``on_game_start``, and
    ``on_game_end`` hooks.

    Returns
    -------
    (final_state, winner)
        ``winner`` is 0 / 1 (player index), ``-1`` (tie), or ``None`` if the
        game was aborted before a winner was determined.
    """
    state = create_game(deck1, deck2, energy_types1, energy_types2, seed)
    agents = [agent1, agent2]

    state = draw_opening_hands(state)

    # Coin flip — announce before placement so HumanAgent can show the result.
    state = state.copy()
    state.first_player = 0 if state.rng.random() < 0.5 else 1
    state.current_player = state.first_player

    for agent, idx in zip(agents, [0, 1]):
        if hasattr(agent, "on_game_start"):
            agent.on_game_start(state, idx)

    # Each agent chooses their Active + bench Pokemon.
    for pi, agent in enumerate(agents):
        basics = [cid for cid in state.players[pi].hand if _is_basic(cid)]
        if hasattr(agent, "choose_setup_placement"):
            active_id, bench_ids = agent.choose_setup_placement(state, pi, basics)
        else:
            active_id, bench_ids = basics[0], basics[1:]
        state = apply_setup_placement(state, pi, active_id, bench_ids)

    state = finalize_setup(state)

    steps = 0
    while check_winner(state) is None and steps < max_steps:
        steps += 1

        if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
            state = _handle_promotion(state, agents)
            continue

        legal = get_legal_actions(state)
        if not legal:
            break

        action = agents[state.current_player].choose_action(state, legal)
        state = apply_action(state, action)

        if action.kind in (ActionKind.ATTACK, ActionKind.END_TURN):
            if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
                continue  # promotion handled on next iteration
            if check_winner(state) is not None:
                break
            state = advance_turn(state)

    winner = check_winner(state)

    for agent, idx in zip(agents, [0, 1]):
        if hasattr(agent, "on_game_end"):
            agent.on_game_end(state, winner)

    return state, winner


def _handle_promotion(state: GameState, agents) -> GameState:
    """Prompt every player who has no Active to promote a bench Pokemon.

    A double-KO (e.g. attack KO + Rocky Helmet recoil) can leave both players
    without an Active simultaneously — loop until neither player needs a
    promotion before returning control to the turn flow.
    """
    while check_winner(state) is None:
        promoting_player: int | None = None
        if state.players[0].active is None and any(s is not None for s in state.players[0].bench):
            promoting_player = 0
        elif state.players[1].active is None and any(s is not None for s in state.players[1].bench):
            promoting_player = 1
        if promoting_player is None:
            break

        promotions = get_legal_promotions(state, promoting_player)
        if not promotions:
            # Edge case: handle_ko should have ended the game already.
            break

        agent = agents[promoting_player]
        if hasattr(agent, "choose_promotion"):
            action = agent.choose_promotion(state, promoting_player, promotions)
        else:
            action = promotions[0]
        # apply_action leaves the state in MAIN phase after PROMOTE, so we may
        # need to re-enter AWAITING_BENCH_PROMOTION for the other player on
        # the next loop iteration.
        state = apply_action(state, action)
        if state.players[0].active is None or state.players[1].active is None:
            # Second player still needs to promote — keep looping.
            state = state.copy()
            state.phase = GamePhase.AWAITING_BENCH_PROMOTION

    # If we broke out cleanly, carry on advancing the turn.
    if state.phase == GamePhase.MAIN and check_winner(state) is None:
        state = advance_turn(state)
    return state


def _is_basic(card_id: str) -> bool:
    try:
        return get_card(card_id).is_basic_pokemon
    except KeyError:
        return False
