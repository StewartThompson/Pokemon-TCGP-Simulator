"""RandomAgent — chooses uniformly at random from legal actions."""
from __future__ import annotations

import random

from ptcgp.engine.state import GameState
from ptcgp.engine.actions import Action
from ptcgp.agents.base import Agent


class RandomAgent(Agent):
    """Chooses uniformly at random from legal actions."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        return self._rng.choice(legal_actions)

    def choose_promotion(
        self,
        state: GameState,
        player_index: int,
        legal_promotions: list[Action],
    ) -> Action:
        return self._rng.choice(legal_promotions)
