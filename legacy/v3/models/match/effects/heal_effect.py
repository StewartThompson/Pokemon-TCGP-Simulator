"""Heal effect - heals damage from Pokemon"""
import re
from typing import Optional, TYPE_CHECKING
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class HealEffect(Effect):
    """Heal damage from Pokemon"""
    
    def __init__(self, amount: int, target: str = "this", pokemon_type: Optional[str] = None):
        self.amount = amount
        self.target = target  # "this", "each", "all", "one"
        self.pokemon_type = pokemon_type  # Optional: "Grass", "Fire", etc. - restricts to specific type
    
    def execute(self, player, battle_engine, source=None):
        from v3.models.cards.energy import Energy
        
        if self.target == "this" and source:
            old_damage = source.damage_taken
            source.damage_taken = max(0, source.damage_taken - self.amount)
            healed = old_damage - source.damage_taken
            battle_engine.log(f"Healed {healed} damage from {source.name}")
        elif self.target == "each":
            # Heal each Pokemon
            if source:
                source.damage_taken = max(0, source.damage_taken - self.amount)
            for bench_pokemon in player.bench_pokemons:
                if bench_pokemon:
                    bench_pokemon.damage_taken = max(0, bench_pokemon.damage_taken - self.amount)
            battle_engine.log(f"Healed {self.amount} damage from each Pokemon")
        elif self.target == "one":
            # Heal one Pokemon (player chooses, or auto-select if agent)
            # Get all eligible Pokemon
            eligible_pokemon = []
            
            # Check active Pokemon
            if player.active_pokemon and player.active_pokemon.damage_taken > 0:
                if not self.pokemon_type:
                    # No type restriction - all Pokemon eligible
                    eligible_pokemon.append(("active", player.active_pokemon))
                elif self._matches_type(player.active_pokemon, self.pokemon_type):
                    # Type restriction - check if matches
                    eligible_pokemon.append(("active", player.active_pokemon))
                    if battle_engine.debug:
                        battle_engine.log(f"DEBUG: Active {player.active_pokemon.name} ({player.active_pokemon.element}) matches type {self.pokemon_type}")
                elif battle_engine.debug:
                    battle_engine.log(f"DEBUG: Active {player.active_pokemon.name} ({player.active_pokemon.element}) does NOT match type {self.pokemon_type} - skipping")
            
            # Check bench Pokemon
            for i, bench_pokemon in enumerate(player.bench_pokemons):
                if bench_pokemon and bench_pokemon.damage_taken > 0:
                    if not self.pokemon_type:
                        # No type restriction - all Pokemon eligible
                        eligible_pokemon.append((f"bench_{i}", bench_pokemon))
                    elif self._matches_type(bench_pokemon, self.pokemon_type):
                        # Type restriction - check if matches
                        eligible_pokemon.append((f"bench_{i}", bench_pokemon))
                        if battle_engine.debug:
                            battle_engine.log(f"DEBUG: Bench {i} {bench_pokemon.name} ({bench_pokemon.element}) matches type {self.pokemon_type}")
                    elif battle_engine.debug:
                        battle_engine.log(f"DEBUG: Bench {i} {bench_pokemon.name} ({bench_pokemon.element}) does NOT match type {self.pokemon_type} - skipping")
            
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: Found {len(eligible_pokemon)} eligible Pokemon for healing (type restriction: {self.pokemon_type or 'none'})")
            
            if eligible_pokemon:
                # For now, choose the most damaged eligible Pokemon
                # TODO: Let player/agent choose if human player
                eligible_pokemon.sort(key=lambda x: x[1].damage_taken, reverse=True)
                location, target_pokemon = eligible_pokemon[0]
                
                old_damage = target_pokemon.damage_taken
                target_pokemon.damage_taken = max(0, target_pokemon.damage_taken - self.amount)
                healed = old_damage - target_pokemon.damage_taken
                battle_engine.log(f"Healed {healed} damage from {target_pokemon.name} ({location})")
            else:
                type_msg = f" {self.pokemon_type}" if self.pokemon_type else ""
                battle_engine.log(f"No damaged{type_msg} Pokemon to heal")
    
    def _matches_type(self, pokemon, pokemon_type: str) -> bool:
        """Check if Pokemon matches the specified type"""
        from v3.models.cards.energy import Energy
        
        # Map type strings to Energy.Type
        type_map = {
            'grass': Energy.Type.GRASS,
            'fire': Energy.Type.FIRE,
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
        
        type_lower = pokemon_type.lower()
        expected_type = type_map.get(type_lower)
        
        if expected_type:
            return pokemon.element == expected_type
        
        return False
    
    @classmethod
    def from_text(cls, effect_text: str) -> Optional['HealEffect']:
        """Parse heal effect from text"""
        # Pattern: "Heal X damage from this Pokémon."
        # Pattern: "Heal X damage from each of your Pokémon."
        # Pattern: "Heal X damage from 1 of your [Type] Pokemon."
        text_lower = effect_text.lower()
        
        # Try to match heal patterns
        # Note: Handle both "pokemon" and "pokémon" (with é)
        pattern1 = r'heal\s+(\d+)\s+damage\s+from\s+this\s+pok[ée]mon'
        pattern2 = r'heal\s+(\d+)\s+damage\s+from\s+each\s+of\s+your\s+pok[ée]mon'
        pattern3 = r'heal\s+(\d+)\s+damage\s+from\s+1\s+of\s+your\s+(\w+)\s+pok[ée]mon'
        pattern4 = r'heal\s+(\d+)\s+damage\s+from\s+1\s+of\s+your\s+pok[ée]mon'  # No type restriction
        
        match1 = re.search(pattern1, text_lower)
        match2 = re.search(pattern2, text_lower)
        match3 = re.search(pattern3, text_lower)
        match4 = re.search(pattern4, text_lower)
        
        if match1:
            amount = int(match1.group(1))
            return cls(amount, "this")
        elif match2:
            amount = int(match2.group(1))
            return cls(amount, "each")
        elif match3:
            amount = int(match3.group(1))
            pokemon_type = match3.group(2)
            return cls(amount, "one", pokemon_type)
        elif match4:
            amount = int(match4.group(1))
            return cls(amount, "one")
        
        return None

