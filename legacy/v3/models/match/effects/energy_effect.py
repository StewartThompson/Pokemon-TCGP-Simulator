"""Energy effect - attaches or removes energy"""
from typing import Optional, TYPE_CHECKING
import re
from .effect import Effect
from v3.models.cards.energy import Energy

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class EnergyEffect(Effect):
    """Effect that attaches or removes energy"""
    
    def __init__(self, action: str, energy_type: str, amount: int = 1):
        self.action = action  # "attach", "remove", "search"
        self.energy_type = energy_type
        self.amount = amount
    
    def execute(self, player, battle_engine, source=None):
        if self.action == "attach" and source:
            # Attach energy to source Pokemon
            energy_map = {
                'FIRE': Energy.Type.FIRE,
                'WATER': Energy.Type.WATER,
                'ROCK': Energy.Type.ROCK,
                'GRASS': Energy.Type.GRASS,
                'NORMAL': Energy.Type.NORMAL,
                'COLORLESS': Energy.Type.NORMAL,
                'ELECTRIC': Energy.Type.ELECTRIC,
                'PSYCHIC': Energy.Type.PSYCHIC,
                'DARK': Energy.Type.DARK,
                'DARKNESS': Energy.Type.DARK,
                'METAL': Energy.Type.METAL,
            }
            energy_type_enum = energy_map.get(self.energy_type.upper(), Energy.Type.NORMAL)
            
            # Check if we need to take from energy zone
            # Pattern: "Take X Energy from your Energy Zone and attach it to this Pokémon"
            # We need to check if the effect text mentions "Energy Zone" to determine if we should consume
            # For now, we'll try to consume from energy zone for all attach effects
            # If energy zone doesn't have the right type, we'll log and skip
            attached_count = 0
            for _ in range(self.amount):
                # Try to get energy from energy zone if available
                if player.energy_zone.has_energy():
                    # Check if current energy matches the type we need
                    current_energy = player.energy_zone.current_energy
                    if current_energy == energy_type_enum:
                        # Consume from energy zone
                        consumed = player.energy_zone.consume_current()
                        if consumed:
                            source.equipped_energies[energy_type_enum] = source.equipped_energies.get(energy_type_enum, 0) + 1
                            attached_count += 1
                            battle_engine.log(f"Took {self.energy_type} energy from Energy Zone and attached to {source.name}")
                        else:
                            # Failed to consume - break loop
                            break
                    else:
                        # Energy type doesn't match - can't attach this type
                        battle_engine.log(f"Energy Zone has {current_energy.name if current_energy else 'None'}, but need {self.energy_type} - cannot attach")
                        break
                else:
                    # No energy in zone
                    battle_engine.log(f"No energy available in Energy Zone")
                    break
            
            if attached_count == 0:
                # Fallback: just attach without consuming (for effects that don't specify "from Energy Zone")
                # This handles backward compatibility for effects that just say "attach" without "from Energy Zone"
                source.equipped_energies[energy_type_enum] = source.equipped_energies.get(energy_type_enum, 0) + self.amount
                battle_engine.log(f"Attached {self.amount} {self.energy_type} energy to {source.name} (not from Energy Zone)")
            elif attached_count < self.amount:
                # Partially attached - log warning
                battle_engine.log(f"Warning: Only attached {attached_count} of {self.amount} {self.energy_type} energy")
        elif self.action == "search":
            # Search deck for energy cards (if we have energy cards)
            # For now, just log
            battle_engine.log(f"Searched deck for {self.amount} {self.energy_type} energy")
    
    @classmethod
    def from_text(cls, effect_text: str):
        text_lower = effect_text.lower()
        
        # Pattern: "Take X Energy from your Energy Zone and attach it to this Pokémon"
        if "take" in text_lower and "energy zone" in text_lower and "attach" in text_lower:
            # Parse energy type and amount
            energy_type = "Colorless"
            amount = 1
            
            # Try to find energy type
            energy_types = ['fire', 'water', 'grass', 'electric', 'lightning', 'psychic', 'rock', 'dark', 'darkness', 'metal', 'colorless', 'normal']
            for et in energy_types:
                if et in text_lower:
                    energy_type = et.capitalize()
                    # Special case: lightning -> Electric
                    if energy_type == 'Lightning':
                        energy_type = 'Electric'
                    break
            
            # Try to find amount
            match = re.search(r'take\s+(\d+)', text_lower)
            if match:
                amount = int(match.group(1))
            
            return cls("attach", energy_type, amount)
        
        # Pattern: "Attach X Energy to this Pokémon" (without "from Energy Zone")
        elif "attach" in text_lower and "energy" in text_lower:
            # Parse energy type and amount
            energy_type = "Colorless"
            amount = 1
            
            # Try to find energy type
            energy_types = ['fire', 'water', 'grass', 'electric', 'lightning', 'psychic', 'rock', 'dark', 'darkness', 'metal', 'colorless', 'normal']
            for et in energy_types:
                if et in text_lower:
                    energy_type = et.capitalize()
                    # Special case: lightning -> Electric
                    if energy_type == 'Lightning':
                        energy_type = 'Electric'
                    break
            
            # Try to find amount
            match = re.search(r'(\d+) (?:basic )?energy', text_lower)
            if match:
                amount = int(match.group(1))
            
            return cls("attach", energy_type, amount)
        
        elif "search" in text_lower and "energy" in text_lower:
            energy_type = "Colorless"
            amount = 1
            match = re.search(r'(\d+) (?:basic )?(\w+) energy', text_lower)
            if match:
                amount = int(match.group(1))
                energy_type = match.group(2).capitalize()
            return cls("search", energy_type, amount)
        return None

