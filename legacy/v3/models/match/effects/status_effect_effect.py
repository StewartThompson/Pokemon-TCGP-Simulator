"""Status effect effect - applies status conditions"""
from typing import Optional, TYPE_CHECKING
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

from v3.models.match.status_effects.asleep import Asleep
from v3.models.match.status_effects.poisoned import Poisoned
from v3.models.match.status_effects.burned import Burned
from v3.models.match.status_effects.paralyzed import Paralyzed
from v3.models.match.status_effects.confused import Confused

class StatusEffectEffect(Effect):
    """Effect that applies a status condition"""
    
    STATUS_MAP = {
        'asleep': Asleep,
        'poisoned': Poisoned,
        'burned': Burned,
        'paralyzed': Paralyzed,
        'confused': Confused,
    }
    
    def __init__(self, status_type: str, target: str = "opponent_active"):
        self.status_type = status_type
        self.target = target
        self.status_class = self.STATUS_MAP.get(status_type.lower())
    
    def execute(self, player: 'Player', battle_engine: 'BattleEngine', source: Optional['Pokemon'] = None) -> None:
        """Apply status effect to target"""
        if not self.status_class:
            battle_engine.log(f"Unknown status type: {self.status_type}")
            return
        
        # Determine target Pokemon
        if self.target == "opponent_active":
            opponent = battle_engine._get_opponent(player)
            target_pokemon = opponent.active_pokemon if opponent else None
        elif self.target == "this":
            target_pokemon = source
        else:
            target_pokemon = source
        
        if target_pokemon:
            status = self.status_class()
            status.apply(target_pokemon, battle_engine)
    
    @classmethod
    def from_text(cls, effect_text: str) -> Optional['StatusEffectEffect']:
        """Parse status effect from text"""
        text_lower = effect_text.lower()
        
        # Patterns: "is now Asleep", "is now Poisoned", etc.
        status_patterns = {
            'asleep': ['asleep', 'sleep'],
            'poisoned': ['poisoned', 'poison'],
            'burned': ['burned', 'burn'],
            'paralyzed': ['paralyzed', 'paralysis'],
            'confused': ['confused', 'confusion'],
        }
        
        for status_name, patterns in status_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    # Determine target
                    target = "opponent_active"
                    if "this pokémon" in text_lower or "your active" in text_lower:
                        target = "this"
                    
                    return cls(status_name, target)
        
        return None

