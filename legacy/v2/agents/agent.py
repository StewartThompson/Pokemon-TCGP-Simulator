import random
from typing import List, Dict, Optional
import numpy as np
from gymnasium import Env, spaces
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env

# Agent Base Class
class Agent:
    def __init__(self, player: str):
        self.player = player
        self.is_human = False

    def get_action(self, state: Dict, valid_action_indices: List[int]) -> Optional[int]:
        raise NotImplementedError