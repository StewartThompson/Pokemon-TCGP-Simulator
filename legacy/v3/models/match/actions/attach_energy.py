from typing import Optional
from .action import Action, ActionType
from v3.models.cards.pokemon import Pokemon

class AttachEnergyAction(Action):
    """Action to attach energy from Energy Zone to Pokemon"""
    
    def __init__(self, pokemon_location: str):
        super().__init__(ActionType.ATTACH_ENERGY)
        self.pokemon_location = pokemon_location  # "active" or "bench_{index}"
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if energy can be attached"""
        # Check if first player's first turn (no energy attachment allowed)
        if hasattr(battle_engine, 'first_player_first_turn') and battle_engine.first_player_first_turn:
            return False, "Cannot attach energy on first player's first turn"
        
        # Check if already attached energy this turn (limit: 1 per turn)
        if player.attached_energy_this_turn:
            return False, "Already attached energy this turn (limit: 1 per turn)"
        
        # Check Energy Zone has energy
        if not player.energy_zone.has_energy():
            return False, "No energy in Energy Zone"
        
        # Get Pokemon
        pokemon = self._get_pokemon(player)
        if not pokemon:
            return False, f"No Pokemon at location: {self.pokemon_location}"
        
        return True, None
    
    def _get_pokemon(self, player) -> Optional[Pokemon]:
        """Get Pokemon at location"""
        if self.pokemon_location == "active":
            return player.active_pokemon
        elif self.pokemon_location.startswith("bench_"):
            try:
                bench_index = int(self.pokemon_location.split("_")[1])
                if 0 <= bench_index < len(player.bench_pokemons):
                    return player.bench_pokemons[bench_index]
            except (ValueError, IndexError):
                pass
        return None
    
    def execute(self, player, battle_engine) -> None:
        """Execute energy attachment"""
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: AttachEnergyAction.execute() called for location: {self.pokemon_location}")
        
        pokemon = self._get_pokemon(player)
        if not pokemon:
            raise ValueError(f"No Pokemon at location: {self.pokemon_location}")
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Found Pokemon: {pokemon.name} at {self.pokemon_location}")
        
        # Check if already attached energy this turn
        if player.attached_energy_this_turn:
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: Already attached energy this turn - raising error")
            raise ValueError("Already attached energy this turn (limit: 1 per turn)")
        
        # Get energy from Energy Zone
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Energy zone has energy: {player.energy_zone.has_energy()}")
            battle_engine.log(f"DEBUG: Current energy: {player.energy_zone.current_energy}")
        
        energy_type = player.energy_zone.consume_current()
        if not energy_type:
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: No energy available after consume - raising error")
            raise ValueError("No energy available")
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Consumed energy type: {energy_type}")
            battle_engine.log(f"DEBUG: Pokemon energy before: {pokemon.equipped_energies}")
        
        # Attach to Pokemon
        pokemon.equipped_energies[energy_type] += 1
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Pokemon energy after: {pokemon.equipped_energies}")
        
        # Mark that energy was attached this turn
        player.attached_energy_this_turn = True
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Set attached_energy_this_turn = True")
        
        battle_engine.log(f"{player.name} attached {energy_type} energy to {pokemon.name}")
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: AttachEnergyAction.execute() completed successfully")
    
    def to_string(self) -> str:
        return f"attach_energy_{self.pokemon_location}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'AttachEnergyAction':
        if not action_str.startswith("attach_energy_"):
            raise ValueError(f"Invalid action string: {action_str}")
        location = action_str.replace("attach_energy_", "")
        return cls(location)

