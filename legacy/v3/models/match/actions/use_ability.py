"""Use Ability action - use a Pokemon ability"""
from typing import Optional
from .action import Action, ActionType
from v3.models.cards.pokemon import Pokemon
from v3.models.match.effects import EffectParser

class UseAbilityAction(Action):
    """Action to use a Pokemon ability"""
    
    def __init__(self, pokemon_location: str, ability_index: int):
        super().__init__(ActionType.USE_ABILITY)
        self.pokemon_location = pokemon_location  # "active" or "bench_{index}"
        self.ability_index = ability_index
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if ability can be used"""
        pokemon = self._get_pokemon(player)
        if not pokemon:
            return False, f"No Pokemon at location: {self.pokemon_location}"
        
        if self.ability_index >= len(pokemon.abilities):
            return False, f"Invalid ability index: {self.ability_index}"
        
        if pokemon.used_ability_this_turn:
            return False, "Pokemon has already used an ability this turn"
        
            # Check if ability can be used (some abilities are passive)
            ability = pokemon.abilities[self.ability_index]
            # For now, assume all abilities can be activated
            # Future: Add passive ability detection (abilities that trigger automatically)
        
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
        """Execute ability use"""
        pokemon = self._get_pokemon(player)
        if not pokemon:
            raise ValueError(f"No Pokemon at location: {self.pokemon_location}")
        
        ability = pokemon.abilities[self.ability_index]
        
        # Mark ability as used
        pokemon.used_ability_this_turn = True
        
        # Execute ability effect
        if ability.effect:
            # Try ability-specific parsing first
            effect = EffectParser.parse_ability_effect(ability.effect)
            if effect:
                try:
                    effect.execute(player, battle_engine, pokemon)
                except Exception as e:
                    battle_engine.log(f"Error executing ability effect: {e}")
                    import traceback
                    if battle_engine.debug:
                        traceback.print_exc()
            else:
                # Fall back to standard parsing
                effects = EffectParser.parse_multiple(ability.effect)
                for effect in effects:
                    try:
                        effect.execute(player, battle_engine, pokemon)
                    except Exception as e:
                        battle_engine.log(f"Error executing ability effect: {e}")
                        import traceback
                        if battle_engine.debug:
                            traceback.print_exc()
        
        battle_engine.log(f"{player.name} used {ability.name} from {pokemon.name}")
    
    def to_string(self) -> str:
        return f"use_ability_{self.pokemon_location}_{self.ability_index}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'UseAbilityAction':
        if not action_str.startswith("use_ability_"):
            raise ValueError(f"Invalid action string: {action_str}")
        parts = action_str.replace("use_ability_", "").split("_")
        if len(parts) < 2:
            raise ValueError(f"Invalid ability action format: {action_str}")
        location = "_".join(parts[:-1])
        ability_index = int(parts[-1])
        return cls(location, ability_index)

