import random
from typing import List, Dict, Optional
import numpy as np
from gymnasium import Env, spaces
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from agents.agent import Agent

# RL Agent with Built-in Training
class RLAgent(Agent):
    def __init__(self, player: str):
        super().__init__(player)
        # Check environment compatibility
        check_env(self.env)
        # Train a PPO model in-memory
        self.model = PPO("MlpPolicy", self.env, verbose=0)
        self.model.learn(total_timesteps=10000)  # Short training for demo

    def get_action(self, state: Dict, valid_action_indices: List[int]) -> Optional[int]:
        if not valid_action_indices:
            return None
        obs = np.array([state["player_hp"], state["opponent_hp"], 
                       state["player_energy"], state["player_hand_energy"], 
                       state["turn"]], dtype=np.float32)
        action, _ = self.model.predict(obs)
        return action if action in valid_action_indices else random.choice(valid_action_indices)