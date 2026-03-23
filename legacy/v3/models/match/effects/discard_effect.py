"""Discard effect - discards cards"""
from typing import Optional, TYPE_CHECKING
import re
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine

class DiscardEffect(Effect):
    """Effect that discards cards"""
    
    def __init__(self, target: str, amount: int = 1, energy_type: Optional[str] = None):
        self.target = target  # "hand", "deck", "energy"
        self.amount = amount
        self.energy_type = energy_type  # Specific energy type to discard (e.g., "Fire", "Grass")
    
    def execute(self, player, battle_engine, source=None):
        if self.target == "hand":
            for _ in range(min(self.amount, len(player.cards_in_hand))):
                if player.cards_in_hand:
                    card = player.cards_in_hand.pop()
                    player.discard_card(card)
                    battle_engine.log(f"{player.name} discarded {card.name}")
        elif self.target == "energy" and source:
            # Discard energy from Pokemon
            from v3.models.cards.energy import Energy
            
            # Map energy type string to Energy.Type enum
            energy_type_map = {
                'fire': Energy.Type.FIRE,
                'grass': Energy.Type.GRASS,
                'water': Energy.Type.WATER,
                'electric': Energy.Type.ELECTRIC,
                'lightning': Energy.Type.ELECTRIC,
                'psychic': Energy.Type.PSYCHIC,
                'fighting': Energy.Type.ROCK,
                'rock': Energy.Type.ROCK,
                'dark': Energy.Type.DARK,
                'darkness': Energy.Type.DARK,
                'metal': Energy.Type.METAL,
                'normal': Energy.Type.NORMAL,
                'colorless': Energy.Type.NORMAL,
            }
            
            # If specific energy type is required
            if self.energy_type:
                energy_type_enum = energy_type_map.get(self.energy_type.lower())
                if energy_type_enum:
                    # Discard specific energy type
                    discarded = 0
                    for _ in range(self.amount):
                        if source.equipped_energies.get(energy_type_enum, 0) > 0:
                            source.equipped_energies[energy_type_enum] -= 1
                            discarded += 1
                            battle_engine.log(f"{source.name} lost 1 {self.energy_type} energy")
                    if discarded == 0:
                        battle_engine.log(f"{source.name} has no {self.energy_type} energy to discard")
                else:
                    battle_engine.log(f"Unknown energy type: {self.energy_type}")
            else:
                # Discard any energy type (fallback)
                for _ in range(min(self.amount, sum(source.equipped_energies.values()))):
                    # Remove one energy (any type)
                    for energy_type in list(source.equipped_energies.keys()):
                        if source.equipped_energies[energy_type] > 0:
                            source.equipped_energies[energy_type] -= 1
                            energy_name = energy_type.name.lower() if hasattr(energy_type, 'name') else str(energy_type)
                            battle_engine.log(f"{source.name} lost 1 {energy_name} energy")
                            break
    
    @classmethod
    def from_text(cls, effect_text: str):
        text_lower = effect_text.lower()
        if "discard" in text_lower:
            # Parse amount
            amount = 1
            match = re.search(r'discard (\d+)', text_lower)
            if match:
                amount = int(match.group(1))
            
            # Determine target
            target = "hand"
            energy_type = None
            
            if "energy" in text_lower:
                target = "energy"
                # Try to parse specific energy type
                energy_types = ['fire', 'grass', 'water', 'electric', 'lightning', 'psychic', 
                               'fighting', 'rock', 'dark', 'darkness', 'metal', 'normal', 'colorless']
                for et in energy_types:
                    if et in text_lower:
                        energy_type = et.capitalize()
                        # Special case: lightning -> Electric
                        if energy_type == 'Lightning':
                            energy_type = 'Electric'
                        break
            
            return cls(target, amount, energy_type)
        return None

