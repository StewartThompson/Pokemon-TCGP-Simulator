from typing import Optional
from .action import Action, ActionType
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.match.game_rules import GamePhase

class PlayPokemonAction(Action):
    """Action to play a Pokemon card from hand"""
    
    def __init__(self, card_id: str, position: str):
        super().__init__(ActionType.PLAY_POKEMON)
        self.card_id = card_id
        self.position = position  # "active" or "bench_{index}"
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if Pokemon can be played"""
        # During setup phase (turn zero), allow multiple Pokemon
        # Otherwise, check if already played Pokemon this turn (limit: 1 per turn)
        if battle_engine.phase != GamePhase.SETUP and player.played_pokemon_this_turn:
            return False, "Already played a Pokemon this turn (limit: 1 per turn)"
        
        # Find card in hand
        card = next((c for c in player.cards_in_hand if c.id == self.card_id), None)
        if not card:
            return False, f"Card {self.card_id} not in hand"
        
        # Check is Pokemon
        if not isinstance(card, Pokemon):
            return False, f"Card {self.card_id} is not a Pokemon"
        
        # Check is Basic
        if card.subtype != Card.Subtype.BASIC:
            return False, "Can only play Basic Pokemon from hand"
        
        # Validate position
        if self.position == "active":
            if player.active_pokemon is not None:
                return False, "Active position already occupied"
        elif self.position == "bench":
            # Check if there's any empty bench slot
            if not any(bench_pokemon is None for bench_pokemon in player.bench_pokemons):
                return False, "No empty bench slots available"
        elif self.position.startswith("bench_"):
            # Legacy format with index (for backward compatibility)
            try:
                bench_index = int(self.position.split("_")[1])
                if bench_index < 0 or bench_index >= len(player.bench_pokemons):
                    return False, f"Invalid bench index: {bench_index}"
                if player.bench_pokemons[bench_index] is not None:
                    return False, f"Bench slot {bench_index} already occupied"
            except (ValueError, IndexError):
                return False, f"Invalid position format: {self.position}"
        else:
            return False, f"Invalid position: {self.position}"
        
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        """Execute playing Pokemon"""
        # During setup phase (turn zero), allow multiple Pokemon
        # Otherwise, check if already played Pokemon this turn
        if battle_engine.phase != GamePhase.SETUP and player.played_pokemon_this_turn:
            raise ValueError("Already played a Pokemon this turn (limit: 1 per turn)")
        
        # Find card
        card = next((c for c in player.cards_in_hand if c.id == self.card_id), None)
        if not card or not isinstance(card, Pokemon):
            raise ValueError(f"Card {self.card_id} not found or not Pokemon")
        
        # Remove from hand
        player.cards_in_hand.remove(card)
        
        # Place Pokemon
        if self.position == "active":
            player.set_active_pokemon(card)
        elif self.position == "bench":
            # Find first empty bench slot (0, 1, 2)
            bench_index = None
            for i, bench_pokemon in enumerate(player.bench_pokemons):
                if bench_pokemon is None:
                    bench_index = i
                    break
            if bench_index is None:
                raise ValueError("No empty bench slots available")
            player.add_to_bench(card, bench_index)
        else:
            # Legacy format with index
            bench_index = int(self.position.split("_")[1])
            player.add_to_bench(card, bench_index)
        
        # Set flags
        card.placed_or_evolved_this_turn = True
        card.turns_in_play = 0
        
        # Mark that Pokemon was played this turn (only if not in setup phase)
        if battle_engine.phase != GamePhase.SETUP:
            player.played_pokemon_this_turn = True
        
        battle_engine.log(f"{player.name} played {card.name} to {self.position}")
    
    def to_string(self) -> str:
        return f"play_pokemon_{self.card_id}_{self.position}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'PlayPokemonAction':
        # Format: "play_pokemon_{card_id}_{position}"
        if not action_str.startswith("play_pokemon_"):
            raise ValueError(f"Invalid action string: {action_str}")
        
        parts = action_str.replace("play_pokemon_", "").split("_", 1)
        if len(parts) < 1:
            raise ValueError(f"Invalid action string format: {action_str}")
        
        card_id = parts[0]
        if len(parts) == 1:
            # No position specified, default to bench
            position = "bench"
        elif parts[1] == "active":
            position = "active"
        elif parts[1] == "bench":
            position = "bench"
        elif parts[1].startswith("bench_"):
            # Legacy format with index
            position = parts[1]
        else:
            # Assume it's a bench index
            position = f"bench_{parts[1]}"
        
        return cls(card_id, position)

