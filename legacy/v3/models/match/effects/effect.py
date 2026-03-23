"""Base effect class for all game effects"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class Effect(ABC):
    """Base class for all game effects"""
    
    @abstractmethod
    def execute(self, player: 'Player', battle_engine: 'BattleEngine', source: Optional['Pokemon'] = None) -> None:
        """Execute the effect"""
        pass
    
    @classmethod
    @abstractmethod
    def from_text(cls, effect_text: str) -> Optional['Effect']:
        """Parse effect from text string"""
        pass

