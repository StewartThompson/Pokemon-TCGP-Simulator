"""Game state validation framework"""
from typing import List, Optional
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.match.game_rules import GameRules

class StateValidator:
    """Validate game state consistency"""
    
    @staticmethod
    def validate_player(player: Player, context: str = "") -> List[str]:
        """Validate player state"""
        errors = []
        
        # No hand size limit - players can have any number of cards in hand
        
        # Bench size check (filter out None values)
        bench_count = sum(1 for p in player.bench_pokemons if p is not None)
        if bench_count > GameRules.MAX_BENCH_SIZE:
            errors.append(f"{context}Bench size {bench_count} > {GameRules.MAX_BENCH_SIZE}")
        
        # Card count consistency (prize cards managed by BattleEngine, not Player)
        total = (
            len(player.deck) +
            len(player.cards_in_hand) +
            len(player.discard_pile) +
            bench_count +
            (1 if player.active_pokemon else 0)
        )
        # Note: Prize cards are managed by BattleEngine, so we don't include them here
        
        # Active Pokemon validation
        if player.active_pokemon:
            pokemon = player.active_pokemon
            if pokemon.damage_taken < 0:
                errors.append(f"{context}Active Pokemon has negative damage: {pokemon.damage_taken}")
            if pokemon.damage_taken > pokemon.health:
                errors.append(f"{context}Active Pokemon damage exceeds health: {pokemon.damage_taken}/{pokemon.health}")
        
        return errors
    
    @staticmethod
    def validate_battle_engine(engine: BattleEngine) -> List[str]:
        """Validate entire battle engine state"""
        errors = []
        
        current = engine._get_current_player()
        opponent = engine._get_opponent()
        
        errors.extend(StateValidator.validate_player(current, f"[{current.name}] "))
        errors.extend(StateValidator.validate_player(opponent, f"[{opponent.name}] "))
        
        # Turn counter
        if engine.turn < 0:
            errors.append(f"Invalid turn counter: {engine.turn}")
        
        return errors
    
    @staticmethod
    def assert_valid(player: Optional[Player] = None, engine: Optional[BattleEngine] = None):
        """Assert state is valid, raise exception if not"""
        from v3.models.match.exceptions import StateError
        errors = []
        if player:
            errors.extend(StateValidator.validate_player(player))
        if engine:
            errors.extend(StateValidator.validate_battle_engine(engine))
        
        if errors:
            raise StateError(f"State validation failed:\n" + "\n".join(errors))

