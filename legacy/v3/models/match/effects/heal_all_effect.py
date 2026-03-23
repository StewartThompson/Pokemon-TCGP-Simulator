"""Heal all effect - heals all Pokemon"""
from typing import Optional, TYPE_CHECKING
import re
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class HealAllEffect(Effect):
    """Effect that heals all Pokemon (active + bench)"""
    
    def __init__(self, amount: int, target: str = "your_all"):
        self.amount = amount
        self.target = target
    
    def execute(self, player, battle_engine, source=None):
        """Heal all Pokemon"""
        pokemon_list = []
        if player.active_pokemon:
            pokemon_list.append(player.active_pokemon)
        pokemon_list.extend([p for p in player.bench_pokemons if p is not None])
        
        for pokemon in pokemon_list:
            if pokemon.damage_taken > 0:
                heal_amount = min(self.amount, pokemon.damage_taken)
                pokemon.damage_taken -= heal_amount
                battle_engine.log(f"Healed {heal_amount} damage from {pokemon.name}")
    
    @classmethod
    def from_text(cls, effect_text: str):
        text_lower = effect_text.lower()
        if "heal" in text_lower and ("each" in text_lower or "all" in text_lower):
            # Parse amount
            match = re.search(r'heal (\d+) damage', text_lower)
            if match:
                amount = int(match.group(1))
                return cls(amount, "your_all")
        return None

