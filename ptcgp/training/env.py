"""Gymnasium environment for PTCGP reinforcement learning."""

from __future__ import annotations

from typing import Optional, Any

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from ptcgp.engine.game import (
    GameState, PokemonSlot, create_game, setup_active_pokemon, setup_bench_pokemon,
    start_game, get_legal_actions, apply_action, get_action_mask, get_card,
)
from ptcgp.engine.runner import auto_setup
from ptcgp.engine.types import (
    EnergyType, StatusEffect, GamePhase, ActionType, NUM_ACTIONS,
    BENCH_SIZE, MAX_HAND_SIZE, POINTS_TO_WIN,
)
from ptcgp.agents.base import Agent
from ptcgp.agents.random_agent import RandomAgent
from ptcgp.agents.heuristic import HeuristicAgent


# Observation space dimensions
NUM_ENERGY_TYPES = 8  # Excluding colorless
NUM_STATUS_EFFECTS = 5
SLOT_OBS_SIZE = 1 + 1 + NUM_ENERGY_TYPES + NUM_STATUS_EFFECTS + 1 + 1 + 1 + 1 + 1  # 20
# card_present, hp_ratio, 8 energy counts, 5 status flags, stage, is_ex, turns_in_play, retreat_cost, has_tool
NUM_POKEMON_SLOTS = 8  # 4 per player (active + 3 bench)
POKEMON_OBS_SIZE = NUM_POKEMON_SLOTS * SLOT_OBS_SIZE  # 160

HAND_OBS_SIZE = MAX_HAND_SIZE + 1  # 10 card types + hand_size = 11
PLAYER_OBS_SIZE = HAND_OBS_SIZE + 3  # hand + points + deck_size + energy_attached_flag
GLOBAL_OBS_SIZE = 1 + 1 + NUM_ENERGY_TYPES + 3  # turn, current_player, energy_zone, 3 flags

TOTAL_OBS_SIZE = POKEMON_OBS_SIZE + 2 * PLAYER_OBS_SIZE + GLOBAL_OBS_SIZE


def _encode_slot(slot: PokemonSlot) -> np.ndarray:
    """Encode a pokemon slot into a fixed-size observation vector."""
    obs = np.zeros(SLOT_OBS_SIZE, dtype=np.float32)

    if slot.is_empty:
        return obs

    obs[0] = 1.0  # card_present
    obs[1] = slot.current_hp / max(slot.max_hp, 1)  # hp_ratio

    # Energy counts (normalized)
    energy_types = [
        EnergyType.GRASS, EnergyType.FIRE, EnergyType.WATER, EnergyType.LIGHTNING,
        EnergyType.PSYCHIC, EnergyType.FIGHTING, EnergyType.DARKNESS, EnergyType.METAL,
    ]
    for i, etype in enumerate(energy_types):
        obs[2 + i] = min(slot.attached_energy.get(etype, 0) / 5.0, 1.0)

    # Status effects
    statuses = [StatusEffect.POISONED, StatusEffect.BURNED, StatusEffect.PARALYZED,
                StatusEffect.ASLEEP, StatusEffect.CONFUSED]
    for i, status in enumerate(statuses):
        obs[2 + NUM_ENERGY_TYPES + i] = 1.0 if status in slot.status_effects else 0.0

    card = slot.card
    if card:
        # Stage (0=basic, 0.5=stage1, 1=stage2)
        stage_val = {"basic": 0.0, "stage1": 0.5, "stage2": 1.0}
        obs[2 + NUM_ENERGY_TYPES + NUM_STATUS_EFFECTS] = stage_val.get(card.stage.value if card.stage else "basic", 0.0)
        obs[2 + NUM_ENERGY_TYPES + NUM_STATUS_EFFECTS + 1] = 1.0 if card.is_ex else 0.0
        obs[2 + NUM_ENERGY_TYPES + NUM_STATUS_EFFECTS + 2] = min(slot.turns_in_play / 10.0, 1.0)
        obs[2 + NUM_ENERGY_TYPES + NUM_STATUS_EFFECTS + 3] = card.retreat_cost / 4.0
        obs[2 + NUM_ENERGY_TYPES + NUM_STATUS_EFFECTS + 4] = 1.0 if slot.tool_card_id else 0.0

    return obs


def _encode_hand(hand: list[str], from_perspective: bool = True) -> np.ndarray:
    """Encode a hand. If not from_perspective (opponent), only encode size."""
    obs = np.zeros(HAND_OBS_SIZE, dtype=np.float32)
    obs[0] = len(hand) / MAX_HAND_SIZE  # hand size

    if from_perspective:
        # Encode card types in hand slots
        for i, card_id in enumerate(hand[:MAX_HAND_SIZE]):
            card = get_card(card_id)
            # Simple encoding: pokemon=0.25, item=0.5, supporter=0.75, tool=1.0
            type_val = {"pokemon": 0.25, "item": 0.5, "supporter": 0.75, "tool": 1.0}
            obs[1 + i] = type_val.get(card.card_type.value, 0.0)

    return obs


def encode_observation(state: GameState, player_idx: int) -> np.ndarray:
    """Encode the full game state as an observation vector from player_idx's perspective."""
    obs = np.zeros(TOTAL_OBS_SIZE, dtype=np.float32)
    offset = 0

    me = state.players[player_idx]
    opp = state.players[1 - player_idx]

    # My pokemon slots: active + bench
    obs[offset:offset + SLOT_OBS_SIZE] = _encode_slot(me.active)
    offset += SLOT_OBS_SIZE
    for slot in me.bench:
        obs[offset:offset + SLOT_OBS_SIZE] = _encode_slot(slot)
        offset += SLOT_OBS_SIZE

    # Opponent pokemon slots
    obs[offset:offset + SLOT_OBS_SIZE] = _encode_slot(opp.active)
    offset += SLOT_OBS_SIZE
    for slot in opp.bench:
        obs[offset:offset + SLOT_OBS_SIZE] = _encode_slot(slot)
        offset += SLOT_OBS_SIZE

    # My player state
    obs[offset:offset + HAND_OBS_SIZE] = _encode_hand(me.hand, from_perspective=True)
    offset += HAND_OBS_SIZE
    obs[offset] = me.points / POINTS_TO_WIN
    obs[offset + 1] = len(me.deck) / 20.0
    obs[offset + 2] = 1.0 if me.has_attached_energy else 0.0
    offset += 3

    # Opponent player state (hidden info: hand only shows size)
    obs[offset:offset + HAND_OBS_SIZE] = _encode_hand(opp.hand, from_perspective=False)
    offset += HAND_OBS_SIZE
    obs[offset] = opp.points / POINTS_TO_WIN
    obs[offset + 1] = len(opp.deck) / 20.0
    obs[offset + 2] = 0.0  # Opponent's flags not visible
    offset += 3

    # Global state
    obs[offset] = min(state.turn_number / 100.0, 1.0)
    obs[offset + 1] = 1.0 if state.current_player == player_idx else 0.0
    offset += 2

    # Energy zone (one-hot)
    energy_types = [
        EnergyType.GRASS, EnergyType.FIRE, EnergyType.WATER, EnergyType.LIGHTNING,
        EnergyType.PSYCHIC, EnergyType.FIGHTING, EnergyType.DARKNESS, EnergyType.METAL,
    ]
    if state.energy_available:
        for i, etype in enumerate(energy_types):
            if state.energy_available == etype:
                obs[offset + i] = 1.0
    offset += NUM_ENERGY_TYPES

    # Flags
    obs[offset] = 1.0 if me.has_attached_energy else 0.0
    obs[offset + 1] = 1.0 if me.has_played_supporter else 0.0
    obs[offset + 2] = 1.0 if me.has_retreated else 0.0

    return obs


class PTCGPEnv(gym.Env):
    """Gymnasium environment for Pokemon TCG Pocket."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        deck1: list[str] | None = None,
        deck2: list[str] | None = None,
        energy_types1: list[EnergyType] | None = None,
        energy_types2: list[EnergyType] | None = None,
        opponent: Agent | str = "heuristic",
        player_idx: int = 0,
        render_mode: str | None = None,
    ):
        super().__init__()

        self.deck1 = deck1 or []
        self.deck2 = deck2 or []
        self.energy_types1 = energy_types1 or [EnergyType.GRASS]
        self.energy_types2 = energy_types2 or [EnergyType.FIRE]
        self.player_idx = player_idx
        self.render_mode = render_mode

        if isinstance(opponent, str):
            if opponent == "random":
                self.opponent = RandomAgent()
            else:
                self.opponent = HeuristicAgent()
        else:
            self.opponent = opponent

        self.observation_space = spaces.Box(
            low=0.0, high=1.0,
            shape=(TOTAL_OBS_SIZE,),
            dtype=np.float32,
        )

        self.action_space = spaces.Discrete(NUM_ACTIONS)

        self.state: GameState | None = None
        self._game_seed = 0

    def reset(self, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)

        if seed is not None:
            self._game_seed = seed
        else:
            self._game_seed += 1

        self.state = create_game(
            self.deck1, self.deck2,
            self.energy_types1, self.energy_types2,
            seed=self._game_seed,
        )

        # Auto setup
        for i in range(2):
            self.state = auto_setup(self.state, i, RandomAgent())

        # Verify setup
        for i in range(2):
            if self.state.players[i].active.is_empty:
                # Bad setup - return terminal state
                obs = np.zeros(TOTAL_OBS_SIZE, dtype=np.float32)
                return obs, {"action_mask": np.zeros(NUM_ACTIONS, dtype=np.int8)}

        self.state = start_game(self.state)

        # If opponent goes first, play their turns
        self._play_opponent_turns()

        obs = encode_observation(self.state, self.player_idx)
        info = {"action_mask": np.array(get_action_mask(self.state), dtype=np.int8)}
        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        if self.state is None or self.state.phase == GamePhase.GAME_OVER:
            obs = np.zeros(TOTAL_OBS_SIZE, dtype=np.float32)
            return obs, 0.0, True, False, {"action_mask": np.zeros(NUM_ACTIONS, dtype=np.int8)}

        action_type = ActionType(action)
        legal = get_legal_actions(self.state)

        if action_type not in legal:
            # With MaskablePPO this shouldn't happen, but handle gracefully
            obs = encode_observation(self.state, self.player_idx)
            info = {"action_mask": np.array(get_action_mask(self.state), dtype=np.int8)}
            return obs, -0.01, False, False, info

        # Snapshot state before action for reward computation
        me = self.state.players[self.player_idx]
        opp = self.state.players[1 - self.player_idx]
        my_points_before = me.points
        opp_points_before = opp.points
        my_hp_before = sum(
            s.current_hp for _, s in me.all_pokemon_slots() if not s.is_empty
        )
        opp_hp_before = sum(
            s.current_hp for _, s in opp.all_pokemon_slots() if not s.is_empty
        )

        # Apply action
        self.state = apply_action(self.state, action_type)

        # If game is over after our action, calculate reward
        if self.state.phase == GamePhase.GAME_OVER:
            return self._terminal_step()

        # Play opponent's turns
        self._play_opponent_turns()

        if self.state.phase == GamePhase.GAME_OVER:
            return self._terminal_step()

        # Richer intermediate reward shaping
        me = self.state.players[self.player_idx]
        opp = self.state.players[1 - self.player_idx]

        reward = 0.0

        # KO rewards (main signal)
        my_point_gain = me.points - my_points_before
        opp_point_gain = opp.points - opp_points_before
        reward += my_point_gain * 0.4
        reward -= opp_point_gain * 0.4

        # Damage dealt/received (small signal to encourage aggression)
        my_hp_after = sum(
            s.current_hp for _, s in me.all_pokemon_slots() if not s.is_empty
        )
        opp_hp_after = sum(
            s.current_hp for _, s in opp.all_pokemon_slots() if not s.is_empty
        )
        damage_dealt = max(0, opp_hp_before - opp_hp_after)
        damage_taken = max(0, my_hp_before - my_hp_after)
        reward += damage_dealt * 0.002   # Small bonus for dealing damage
        reward -= damage_taken * 0.001   # Smaller penalty for taking damage

        obs = encode_observation(self.state, self.player_idx)
        info = {"action_mask": np.array(get_action_mask(self.state), dtype=np.int8)}
        return obs, reward, False, False, info

    def _terminal_step(self) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Handle a terminal game state."""
        if self.state.winner == self.player_idx:
            reward = 1.0
        elif self.state.winner is not None:
            reward = -1.0
        else:
            reward = -0.1  # Small penalty for draws (encourage decisive play)

        obs = encode_observation(self.state, self.player_idx)
        info = {"action_mask": np.zeros(NUM_ACTIONS, dtype=np.int8)}
        return obs, reward, True, False, info

    def _play_opponent_turns(self) -> None:
        """Play the opponent's turns until it's the agent's turn or game over."""
        max_opponent_actions = 200  # Safety limit
        actions_taken = 0

        while (self.state.phase != GamePhase.GAME_OVER
               and self.state.current_player != self.player_idx
               and actions_taken < max_opponent_actions):

            legal = get_legal_actions(self.state)
            if not legal:
                self.state = apply_action(self.state, ActionType.END_TURN)
                actions_taken += 1
                continue

            action = self.opponent.choose_action(self.state, legal)
            self.state = apply_action(self.state, action)
            actions_taken += 1

        # Also handle target selection / promotion for our player
        while (self.state.phase in (GamePhase.AWAITING_TARGET, GamePhase.AWAITING_BENCH_PROMOTION)
               and self.state.phase != GamePhase.GAME_OVER):
            # These require agent input, so break back to step()
            break

    def action_masks(self) -> np.ndarray:
        """Get action mask for use with MaskablePPO."""
        if self.state is None:
            return np.zeros(NUM_ACTIONS, dtype=np.int8)
        return np.array(get_action_mask(self.state), dtype=np.int8)

    def render(self) -> None:
        if self.render_mode == "human" and self.state:
            from ptcgp.agents.human import _render_board
            _render_board(self.state, self.player_idx)
