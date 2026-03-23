"""Retreat action - retreat active Pokemon to bench"""
from typing import Optional
from .action import Action, ActionType
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card

class RetreatAction(Action):
    """Action to retreat active Pokemon to bench"""
    
    def __init__(self, bench_index: int):
        super().__init__(ActionType.RETREAT)
        self.bench_index = bench_index
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if retreat can be performed"""
        if not player.active_pokemon:
            return False, "No active Pokemon"
        
        if not player.active_pokemon.can_retreat():
            return False, "Pokemon cannot retreat"
        
        # Check retreat cost
        retreat_cost = player.active_pokemon.retreat_cost
        total_energy = sum(player.active_pokemon.equipped_energies.values())
        if total_energy < retreat_cost:
            return False, f"Not enough energy to retreat (need {retreat_cost}, have {total_energy})"
        
        # Check if there's a bench Pokemon to switch with
        has_bench = any(p is not None for p in player.bench_pokemons)
        if not has_bench:
            return False, "No Pokemon on bench to retreat to"
        
        # Check bench slot
        if self.bench_index < 0 or self.bench_index >= len(player.bench_pokemons):
            return False, f"Invalid bench index: {self.bench_index}"
        
        if player.bench_pokemons[self.bench_index] is not None:
            return False, f"Bench slot {self.bench_index} is occupied"
        
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        """Execute retreat"""
        active = player.active_pokemon
        
        # Discard energy equal to retreat cost
        energy_to_discard = active.retreat_cost
        discarded = 0
        
        # Discard energy (any type)
        for energy_type in list(active.equipped_energies.keys()):
            if discarded >= energy_to_discard:
                break
            if active.equipped_energies[energy_type] > 0:
                discard_amount = min(active.equipped_energies[energy_type], energy_to_discard - discarded)
                active.equipped_energies[energy_type] -= discard_amount
                discarded += discard_amount
        
        # Move to bench
        player.bench_pokemons[self.bench_index] = active
        active.card_position = Card.Position.BENCH
        
        # Move bench Pokemon to active (find first available)
        new_active = None
        for i, bench_pokemon in enumerate(player.bench_pokemons):
            if bench_pokemon and i != self.bench_index:
                new_active = bench_pokemon
                player.bench_pokemons[i] = None
                break
        
        if new_active:
            player.active_pokemon = new_active
            new_active.card_position = Card.Position.ACTIVE
        else:
            player.active_pokemon = None
        
        battle_engine.log(f"{player.name} retreated {active.name} to bench")
    
    def to_string(self) -> str:
        return f"retreat_{self.bench_index}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'RetreatAction':
        if not action_str.startswith("retreat_"):
            raise ValueError(f"Invalid action string: {action_str}")
        try:
            bench_index = int(action_str.split("_")[1])
            return cls(bench_index)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid retreat action format: {action_str}")

