"""Rare Candy effect - allows Basic Pokemon to evolve directly to Stage 2"""
from typing import Optional, TYPE_CHECKING
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine

class RareCandyEffect(Effect):
    """Effect that allows Basic -> Stage 2 evolution this turn"""
    
    def __init__(self):
        pass
    
    def execute(self, player, battle_engine, source=None):
        """Mark that Rare Candy was used, allowing Basic -> Stage 2 evolution this turn"""
        player.used_rare_candy_this_turn = True
        battle_engine.log(f"{player.name} used Rare Candy - can evolve Basic Pokemon directly to Stage 2 this turn")
    
    @classmethod
    def from_text(cls, effect_text: str) -> Optional['RareCandyEffect']:
        """Parse Rare Candy effect from text"""
        import re
        text_lower = effect_text.lower()
        # Pattern: "You may evolve a Basic Pokemon directly to a Stage 2 Pokemon this turn."
        # Check for key phrases
        has_evolve = "evolve" in text_lower
        has_basic = "basic" in text_lower
        # Check for "stage 2" or "stage2" (with optional space)
        has_stage2 = bool(re.search(r'stage\s*2', text_lower))
        
        if has_evolve and has_basic and has_stage2:
            return cls()
        if "rare candy" in text_lower:
            return cls()
        return None

