from abc import ABC, abstractmethod
import random
from sb3_contrib import MaskablePPO
from agents.agent import Agent
from typing import Dict, List, Optional

class RandomAgent(Agent):

    """
    An agent that randomly selects a valid action.
    Useful for testing and as a baseline.
    """
    def get_action(self, state: Dict, valid_action_indices: List[int]) -> Optional[int]:
        return random.choice(valid_action_indices) if valid_action_indices else None