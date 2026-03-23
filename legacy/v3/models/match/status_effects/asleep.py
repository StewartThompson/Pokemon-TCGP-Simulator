"""Asleep status effect"""
import random
from .status_effect import StatusEffect

class Asleep(StatusEffect):
    """Pokemon is Asleep - coin flip to wake up, can't attack"""
    
    def apply(self, pokemon, battle_engine):
        if not hasattr(pokemon, 'status_effects'):
            pokemon.status_effects = []
        if self not in pokemon.status_effects:
            pokemon.status_effects.append(self)
            battle_engine.log(f"{pokemon.name} is now Asleep")
    
    def check_removal(self, pokemon, battle_engine):
        # Coin flip: heads = wake up
        if random.random() < 0.5:
            battle_engine.log(f"{pokemon.name} woke up!")
            return True
        return False
    
    def remove(self, pokemon):
        if hasattr(pokemon, 'status_effects') and self in pokemon.status_effects:
            pokemon.status_effects.remove(self)

