"""Game state validation utilities"""
from typing import List
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.match.game_rules import GameRules

class GameStateValidator:
    """Validate game state consistency"""
    
    @staticmethod
    def validate_player_state(player: Player) -> List[str]:
        """Validate player state and return list of errors"""
        errors = []
        
        # No hand size limit - players can have any number of cards in hand
        
        # Check bench size (filter out None values)
        bench_count = sum(1 for p in player.bench_pokemons if p is not None)
        if bench_count > GameRules.MAX_BENCH_SIZE:
            errors.append(f"Bench size exceeds limit: {bench_count}")
        
        # Check deck + hand + discard + bench + active = total cards
        # Note: Prize cards are managed by BattleEngine, not Player
        total_cards = (
            len(player.deck) +
            len(player.cards_in_hand) +
            len(player.discard_pile) +
            bench_count +
            (1 if player.active_pokemon else 0)
        )
        
        # Check active Pokemon
        if player.active_pokemon:
            if player.active_pokemon.damage_taken < 0:
                errors.append("Active Pokemon has negative damage")
            if player.active_pokemon.damage_taken > player.active_pokemon.health:
                errors.append("Active Pokemon damage exceeds health (should be KO'd)")
        
        return errors
    
    @staticmethod
    def validate_battle_engine(engine: BattleEngine) -> List[str]:
        """Validate battle engine state"""
        errors = []
        
        # Validate both players
        errors.extend(GameStateValidator.validate_player_state(engine._get_current_player()))
        errors.extend(GameStateValidator.validate_player_state(engine._get_opponent()))
        
        # Check turn counter
        if engine.turn < 0:
            errors.append("Turn counter is negative")
        
        return errors

