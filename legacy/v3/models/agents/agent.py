import random
from typing import List, Dict, Optional
# import numpy as np  # Not needed for base Agent
# from gymnasium import Env, spaces  # Not needed for base Agent
# from stable_baselines3 import PPO  # Not needed for base Agent
# from stable_baselines3.common.env_checker import check_env  # Not needed for base Agent

# Agent Base Class
class Agent:
    def __init__(self, player: str):
        self.player = player
        self.is_human = False

    def get_action(self, state: Dict, valid_action_indices: List[int]) -> Optional[int]:
        raise NotImplementedError