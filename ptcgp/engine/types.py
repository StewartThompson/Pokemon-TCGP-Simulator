"""Core type definitions for the PTCGP engine."""

from __future__ import annotations

from enum import Enum, IntEnum, auto
from dataclasses import dataclass, field
from typing import Optional


class EnergyType(Enum):
    GRASS = "grass"
    FIRE = "fire"
    WATER = "water"
    LIGHTNING = "lightning"
    PSYCHIC = "psychic"
    FIGHTING = "fighting"
    DARKNESS = "darkness"
    METAL = "metal"
    COLORLESS = "colorless"  # Not a real energy type, just for cost specification


class PokemonStage(Enum):
    BASIC = "basic"
    STAGE1 = "stage1"
    STAGE2 = "stage2"


class CardType(Enum):
    POKEMON = "pokemon"
    ITEM = "item"
    SUPPORTER = "supporter"
    TOOL = "tool"


class StatusEffect(Enum):
    POISONED = "poisoned"
    BURNED = "burned"
    PARALYZED = "paralyzed"
    ASLEEP = "asleep"
    CONFUSED = "confused"


class GamePhase(Enum):
    SETUP = "setup"
    DRAW = "draw"
    MAIN = "main"
    ATTACK = "attack"
    BETWEEN_TURNS = "between_turns"
    AWAITING_TARGET = "awaiting_target"
    AWAITING_BENCH_PROMOTION = "awaiting_bench_promotion"
    GAME_OVER = "game_over"


class ActionType(IntEnum):
    ATTACK_0 = 0
    ATTACK_1 = 1
    RETREAT_BENCH_0 = 2
    RETREAT_BENCH_1 = 3
    RETREAT_BENCH_2 = 4
    PLAY_HAND_0 = 5
    PLAY_HAND_1 = 6
    PLAY_HAND_2 = 7
    PLAY_HAND_3 = 8
    PLAY_HAND_4 = 9
    PLAY_HAND_5 = 10
    PLAY_HAND_6 = 11
    PLAY_HAND_7 = 12
    PLAY_HAND_8 = 13
    PLAY_HAND_9 = 14
    ENERGY_ACTIVE = 15
    ENERGY_BENCH_0 = 16
    ENERGY_BENCH_1 = 17
    ENERGY_BENCH_2 = 18
    ABILITY_ACTIVE = 19
    ABILITY_BENCH_0 = 20
    ABILITY_BENCH_1 = 21
    ABILITY_BENCH_2 = 22
    END_TURN = 23
    # Target selection actions (used in AWAITING_TARGET phase)
    TARGET_ACTIVE = 24
    TARGET_BENCH_0 = 25
    TARGET_BENCH_1 = 26
    TARGET_BENCH_2 = 27
    TARGET_OPP_ACTIVE = 28
    TARGET_OPP_BENCH_0 = 29
    TARGET_OPP_BENCH_1 = 30
    TARGET_OPP_BENCH_2 = 31

NUM_ACTIONS = 32  # Total action space size


# --- Effect types for card effects ---

class EffectType(Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    DRAW_CARDS = "draw_cards"
    SEARCH_DECK = "search_deck"
    DISCARD_ENERGY = "discard_energy"
    ATTACH_ENERGY = "attach_energy"
    APPLY_STATUS = "apply_status"
    SWITCH_OPPONENT = "switch_opponent"
    SWITCH_SELF = "switch_self"
    COIN_FLIP = "coin_flip"
    HEAL_ALL = "heal_all"
    EXTRA_DAMAGE = "extra_damage"
    PREVENT_DAMAGE = "prevent_damage"
    SELF_DAMAGE = "self_damage"
    BENCH_DAMAGE = "bench_damage"
    CANT_ATTACK = "cant_attack"
    EVOLVE_SKIP = "evolve_skip"  # Rare Candy
    HP_BONUS = "hp_bonus"  # Giant Cape etc


# --- Constants ---

DECK_SIZE = 20
MAX_COPIES_PER_CARD = 2
BENCH_SIZE = 3
MAX_HAND_SIZE = 10
INITIAL_HAND_SIZE = 5
POINTS_TO_WIN = 3
POINTS_PER_KO = 1
POINTS_PER_EX_KO = 2
WEAKNESS_BONUS = 20
POISON_DAMAGE = 10
BURN_DAMAGE = 20
CONFUSION_SELF_DAMAGE = 30
MAX_TURNS = 200  # Safety limit

# Weakness chart: defending_type -> attacking_type that triggers weakness
WEAKNESS_CHART: dict[EnergyType, EnergyType] = {
    EnergyType.GRASS: EnergyType.FIRE,
    EnergyType.FIRE: EnergyType.WATER,
    EnergyType.WATER: EnergyType.LIGHTNING,
    EnergyType.LIGHTNING: EnergyType.FIGHTING,
    EnergyType.PSYCHIC: EnergyType.DARKNESS,
    EnergyType.FIGHTING: EnergyType.PSYCHIC,
    EnergyType.DARKNESS: EnergyType.FIGHTING,
    EnergyType.METAL: EnergyType.FIRE,
}
