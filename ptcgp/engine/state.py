"""Core game state dataclasses — the pure data model for the engine."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from ptcgp.cards.types import Element


def _copy_rng(rng: random.Random) -> random.Random:
    """Copy a Random instance without calling __init__ or seed().

    ``copy.copy`` uses Python's pickle protocol which reconstructs via
    ``Random.__init__()`` → ``seed()``, wasting ~1.8s per 1000 games.
    ``__new__`` + ``setstate`` skips init entirely.
    """
    new = random.Random.__new__(random.Random)
    new.setstate(rng.getstate())
    return new


class StatusEffect(Enum):
    POISONED = "poisoned"
    BURNED = "burned"
    PARALYZED = "paralyzed"
    ASLEEP = "asleep"
    CONFUSED = "confused"


class GamePhase(Enum):
    SETUP = "setup"
    MAIN = "main"
    AWAITING_BENCH_PROMOTION = "awaiting_bench_promotion"
    GAME_OVER = "game_over"


@dataclass
class PokemonSlot:
    """A single Pokemon in play (active or bench)."""
    card_id: str
    current_hp: int
    max_hp: int
    attached_energy: dict[Element, int] = field(default_factory=dict)
    status_effects: set[StatusEffect] = field(default_factory=set)
    turns_in_play: int = 0          # incremented at start of each owner's turn
    tool_card_id: Optional[str] = None
    evolved_this_turn: bool = False
    ability_used_this_turn: bool = False
    cant_attack_next_turn: bool = False  # set by Tail Whip and similar effects
    cant_retreat_next_turn: bool = False  # set by retreat-block effects
    prevent_damage_next_turn: bool = False  # set by prevent-all-damage effects
    incoming_damage_reduction: int = 0  # -N from attacks next turn
    attack_bonus_next_turn_self: int = 0  # e.g. -20 damage dealt next turn (Defending nerf)

    def copy(self) -> "PokemonSlot":
        return PokemonSlot(
            card_id=self.card_id,
            current_hp=self.current_hp,
            max_hp=self.max_hp,
            attached_energy=dict(self.attached_energy),
            status_effects=set(self.status_effects),
            turns_in_play=self.turns_in_play,
            tool_card_id=self.tool_card_id,
            evolved_this_turn=self.evolved_this_turn,
            ability_used_this_turn=self.ability_used_this_turn,
            cant_attack_next_turn=self.cant_attack_next_turn,
            cant_retreat_next_turn=self.cant_retreat_next_turn,
            prevent_damage_next_turn=self.prevent_damage_next_turn,
            incoming_damage_reduction=self.incoming_damage_reduction,
            attack_bonus_next_turn_self=self.attack_bonus_next_turn_self,
        )

    def total_energy(self) -> int:
        return sum(self.attached_energy.values())

    def energy_count(self, element: Element) -> int:
        return self.attached_energy.get(element, 0)


@dataclass
class PlayerState:
    """All state belonging to one player."""
    active: Optional[PokemonSlot] = None
    bench: list[Optional[PokemonSlot]] = field(default_factory=lambda: [None, None, None])
    hand: list[str] = field(default_factory=list)       # list of card IDs
    deck: list[str] = field(default_factory=list)       # list of card IDs
    discard: list[str] = field(default_factory=list)    # list of card IDs
    points: int = 0
    energy_types: list[Element] = field(default_factory=list)  # up to 3

    # Per-turn flags (reset each turn)
    has_attached_energy: bool = False
    has_played_supporter: bool = False
    has_retreated: bool = False
    energy_available: Optional[Element] = None  # energy generated this turn

    # Turn-scoped buffs/debuffs (cleared at end_turn)
    attack_damage_bonus: int = 0  # flat damage added to every attack this turn (Giovanni-style)
    attack_damage_bonus_names: tuple = ()  # empty means all attackers; else only these pokemon names
    retreat_cost_modifier: int = 0  # -N retreat cost (X Speed) this turn
    cant_play_supporter_this_turn: bool = False

    # Flags scheduled to take effect on the player's next turn
    cant_play_supporter_incoming: bool = False

    def copy(self) -> "PlayerState":
        return PlayerState(
            active=self.active.copy() if self.active else None,
            bench=[s.copy() if s else None for s in self.bench],
            hand=list(self.hand),
            deck=list(self.deck),
            discard=list(self.discard),
            points=self.points,
            energy_types=list(self.energy_types),
            has_attached_energy=self.has_attached_energy,
            has_played_supporter=self.has_played_supporter,
            has_retreated=self.has_retreated,
            energy_available=self.energy_available,
            attack_damage_bonus=self.attack_damage_bonus,
            attack_damage_bonus_names=self.attack_damage_bonus_names,
            retreat_cost_modifier=self.retreat_cost_modifier,
            cant_play_supporter_this_turn=self.cant_play_supporter_this_turn,
            cant_play_supporter_incoming=self.cant_play_supporter_incoming,
        )

    def all_pokemon(self) -> list[PokemonSlot]:
        """Return all non-None Pokemon in play (active + bench)."""
        result = []
        if self.active:
            result.append(self.active)
        result.extend(s for s in self.bench if s is not None)
        return result

    def bench_count(self) -> int:
        return sum(1 for s in self.bench if s is not None)

    def has_any_pokemon(self) -> bool:
        return self.active is not None or any(s is not None for s in self.bench)


@dataclass
class GameState:
    """Complete game state. The engine only mutates via copy-on-write."""
    players: list[PlayerState] = field(default_factory=lambda: [PlayerState(), PlayerState()])
    turn_number: int = 0            # total half-turns elapsed (increments each turn)
    current_player: int = 0         # index 0 or 1
    first_player: int = 0           # set after coin flip; used to determine turn-1 restrictions
    phase: GamePhase = GamePhase.SETUP
    winner: Optional[int] = None    # 0 or 1, or -1 for tie
    rng: random.Random = field(default_factory=random.Random)

    def copy(self) -> "GameState":
        new = GameState(
            players=[p.copy() for p in self.players],
            turn_number=self.turn_number,
            current_player=self.current_player,
            first_player=self.first_player,
            phase=self.phase,
            winner=self.winner,
            rng=_copy_rng(self.rng),
        )
        return new

    @property
    def current(self) -> PlayerState:
        return self.players[self.current_player]

    @property
    def opponent(self) -> PlayerState:
        return self.players[1 - self.current_player]

    @property
    def opponent_index(self) -> int:
        return 1 - self.current_player

    def is_first_turn(self) -> bool:
        """True if the current player is taking their very first turn ever."""
        return self.turn_number == 0 or (self.turn_number == 1 and self.current_player != self.first_player)

    def player_turn_number(self) -> int:
        """How many turns the current player has taken (0-indexed)."""
        return self.turn_number // 2
