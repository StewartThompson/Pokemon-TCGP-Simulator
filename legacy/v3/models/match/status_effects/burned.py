"""Burned status effect"""
import random
from .status_effect import StatusEffect

class Burned(StatusEffect):
    """Pokemon is Burned - coin flip: heads = 20 damage, tails = remove"""
    
    def apply(self, pokemon, battle_engine):
        if not hasattr(pokemon, 'status_effects'):
            pokemon.status_effects = []
        if self not in pokemon.status_effects:
            pokemon.status_effects.append(self)
            battle_engine.log(f"{pokemon.name} is now Burned")
    
    def check_removal(self, pokemon, battle_engine):
        # Burn removal is handled in apply_damage
        return False
    
    def remove(self, pokemon):
        if hasattr(pokemon, 'status_effects') and self in pokemon.status_effects:
            pokemon.status_effects.remove(self)
    
    def apply_damage(self, pokemon, battle_engine):
        """Apply burn damage between turns"""
        # Heads = 20 damage, tails = remove
        if random.random() < 0.5:
            battle_engine.log(f"{pokemon.name} takes 20 damage from Burn")
            pokemon.damage_taken += 20
            # Check for knockout
            if pokemon.damage_taken >= pokemon.health:
                battle_engine._handle_knockout(pokemon, battle_engine._get_player_with_pokemon(pokemon))
        else:
            battle_engine.log(f"{pokemon.name} recovered from Burn")
            self.remove(pokemon)

