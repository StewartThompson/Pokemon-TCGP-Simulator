"""Batch runner — runs multiple games in parallel and aggregates results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import multiprocessing as mp

from ptcgp.runner.game_runner import run_game
from ptcgp.cards.types import Element


@dataclass
class BatchResult:
    """Aggregated results from a batch of simulated games."""

    total_games: int
    wins: list[int]   # wins[0] = p1 wins, wins[1] = p2 wins
    ties: int
    errors: int

    @property
    def win_rate(self) -> tuple[float, float]:
        """Return (p1_win_rate, p2_win_rate) as fractions 0.0-1.0."""
        completed = self.total_games - self.errors
        if completed == 0:
            return (0.0, 0.0)
        return (self.wins[0] / completed, self.wins[1] / completed)

    @property
    def tie_rate(self) -> float:
        completed = self.total_games - self.errors
        return self.ties / completed if completed > 0 else 0.0


def _run_single_game(args):
    """Worker function for multiprocessing. args is a tuple."""
    (agent1_factory, agent2_factory, deck1, deck2,
     energy_types1, energy_types2, seed, max_steps) = args
    try:
        import ptcgp.effects  # ensure effects are registered in worker process
        from ptcgp.cards.database import load_defaults, is_loaded
        if not is_loaded():
            load_defaults()
        # Pass the game seed to agents so results are fully reproducible.
        # Agents that accept a ``seed`` keyword argument will use it; others
        # (e.g. HeuristicAgent) ignore it via kwargs.
        import inspect
        def _make_agent(factory, agent_seed):
            try:
                sig = inspect.signature(factory)
                if "seed" in sig.parameters:
                    return factory(seed=agent_seed)
            except (ValueError, TypeError):
                pass
            return factory()

        a1 = _make_agent(agent1_factory, seed)
        a2 = _make_agent(agent2_factory, seed + 1 if seed is not None else None)
        _, winner = run_game(
            a1, a2,
            list(deck1), list(deck2),
            list(energy_types1), list(energy_types2),
            seed=seed,
            max_steps=max_steps,
        )
        return winner
    except Exception:
        return "error"


def run_batch(
    agent1_factory: Callable,       # callable() -> Agent
    agent2_factory: Callable,       # callable() -> Agent
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[Element],
    energy_types2: list[Element],
    n_games: int,
    base_seed: int = 0,
    n_workers: int | None = None,   # None = use cpu_count
    max_steps: int = 10_000,
) -> BatchResult:
    """Run n_games games in parallel using multiprocessing.

    Each game gets seed = base_seed + game_index for reproducibility.
    Returns aggregated BatchResult.

    Parameters
    ----------
    agent1_factory : Callable that returns a new Agent instance for player 1.
                     Must be picklable (called in worker processes).
    agent2_factory : Callable that returns a new Agent instance for player 2.
                     Must be picklable (called in worker processes).
    deck1          : List of card IDs for player 1.
    deck2          : List of card IDs for player 2.
    energy_types1  : Energy types available to player 1.
    energy_types2  : Energy types available to player 2.
    n_games        : Number of games to simulate.
    base_seed      : Base seed; game i uses seed = base_seed + i.
    n_workers      : Number of worker processes (None = cpu_count).
    max_steps      : Hard limit per game before aborting.
    """
    args_list = [
        (agent1_factory, agent2_factory, deck1, deck2,
         energy_types1, energy_types2, base_seed + i, max_steps)
        for i in range(n_games)
    ]

    workers = n_workers if n_workers is not None else mp.cpu_count()

    wins = [0, 0]
    ties = 0
    errors = 0

    with mp.Pool(processes=workers) as pool:
        for result in pool.imap_unordered(_run_single_game, args_list):
            if result == "error":
                errors += 1
            elif result == 0:
                wins[0] += 1
            elif result == 1:
                wins[1] += 1
            else:
                ties += 1  # -1 or None

    return BatchResult(total_games=n_games, wins=wins, ties=ties, errors=errors)


def run_batch_simple(
    deck1_name: str = "grass",
    deck2_name: str = "fire",
    agent1_type: str = "random",    # "random" or "heuristic"
    agent2_type: str = "random",
    n_games: int = 100,
    base_seed: int = 0,
    n_workers: int | None = 1,
) -> BatchResult:
    """High-level batch runner using named decks and agents.

    Parameters
    ----------
    deck1_name  : Name of the deck for player 1 (e.g. ``"grass"``, ``"fire"``).
    deck2_name  : Name of the deck for player 2.
    agent1_type : Agent type for player 1: ``"random"`` or ``"heuristic"``.
    agent2_type : Agent type for player 2: ``"random"`` or ``"heuristic"``.
    n_games     : Number of games to simulate.
    base_seed   : Base seed for reproducibility.
    n_workers   : Number of worker processes (default 1 to avoid fork issues in
                  pytest; pass ``None`` to use all available CPUs).
    """
    from ptcgp.decks.sample_decks import get_sample_deck
    from ptcgp.agents.random_agent import RandomAgent
    from ptcgp.agents.heuristic import HeuristicAgent

    deck1, energy1 = get_sample_deck(deck1_name)
    deck2, energy2 = get_sample_deck(deck2_name)

    def make_factory(agent_type: str) -> Callable:
        if agent_type == "heuristic":
            return HeuristicAgent
        return RandomAgent

    agent1_factory = make_factory(agent1_type)
    agent2_factory = make_factory(agent2_type)

    return run_batch(
        agent1_factory=agent1_factory,
        agent2_factory=agent2_factory,
        deck1=deck1,
        deck2=deck2,
        energy_types1=energy1,
        energy_types2=energy2,
        n_games=n_games,
        base_seed=base_seed,
        n_workers=n_workers,
    )
