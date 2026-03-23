"""Simulation framework - run batches of games and collect statistics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

from ptcgp.engine.types import EnergyType
from ptcgp.engine.runner import run_game
from ptcgp.agents.base import Agent
from ptcgp.agents.random_agent import RandomAgent
from ptcgp.agents.heuristic import HeuristicAgent


@dataclass
class GameResult:
    """Result of a single game."""
    winner: Optional[int]
    turns: int
    points: tuple[int, int]
    seed: int


@dataclass
class SimulationResults:
    """Aggregated results from a simulation run."""
    n_games: int = 0
    wins: list[int] = field(default_factory=lambda: [0, 0])
    draws: int = 0
    total_turns: int = 0
    results: list[GameResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def win_rate_0(self) -> float:
        return self.wins[0] / max(self.n_games, 1)

    @property
    def win_rate_1(self) -> float:
        return self.wins[1] / max(self.n_games, 1)

    @property
    def draw_rate(self) -> float:
        return self.draws / max(self.n_games, 1)

    @property
    def avg_turns(self) -> float:
        return self.total_turns / max(self.n_games, 1)

    @property
    def games_per_second(self) -> float:
        return self.n_games / max(self.elapsed_seconds, 0.001)

    def summary(self) -> str:
        lines = [
            f"Simulation Results ({self.n_games} games)",
            f"  Player 1 wins: {self.wins[0]} ({self.win_rate_0:.1%})",
            f"  Player 2 wins: {self.wins[1]} ({self.win_rate_1:.1%})",
            f"  Draws: {self.draws} ({self.draw_rate:.1%})",
            f"  Avg turns: {self.avg_turns:.1f}",
            f"  Speed: {self.games_per_second:.0f} games/sec",
            f"  Total time: {self.elapsed_seconds:.1f}s",
        ]
        return "\n".join(lines)


def _run_single_game(args: tuple) -> GameResult:
    """Run a single game (for multiprocessing)."""
    deck1, deck2, etypes1, etypes2, agent_type1, agent_type2, seed = args

    # Reconstruct agents (can't pickle agent objects across processes)
    if agent_type1 == "random":
        a1 = RandomAgent(seed=seed)
    else:
        a1 = HeuristicAgent(seed=seed)

    if agent_type2 == "random":
        a2 = RandomAgent(seed=seed + 1)
    else:
        a2 = HeuristicAgent(seed=seed + 1)

    state, winner = run_game(deck1, deck2, etypes1, etypes2, a1, a2, seed=seed)

    return GameResult(
        winner=winner,
        turns=state.turn_number,
        points=(state.players[0].points, state.players[1].points),
        seed=seed,
    )


def simulate(
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[EnergyType],
    energy_types2: list[EnergyType],
    agent1: Agent | str = "heuristic",
    agent2: Agent | str = "heuristic",
    n_games: int = 100,
    parallel: bool = False,
    base_seed: int = 0,
) -> SimulationResults:
    """Run N games between two decks/agents and collect results.

    Args:
        deck1, deck2: Card ID lists for each deck
        energy_types1, energy_types2: Energy types for each deck
        agent1, agent2: Agent instances or "random"/"heuristic" strings
        n_games: Number of games to simulate
        parallel: Use multiprocessing for parallel execution
        base_seed: Starting seed for reproducibility
    """
    results = SimulationResults()
    start_time = time.time()

    # Resolve agent type strings
    def _agent_type(a) -> str:
        if isinstance(a, str):
            return a
        if isinstance(a, RandomAgent):
            return "random"
        return "heuristic"

    at1 = _agent_type(agent1)
    at2 = _agent_type(agent2)

    if parallel:
        args_list = [
            (deck1, deck2, energy_types1, energy_types2, at1, at2, base_seed + i)
            for i in range(n_games)
        ]

        with ProcessPoolExecutor() as executor:
            futures = [executor.submit(_run_single_game, args) for args in args_list]
            for future in as_completed(futures):
                result = future.result()
                results.results.append(result)
                results.n_games += 1
                results.total_turns += result.turns
                if result.winner is not None:
                    results.wins[result.winner] += 1
                else:
                    results.draws += 1
    else:
        for i in range(n_games):
            seed = base_seed + i

            if isinstance(agent1, Agent):
                a1 = agent1
            elif at1 == "random":
                a1 = RandomAgent(seed=seed)
            else:
                a1 = HeuristicAgent(seed=seed)

            if isinstance(agent2, Agent):
                a2 = agent2
            elif at2 == "random":
                a2 = RandomAgent(seed=seed + 1)
            else:
                a2 = HeuristicAgent(seed=seed + 1)

            state, winner = run_game(
                deck1, deck2, energy_types1, energy_types2,
                a1, a2, seed=seed,
            )

            result = GameResult(
                winner=winner,
                turns=state.turn_number,
                points=(state.players[0].points, state.players[1].points),
                seed=seed,
            )
            results.results.append(result)
            results.n_games += 1
            results.total_turns += result.turns
            if result.winner is not None:
                results.wins[result.winner] += 1
            else:
                results.draws += 1

    results.elapsed_seconds = time.time() - start_time
    return results
