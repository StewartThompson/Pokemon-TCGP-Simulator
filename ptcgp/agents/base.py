"""Abstract base class for all game agents."""
from __future__ import annotations

import random
from abc import ABC, abstractmethod

from ptcgp.engine.state import GameState
from ptcgp.engine.actions import Action


class Agent(ABC):
    """Abstract base class for all game agents."""

    def on_game_start(self, state: GameState, player_index: int) -> None:
        """Called once at the start of a game. Override to initialize state."""
        pass

    def on_game_end(self, state: GameState, winner: int | None) -> None:
        """Called once at game end. Override to collect results."""
        pass

    @abstractmethod
    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        """Choose an action from the list of legal actions."""
        ...

    def choose_setup_placement(
        self,
        state: GameState,
        player_index: int,
        basics_in_hand: list[str],
    ) -> tuple[str, list[str]]:
        """Choose Active + bench Pokemon during the setup phase.

        Returns (active_card_id, bench_card_ids).
        Default: first basic → Active, remaining basics → bench.
        """
        return basics_in_hand[0], basics_in_hand[1:]

    def choose_promotion(
        self,
        state: GameState,
        player_index: int,
        legal_promotions: list[Action],
    ) -> Action:
        """Choose which bench Pokemon to promote after a KO. Default: random."""
        return random.choice(legal_promotions)
