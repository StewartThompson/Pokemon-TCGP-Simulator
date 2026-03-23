"""Training pipeline for PTCGP RL agents with MaskablePPO and curriculum learning."""

from __future__ import annotations

import os
import time
from typing import Optional

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from ptcgp.engine.types import EnergyType
from ptcgp.training.env import PTCGPEnv


def mask_fn(env: PTCGPEnv) -> np.ndarray:
    """Return the action mask for sb3-contrib's ActionMasker."""
    return env.action_masks()


class WinRateCallback(BaseCallback):
    """Evaluate win rate periodically during training."""

    def __init__(
        self,
        eval_env_fn,
        eval_freq: int = 2048,
        n_eval_games: int = 30,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.eval_env_fn = eval_env_fn
        self.eval_freq = eval_freq
        self.n_eval_games = n_eval_games
        self.win_rates: list[tuple[int, float]] = []
        self._eval_env = None

    def _on_step(self) -> bool:
        if self.n_calls % self.eval_freq == 0:
            if self._eval_env is None:
                self._eval_env = self.eval_env_fn()

            wins = 0
            total_reward = 0.0

            for ep in range(self.n_eval_games):
                obs, info = self._eval_env.reset(seed=ep + self.n_calls * 100)
                done = False
                ep_reward = 0.0
                while not done:
                    mask = info.get("action_mask", None)
                    action, _ = self.model.predict(
                        obs, deterministic=True,
                        action_masks=mask,
                    )
                    obs, reward, terminated, truncated, info = self._eval_env.step(int(action))
                    ep_reward += reward
                    done = terminated or truncated

                total_reward += ep_reward
                if ep_reward > 0:
                    wins += 1

            win_rate = wins / self.n_eval_games
            avg_reward = total_reward / self.n_eval_games
            self.win_rates.append((self.n_calls, win_rate))
            if self.verbose:
                print(f"  Step {self.n_calls:>6d}: win_rate={win_rate:.1%}  avg_reward={avg_reward:.3f}")

        return True


class CurriculumCallback(BaseCallback):
    """Switch opponent from random to heuristic after reaching a win rate threshold."""

    def __init__(
        self,
        win_rate_callback: WinRateCallback,
        threshold: float = 0.7,
        deck1: list[str] = None,
        deck2: list[str] = None,
        energy_types1: list[EnergyType] = None,
        energy_types2: list[EnergyType] = None,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.win_rate_cb = win_rate_callback
        self.threshold = threshold
        self.deck1 = deck1
        self.deck2 = deck2
        self.energy_types1 = energy_types1
        self.energy_types2 = energy_types2
        self.upgraded = False

    def _on_step(self) -> bool:
        if self.upgraded:
            return True

        if self.win_rate_cb.win_rates and self.win_rate_cb.win_rates[-1][1] >= self.threshold:
            if self.verbose:
                print(f"\n  >>> Curriculum upgrade: switching opponent to heuristic (win rate = {self.win_rate_cb.win_rates[-1][1]:.1%})")

            # Rebuild environments with heuristic opponent
            n_envs = len(self.training_env.envs)
            new_env_fns = [
                lambda i=i: ActionMasker(
                    PTCGPEnv(
                        deck1=self.deck1, deck2=self.deck2,
                        energy_types1=self.energy_types1, energy_types2=self.energy_types2,
                        opponent="heuristic",
                    ),
                    mask_fn,
                )
                for i in range(n_envs)
            ]
            # We can't easily swap envs mid-training with DummyVecEnv,
            # so just update the inner env's opponent
            for env in self.training_env.envs:
                inner = env
                while hasattr(inner, 'env'):
                    inner = inner.env
                if hasattr(inner, 'opponent'):
                    from ptcgp.agents.heuristic import HeuristicAgent
                    inner.opponent = HeuristicAgent()

            self.upgraded = True

        return True


def make_env(
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[EnergyType],
    energy_types2: list[EnergyType],
    opponent: str = "random",
    seed: int = 0,
) -> ActionMasker:
    """Create a PTCGP environment with action masking."""
    env = PTCGPEnv(
        deck1=deck1, deck2=deck2,
        energy_types1=energy_types1, energy_types2=energy_types2,
        opponent=opponent,
    )
    env._game_seed = seed
    return ActionMasker(env, mask_fn)


def evaluate_model(
    model: MaskablePPO,
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[EnergyType],
    energy_types2: list[EnergyType],
    opponent: str = "heuristic",
    n_games: int = 100,
) -> dict:
    """Evaluate a trained model against an opponent."""
    env = PTCGPEnv(
        deck1=deck1, deck2=deck2,
        energy_types1=energy_types1, energy_types2=energy_types2,
        opponent=opponent,
    )

    wins = 0
    losses = 0
    draws = 0
    total_reward = 0.0

    for ep in range(n_games):
        obs, info = env.reset(seed=ep)
        done = False
        ep_reward = 0.0
        while not done:
            mask = info.get("action_mask", None)
            action, _ = model.predict(obs, deterministic=True, action_masks=mask)
            obs, reward, terminated, truncated, info = env.step(int(action))
            ep_reward += reward
            done = terminated or truncated

        total_reward += ep_reward
        if ep_reward > 0:
            wins += 1
        elif ep_reward < 0:
            losses += 1
        else:
            draws += 1

    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / n_games,
        "avg_reward": total_reward / n_games,
        "n_games": n_games,
    }


def train_agent(
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[EnergyType],
    energy_types2: list[EnergyType],
    total_timesteps: int = 100_000,
    opponent: str = "random",
    n_envs: int = 4,
    learning_rate: float = 3e-4,
    save_path: str = "models/ppo_ptcgp",
    verbose: int = 1,
    curriculum: bool = True,
) -> MaskablePPO:
    """Train a MaskablePPO agent to play PTCGP.

    Key improvements over basic PPO:
    1. MaskablePPO ensures only legal actions are ever selected
    2. Curriculum learning: starts vs random, upgrades to heuristic
    3. Better hyperparameters tuned for card game dynamics
    """
    start_opponent = "random" if curriculum else opponent

    # Create vectorized environment with action masking
    env_fns = [
        lambda i=i: make_env(deck1, deck2, energy_types1, energy_types2, start_opponent, seed=i * 1000)
        for i in range(n_envs)
    ]
    vec_env = DummyVecEnv(env_fns)

    model = MaskablePPO(
        "MlpPolicy",
        vec_env,
        learning_rate=learning_rate,
        n_steps=512,          # More steps per update for card game (longer episodes)
        batch_size=128,        # Larger batch for stability
        n_epochs=6,            # More epochs per update
        gamma=0.995,           # High discount - card games are long-horizon
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.02,         # Higher entropy for exploration in large action space
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=0,
        policy_kwargs=dict(
            net_arch=dict(pi=[256, 256, 128], vf=[256, 256, 128]),
        ),
    )

    # Evaluation environment (always against heuristic for consistent measurement)
    eval_env_fn = lambda: PTCGPEnv(
        deck1=deck1, deck2=deck2,
        energy_types1=energy_types1, energy_types2=energy_types2,
        opponent="heuristic",
    )

    eval_freq = max(2048, total_timesteps // 20)  # ~20 eval points during training
    win_rate_cb = WinRateCallback(
        eval_env_fn=eval_env_fn,
        eval_freq=eval_freq,
        n_eval_games=30,
        verbose=verbose,
    )

    callbacks = [win_rate_cb]

    if curriculum:
        curriculum_cb = CurriculumCallback(
            win_rate_callback=win_rate_cb,
            threshold=0.65,
            deck1=deck1, deck2=deck2,
            energy_types1=energy_types1, energy_types2=energy_types2,
            verbose=verbose,
        )
        callbacks.append(curriculum_cb)

    if verbose:
        mode = "curriculum (random → heuristic)" if curriculum else opponent
        print(f"Training MaskablePPO for {total_timesteps:,} steps [{mode}]")
        print(f"  Envs: {n_envs}, LR: {learning_rate}, Arch: [256,256,128]")

    start_time = time.time()
    model.learn(total_timesteps=total_timesteps, callback=callbacks)
    elapsed = time.time() - start_time

    # Save model
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    model.save(save_path)

    if verbose:
        print(f"\nTraining complete in {elapsed:.1f}s")
        print(f"Model saved to {save_path}")

        # Final evaluation
        print("\nFinal evaluation vs heuristic:")
        results = evaluate_model(
            model, deck1, deck2, energy_types1, energy_types2,
            opponent="heuristic", n_games=100,
        )
        print(f"  Win rate: {results['win_rate']:.1%} "
              f"({results['wins']}W/{results['losses']}L/{results['draws']}D)")

    vec_env.close()
    return model


def load_agent(model_path: str) -> MaskablePPO:
    """Load a trained MaskablePPO agent."""
    return MaskablePPO.load(model_path)
