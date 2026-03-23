"""Coin flip effect - handles coin flip mechanics for attacks"""
from typing import Optional, TYPE_CHECKING
import re
import random
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class CoinFlipEffect(Effect):
    """Effect that involves a coin flip"""
    
    def __init__(self, effect_type: str, success_effect: Optional[Effect] = None, failure_effect: Optional[Effect] = None):
        """
        Args:
            effect_type: Type of coin flip effect:
                - "prevent_attack": If heads, opponent can't attack next turn
                - "extra_damage": If heads, add extra damage
                - "conditional_damage": If tails, attack does nothing
            success_effect: Effect to execute on heads (or success)
            failure_effect: Effect to execute on tails (or failure)
        """
        self.effect_type = effect_type
        self.success_effect = success_effect
        self.failure_effect = failure_effect
    
    def execute(self, player, battle_engine, source=None):
        """Execute coin flip"""
        # Flip coin: True = heads, False = tails
        coin_flip = random.random() < 0.5
        result = "heads" if coin_flip else "tails"
        battle_engine.log(f"Coin flip: {result}")
        
        if self.effect_type == "prevent_attack":
            # If heads, prevent opponent from attacking next turn
            opponent = battle_engine._get_opponent(player)
            if coin_flip and opponent:
                # Mark that opponent can't attack next turn
                opponent.can_attack_next_turn = False
                battle_engine.log(f"{opponent.name} can't attack during their next turn!")
            else:
                battle_engine.log("Coin flip failed - no effect")
        
        elif self.effect_type == "extra_damage":
            # If heads, add extra damage (handled in attack execution)
            if coin_flip and self.success_effect:
                self.success_effect.execute(player, battle_engine, source)
        
        elif self.effect_type == "conditional_damage":
            # If tails, attack does nothing (handled in attack execution)
            if not coin_flip:
                battle_engine.log("Coin flip failed - attack does nothing")
                # Return a flag that attack should be cancelled
                return False
        
        # Execute success/failure effects if provided
        if coin_flip and self.success_effect:
            self.success_effect.execute(player, battle_engine, source)
        elif not coin_flip and self.failure_effect:
            self.failure_effect.execute(player, battle_engine, source)
        
        return coin_flip
    
    @classmethod
    def from_text(cls, effect_text: str) -> Optional['CoinFlipEffect']:
        """Parse coin flip effect from text"""
        text_lower = effect_text.lower()
        
        # Pattern: "Flip a coin. If heads, the Defending Pokémon can't attack during your opponent's next turn."
        if "flip a coin" in text_lower and "can't attack" in text_lower:
            return cls("prevent_attack")
        
        # Pattern: "Flip a coin. If heads, this attack does X more damage."
        if "flip a coin" in text_lower and "more damage" in text_lower:
            # Parse extra damage amount
            match = re.search(r'(\d+) more damage', text_lower)
            if match:
                extra_damage = int(match.group(1))
                # Create a damage effect (would need to be handled in attack execution)
                return cls("extra_damage")
        
        # Pattern: "Flip a coin. If tails, this attack does nothing."
        if "flip a coin" in text_lower and ("tails" in text_lower or "does nothing" in text_lower):
            return cls("conditional_damage")
        
        return None

