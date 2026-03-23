"""Draw effect - draws cards from deck"""
import re
from typing import Optional, TYPE_CHECKING
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class DrawEffect(Effect):
    """Draw cards from deck"""
    
    def __init__(self, amount: int):
        self.amount = amount
    
    def execute(self, player, battle_engine, source=None):
        drawn = 0
        for _ in range(self.amount):
            if len(player.deck) > 0:
                try:
                    player.draw(1)
                    drawn += 1
                except ValueError:
                    break
        battle_engine.log(f"Drew {drawn} card(s)")
    
    @classmethod
    def from_text(cls, effect_text: str) -> Optional['DrawEffect']:
        """Parse draw effect from text"""
        # Pattern: "Draw X cards"
        pattern = r'draw\s+(\d+)\s+card'
        match = re.search(pattern, effect_text.lower())
        if match:
            amount = int(match.group(1))
            return cls(amount)
        return None

