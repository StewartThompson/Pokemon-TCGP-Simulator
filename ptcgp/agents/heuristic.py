"""Heuristic agent - rule-based priorities for decent play."""

from __future__ import annotations

import random

from ptcgp.engine.game import GameState, get_card
from ptcgp.engine.types import ActionType, CardType, EnergyType, StatusEffect
from .base import Agent


class HeuristicAgent(Agent):
    """Agent that uses hand-crafted heuristics to play reasonably well."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def choose_action(self, state: GameState, legal_actions: list[ActionType]) -> ActionType:
        if len(legal_actions) == 1:
            return legal_actions[0]

        player = state.current
        opponent = state.opponent

        scored: list[tuple[float, ActionType]] = []
        for action in legal_actions:
            score = self._score_action(state, action)
            scored.append((score, action))

        # Sort by score descending, pick the best (with some randomness among ties)
        scored.sort(key=lambda x: (-x[0], self.rng.random()))
        return scored[0][1]

    def _score_action(self, state: GameState, action: ActionType) -> float:
        """Score an action. Higher = better."""
        player = state.current
        opponent = state.opponent
        active = player.active
        active_card = active.card if not active.is_empty else None

        # --- ATTACK: highest priority if it can KO ---
        if action in (ActionType.ATTACK_0, ActionType.ATTACK_1):
            atk_idx = 0 if action == ActionType.ATTACK_0 else 1
            if active_card and atk_idx < len(active_card.attacks):
                attack = active_card.attacks[atk_idx]
                damage = attack.damage
                # Weakness bonus
                if (not opponent.active.is_empty and opponent.active.card and
                    opponent.active.card.weakness == active_card.element):
                    damage += 20

                opp_hp = opponent.active.current_hp if not opponent.active.is_empty else 999

                if damage >= opp_hp:
                    return 100  # KO! Highest priority
                else:
                    return 50 + (damage / max(opp_hp, 1)) * 30  # Partial damage

        # --- ENERGY ATTACHMENT ---
        if ActionType.ENERGY_ACTIVE <= action <= ActionType.ENERGY_BENCH_2:
            if action == ActionType.ENERGY_ACTIVE:
                slot = active
            else:
                idx = action - ActionType.ENERGY_BENCH_0
                slot = player.bench[idx]

            if not slot.is_empty and slot.card:
                card = slot.card
                # Prioritize Pokemon that need energy to attack
                if card.attacks:
                    total_cost = sum(card.attacks[0].cost.values())
                    current = slot.total_energy
                    if current < total_cost:
                        return 45 + (1 - current / max(total_cost, 1)) * 10
                return 40
            return 0

        # --- PLAY BASIC POKEMON TO BENCH ---
        if ActionType.PLAY_HAND_0 <= action <= ActionType.PLAY_HAND_9:
            hand_idx = action - ActionType.PLAY_HAND_0
            if hand_idx >= len(player.hand):
                return 0
            card_id = player.hand[hand_idx]
            card = get_card(card_id)

            if card.card_type == CardType.POKEMON and card.is_basic:
                # Good to fill bench early
                empty_count = len(player.empty_bench_slots())
                return 35 + empty_count * 3

            if card.card_type == CardType.POKEMON:
                # Evolution - high value
                return 42

            if card.card_type == CardType.SUPPORTER:
                return 38  # Supporters are generally strong

            if card.card_type == CardType.ITEM:
                return 30  # Items are free to play

            if card.card_type == CardType.TOOL:
                return 28

        # --- RETREAT ---
        if ActionType.RETREAT_BENCH_0 <= action <= ActionType.RETREAT_BENCH_2:
            if active_card and not active.is_empty:
                # Retreat if active is weak against opponent
                if (not opponent.active.is_empty and opponent.active.card and
                    active_card.weakness and
                    active_card.weakness == opponent.active.card.element):
                    return 40  # Get out of weakness matchup

                # Retreat if active is low HP
                if active.current_hp < active.max_hp * 0.3:
                    return 38

                # Retreat if poisoned/burned
                if active.status_effects & {StatusEffect.POISONED, StatusEffect.BURNED}:
                    return 35

            return 5  # Generally don't retreat without reason

        # --- ABILITIES ---
        if ActionType.ABILITY_ACTIVE <= action <= ActionType.ABILITY_BENCH_2:
            return 32  # Abilities are usually good to use

        # --- TARGET SELECTION ---
        if ActionType.TARGET_ACTIVE <= action <= ActionType.TARGET_OPP_BENCH_2:
            return 20  # Just pick one (more nuance could be added)

        # --- END TURN ---
        if action == ActionType.END_TURN:
            return 1  # Low priority - prefer doing something

        return 0
