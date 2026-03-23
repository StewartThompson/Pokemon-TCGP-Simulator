from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine

class ActionType(Enum):
    PLAY_POKEMON = "play_pokemon"
    ATTACH_ENERGY = "attach_energy"
    EVOLVE = "evolve"
    PLAY_ITEM = "play_item"
    PLAY_SUPPORTER = "play_supporter"
    ATTACH_TOOL = "attach_tool"
    USE_ABILITY = "use_ability"
    ATTACK = "attack"
    RETREAT = "retreat"
    SWITCH = "switch"
    END_TURN = "end_turn"

@dataclass
class Action(ABC):
    """Base class for all game actions"""
    action_type: ActionType
    
    @abstractmethod
    def validate(self, player: 'Player', battle_engine: 'BattleEngine') -> tuple[bool, Optional[str]]:
        """
        Validate if action can be executed
        Returns: (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def execute(self, player: 'Player', battle_engine: 'BattleEngine') -> None:
        """Execute the action"""
        pass
    
    @abstractmethod
    def to_string(self) -> str:
        """Convert action to string representation for agents"""
        pass
    
    @classmethod
    @abstractmethod
    def from_string(cls, action_str: str, player: 'Player') -> 'Action':
        """Create action from string representation"""
        pass

