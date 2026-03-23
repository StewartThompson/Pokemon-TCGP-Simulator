"""Paralyzed status effect"""
from .status_effect import StatusEffect

class Paralyzed(StatusEffect):
    """Pokemon is Paralyzed - can't attack or retreat, removed after turn"""
    
    def apply(self, pokemon, battle_engine):
        if not hasattr(pokemon, 'status_effects'):
            pokemon.status_effects = []
        if self not in pokemon.status_effects:
            pokemon.status_effects.append(self)
            battle_engine.log(f"{pokemon.name} is now Paralyzed")
    
    def check_removal(self, pokemon, battle_engine):
        # Removed after one turn
        return True
    
    def remove(self, pokemon):
        if hasattr(pokemon, 'status_effects') and self in pokemon.status_effects:
            pokemon.status_effects.remove(self)

