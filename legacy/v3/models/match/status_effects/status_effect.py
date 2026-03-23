"""Base class for status effects"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v3.models.cards.pokemon import Pokemon
    from v3.models.match.battle_engine import BattleEngine

class StatusEffect(ABC):
    """Base class for status conditions"""
    
    @abstractmethod
    def apply(self, pokemon: 'Pokemon', battle_engine: 'BattleEngine') -> None:
        """Apply status effect to Pokemon"""
        pass
    
    @abstractmethod
    def check_removal(self, pokemon: 'Pokemon', battle_engine: 'BattleEngine') -> bool:
        """Check if status effect should be removed"""
        return False
    
    @abstractmethod
    def remove(self, pokemon: 'Pokemon') -> None:
        """Remove status effect from Pokemon"""
        pass

