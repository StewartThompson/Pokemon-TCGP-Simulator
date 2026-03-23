"""Switch effect - switches Pokemon"""
from typing import Optional, TYPE_CHECKING
from .effect import Effect

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine
    from v3.models.cards.pokemon import Pokemon

class SwitchEffect(Effect):
    """Effect that switches Pokemon"""
    
    def __init__(self, target: str = "opponent_active"):
        self.target = target
    
    def execute(self, player, battle_engine, source=None):
        """Switch opponent's active Pokemon with bench"""
        opponent = battle_engine._get_opponent(player)
        if not opponent or not opponent.active_pokemon:
            battle_engine.log("No opponent active Pokemon to switch")
            return
        
        # Check if opponent has bench Pokemon
        available_bench = [i for i, bench in enumerate(opponent.bench_pokemons) if bench is not None]
        if not available_bench:
            battle_engine.log(f"{opponent.name} has no bench Pokemon to switch to")
            return
        
        # For AI agents, choose the first available bench Pokemon
        # For human players, they would choose (but we'll auto-select for now)
        bench_index = available_bench[0]
        bench_pokemon = opponent.bench_pokemons[bench_index]
        
        # Switch active with bench Pokemon
        old_active = opponent.active_pokemon
        from v3.models.cards.card import Card
        
        # Move old active to bench
        opponent.bench_pokemons[bench_index] = old_active
        old_active.card_position = Card.Position.BENCH
        
        # Move bench Pokemon to active
        opponent.active_pokemon = bench_pokemon
        bench_pokemon.card_position = Card.Position.ACTIVE
        
        battle_engine.log(f"{opponent.name} switched {old_active.name} to bench, {bench_pokemon.name} to active")
    
    @classmethod
    def from_text(cls, effect_text: str):
        """Parse switch effect from text"""
        text_lower = effect_text.lower()
        # Pattern: "Switch out your opponent's Active Pokemon to the Bench"
        if "switch" in text_lower and "opponent" in text_lower:
            return cls("opponent_active")
        if "switch" in text_lower or "force" in text_lower:
            return cls("opponent_active")
        return None

