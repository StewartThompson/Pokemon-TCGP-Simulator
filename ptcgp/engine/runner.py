"""Game runner - plays a full game between two agents."""

from __future__ import annotations

from typing import Optional

from .game import (
    GameState, create_game, setup_active_pokemon, setup_bench_pokemon,
    start_game, get_legal_actions, apply_action, get_card,
)
from .types import EnergyType, GamePhase, ActionType, MAX_TURNS
from ..agents.base import Agent


def auto_setup(state: GameState, player_idx: int, agent: Agent) -> GameState:
    """Automatically handle the setup phase for a player."""
    player = state.players[player_idx]

    # Place the first Basic Pokemon as active
    basics_in_hand = [
        (i, cid) for i, cid in enumerate(player.hand)
        if get_card(cid).is_pokemon and get_card(cid).is_basic
    ]

    if not basics_in_hand:
        return state

    # Use agent to pick which Basic to put active (for now, just pick first)
    state = setup_active_pokemon(state, player_idx, basics_in_hand[0][0])

    # Place remaining Basics on bench
    player = state.players[player_idx]
    basics_in_hand = [
        (i, cid) for i, cid in enumerate(player.hand)
        if get_card(cid).is_pokemon and get_card(cid).is_basic
    ]

    for i, (hand_idx, _) in enumerate(basics_in_hand[:3]):  # Max 3 bench
        # Adjust index since we're removing from hand
        adjusted_idx = hand_idx - i
        if adjusted_idx >= 0 and adjusted_idx < len(state.players[player_idx].hand):
            try:
                state = setup_bench_pokemon(state, player_idx, adjusted_idx)
            except (ValueError, IndexError):
                break

    return state


def run_game(
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[EnergyType],
    energy_types2: list[EnergyType],
    agent1: Agent,
    agent2: Agent,
    seed: Optional[int] = None,
    debug: bool = False,
    max_turns: int = MAX_TURNS,
) -> tuple[GameState, Optional[int]]:
    """Run a full game between two agents.

    Returns:
        Tuple of (final_state, winner_index) where winner_index is 0, 1, or None (draw).
    """
    agents = [agent1, agent2]

    # Create game
    state = create_game(deck1, deck2, energy_types1, energy_types2, seed=seed)

    # Notify agents
    for i, agent in enumerate(agents):
        agent.on_game_start(state, i)

    # Setup phase
    for i in range(2):
        state = auto_setup(state, i, agents[i])

    # Verify both players have active Pokemon
    for i in range(2):
        if state.players[i].active.is_empty:
            # Can't play without an active pokemon
            state.phase = GamePhase.GAME_OVER
            state.winner = 1 - i
            for agent in agents:
                agent.on_game_end(state, state.winner)
            return state, state.winner

    # Start game
    state = start_game(state)

    # Main game loop
    turn_count = 0
    while state.phase != GamePhase.GAME_OVER and turn_count < max_turns * 2:
        turn_count += 1

        legal = get_legal_actions(state)
        if not legal:
            # No legal actions - force end turn
            state = apply_action(state, ActionType.END_TURN)
            continue

        # Determine which agent should act
        if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
            # Find which player needs to promote
            for p_idx in range(2):
                player = state.players[p_idx]
                if player.active.is_empty and any(not s.is_empty for s in player.bench):
                    action = agents[p_idx].choose_action(state, legal)
                    break
            else:
                action = legal[0]
        else:
            current_agent = agents[state.current_player]
            action = current_agent.choose_action(state, legal)

        if action not in legal:
            action = legal[0]  # Safety fallback

        if debug:
            print(f"Turn {state.turn_number} P{state.current_player}: {action.name}")

        state = apply_action(state, action)

    # Safety: if we hit max iterations without game over
    if state.phase != GamePhase.GAME_OVER:
        state.phase = GamePhase.GAME_OVER
        # Winner is whoever has more points, or draw
        if state.players[0].points > state.players[1].points:
            state.winner = 0
        elif state.players[1].points > state.players[0].points:
            state.winner = 1
        else:
            state.winner = None

    # Notify agents
    for agent in agents:
        agent.on_game_end(state, state.winner)

    return state, state.winner
