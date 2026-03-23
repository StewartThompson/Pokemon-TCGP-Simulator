"""Random agent - picks uniformly from legal actions."""

from __future__ import annotations

import random

from ptcgp.engine.game import GameState
from ptcgp.engine.types import ActionType
from .base import Agent


class RandomAgent(Agent):
    """Agent that picks a random legal action each turn."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def choose_action(self, state: GameState, legal_actions: list[ActionType]) -> ActionType:
        return self.rng.choice(legal_actions)
