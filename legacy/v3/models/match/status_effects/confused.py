"""Confused status effect"""
import random
from .status_effect import StatusEffect

class Confused(StatusEffect):
    """Pokemon is Confused - coin flip to attack self for 30 damage"""
    
    def apply(self, pokemon, battle_engine):
        if not hasattr(pokemon, 'status_effects'):
            pokemon.status_effects = []
        if self not in pokemon.status_effects:
            pokemon.status_effects.append(self)
            battle_engine.log(f"{pokemon.name} is now Confused")
    
    def check_removal(self, pokemon, battle_engine):
        # Confusion doesn't auto-remove
        return False
    
    def remove(self, pokemon):
        if hasattr(pokemon, 'status_effects') and self in pokemon.status_effects:
            pokemon.status_effects.remove(self)
    
    def check_attack_self(self, pokemon, battle_engine):
        """Check if Pokemon attacks itself (tails = attack self)"""
        if random.random() < 0.5:
            battle_engine.log(f"{pokemon.name} is confused and attacks itself!")
            pokemon.damage_taken += 30
            # Check for knockout
            if pokemon.damage_taken >= pokemon.health:
                battle_engine._handle_knockout(pokemon, battle_engine._get_player_with_pokemon(pokemon))
            return True
        return False

