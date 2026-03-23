"""Poisoned status effect"""
from .status_effect import StatusEffect

class Poisoned(StatusEffect):
    """Pokemon is Poisoned - takes 10 damage between turns"""
    
    def apply(self, pokemon, battle_engine):
        if not hasattr(pokemon, 'status_effects'):
            pokemon.status_effects = []
        if self not in pokemon.status_effects:
            pokemon.status_effects.append(self)
            battle_engine.log(f"{pokemon.name} is Poisoned")
    
    def check_removal(self, pokemon, battle_engine):
        # Poison doesn't auto-remove
        return False
    
    def remove(self, pokemon):
        if hasattr(pokemon, 'status_effects') and self in pokemon.status_effects:
            pokemon.status_effects.remove(self)
    
    def apply_damage(self, pokemon, battle_engine):
        """Apply poison damage between turns"""
        battle_engine.log(f"{pokemon.name} takes 10 damage from Poison")
        pokemon.damage_taken += 10
        # Check for knockout
        if pokemon.damage_taken >= pokemon.health:
            battle_engine._handle_knockout(pokemon, battle_engine._get_player_with_pokemon(pokemon))

