from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from v3.models.cards.pokemon import Pokemon
    from v3.models.cards.card import Card

class GamePhase(Enum):
    SETUP = "setup"
    TURN_ZERO = "turn_zero"
    DRAW = "draw"
    MAIN = "main"
    ATTACK = "attack"
    END = "end"

class GameRules:
    """Centralized game rules and constants"""
    DECK_SIZE = 20
    MAX_BENCH_SIZE = 3
    WINNING_POINTS = 3
    PRIZE_CARDS = 3  # Number of prize cards (points) needed to win
    INITIAL_HAND_SIZE = 5
    MAX_TURNS = 100  # Maximum number of turns before game ends in a draw
    
    # Evolution stages
    BASIC = "basic"
    STAGE1 = "stage1"
    STAGE2 = "stage2"
    
    # Weakness modifier (Pokemon TCG Pocket uses +20)
    WEAKNESS_BONUS = 20


    
    @staticmethod
    def can_evolve(target: 'Pokemon', evolution: 'Pokemon', allow_rare_candy: bool = False) -> bool:
        """Check evolution rules
        
        Args:
            target: The Pokemon to evolve
            evolution: The evolution card
            allow_rare_candy: If True, allows Basic -> Stage 2 evolution (Rare Candy effect)
        """
        if not hasattr(target, 'turns_in_play') or target.turns_in_play < 1:
            return False
        
        # Check evolution chain matches
        if evolution.evolves_from and evolution.evolves_from != target.name:
            return False
        
        # Map subtypes to stages
        from v3.models.cards.card import Card
        stage_map = {
            Card.Subtype.BASIC: GameRules.BASIC,
            Card.Subtype.STAGE_1: GameRules.STAGE1,
            Card.Subtype.STAGE_2: GameRules.STAGE2,
        }
        
        target_stage = stage_map.get(target.subtype)
        evolution_stage = stage_map.get(evolution.subtype)
        
        if target_stage == GameRules.BASIC and evolution_stage == GameRules.STAGE1:
            return True
        if target_stage == GameRules.STAGE1 and evolution_stage == GameRules.STAGE2:
            return True
        
        # Rare Candy: Basic -> Stage 2 (if evolution chain matches)
        if allow_rare_candy and target_stage == GameRules.BASIC and evolution_stage == GameRules.STAGE2:
            # Check if the Stage 2 evolves from the Basic (via evolution chain)
            # For example, Bulbasaur -> Venusaur (if Venusaur.evolves_from == "Bulbasaur" or "Ivysaur")
            # We need to check if there's a valid evolution chain
            if evolution.evolves_from:
                # Check if evolution chain matches (e.g., Venusaur evolves from Ivysaur, which evolves from Bulbasaur)
                # For Rare Candy, we allow if the Stage 2's evolves_from matches the Basic's name
                # OR if we can trace the chain
                if evolution.evolves_from == target.name:
                    return True
                # Also check if there's an intermediate stage that matches
                # For now, we'll be lenient and allow if the name matches part of the chain
                # This is a simplification - in real game, you'd need to check the full chain
                return True  # Allow Basic -> Stage 2 with Rare Candy
        
        return False
    
    @staticmethod
    def calculate_prize_value(pokemon: 'Pokemon') -> int:  # FIX: return type is int
        """Calculate prize points for knocking out Pokemon"""
        # Check if EX Pokemon
        if hasattr(pokemon, 'is_ex') and pokemon.is_ex:
            return 2
        if pokemon.name.endswith(' ex'):
            return 2
        return 1
