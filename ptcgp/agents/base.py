"""Base agent interface for PTCGP."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ptcgp.engine.game import GameState
from ptcgp.engine.types import ActionType


class Agent(ABC):
    """Base class for all PTCGP agents."""

    @abstractmethod
    def choose_action(self, state: GameState, legal_actions: list[ActionType]) -> ActionType:
        """Choose an action from the list of legal actions."""
        ...

    def on_game_start(self, state: GameState, player_idx: int) -> None:
        """Called when a game starts."""
        self.player_idx = player_idx

    def on_game_end(self, state: GameState, winner: int | None) -> None:
        """Called when a game ends."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
