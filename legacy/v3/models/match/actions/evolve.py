"""Evolve action - evolve a Pokemon"""
from typing import Optional
from .action import Action, ActionType
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.match.game_rules import GameRules

class EvolveAction(Action):
    """Action to evolve a Pokemon"""
    
    def __init__(self, evolution_card_id: str, target_location: str):
        super().__init__(ActionType.EVOLVE)
        self.evolution_card_id = evolution_card_id
        self.target_location = target_location  # "active" or "bench_{index}"
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if evolution can be performed"""
        # Find evolution card in hand
        evolution_card = next((c for c in player.cards_in_hand if c.id == self.evolution_card_id), None)
        if not evolution_card:
            return False, f"Evolution card {self.evolution_card_id} not in hand"
        
        if not isinstance(evolution_card, Pokemon):
            return False, "Evolution card must be a Pokemon"
        
        # Get target Pokemon
        target = self._get_target_pokemon(player)
        if not target:
            return False, f"No Pokemon at location: {self.target_location}"
        
        # Check if Pokemon has already been evolved this turn
        if target.placed_or_evolved_this_turn:
            return False, "This Pokemon has already been evolved this turn (limit: 1 evolution per Pokemon per turn)"
        
        # Check first turn restriction - neither player can evolve on first turn
        if battle_engine.turn == 1:
            return False, "Cannot evolve on first turn"
        
        # Check if Rare Candy was used this turn (allows Basic -> Stage 2)
        allow_rare_candy = getattr(player, 'used_rare_candy_this_turn', False)
        
        # Check evolution rules
        if not GameRules.can_evolve(target, evolution_card, allow_rare_candy=allow_rare_candy):
            return False, "Evolution rules not met"
        
        return True, None
    
    def _get_target_pokemon(self, player) -> Optional[Pokemon]:
        """Get Pokemon at target location"""
        if self.target_location == "active":
            return player.active_pokemon
        elif self.target_location.startswith("bench_"):
            try:
                bench_index = int(self.target_location.split("_")[1])
                if 0 <= bench_index < len(player.bench_pokemons):
                    return player.bench_pokemons[bench_index]
            except (ValueError, IndexError):
                pass
        return None
    
    def execute(self, player, battle_engine) -> None:
        """Execute evolution"""
        evolution_card = next((c for c in player.cards_in_hand if c.id == self.evolution_card_id), None)
        target = self._get_target_pokemon(player)
        
        if not evolution_card or not target:
            raise ValueError("Evolution card or target not found")
        
        # Remove evolution card from hand
        player.cards_in_hand.remove(evolution_card)
        
        # Transfer properties from target to evolution
        evolution_card.damage_taken = target.damage_taken
        evolution_card.equipped_energies = target.equipped_energies.copy()
        evolution_card.turns_in_play = target.turns_in_play
        evolution_card.placed_or_evolved_this_turn = True
        
        # Remove all status effects when evolving
        evolution_card.status_effects = []
        
        # Replace target with evolution
        if self.target_location == "active":
            player.active_pokemon = evolution_card
            evolution_card.card_position = Card.Position.ACTIVE
        else:
            bench_index = int(self.target_location.split("_")[1])
            player.bench_pokemons[bench_index] = evolution_card
            evolution_card.card_position = Card.Position.BENCH
        
        # Discard old Pokemon
        target.card_position = Card.Position.DISCARD
        player.discard_card(target)
        
        battle_engine.log(f"{player.name} evolved {target.name} into {evolution_card.name}")
    
    def to_string(self) -> str:
        return f"evolve_{self.evolution_card_id}_{self.target_location}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'EvolveAction':
        if not action_str.startswith("evolve_"):
            raise ValueError(f"Invalid action string: {action_str}")
        parts = action_str.replace("evolve_", "").split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid evolution action format: {action_str}")
        return cls(parts[0], parts[1])

