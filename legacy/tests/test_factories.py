"""Factory classes for creating test data"""
from typing import List
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.attack import Attack
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from test_helpers import create_test_pokemon, create_test_attack

class PokemonFactory:
    """Factory for creating Pokemon with common configurations"""
    
    @staticmethod
    def basic_grass(health: int = 70) -> Pokemon:
        return create_test_pokemon(
            name="Basic Grass",
            health=health,
            pokemon_type=Energy.Type.GRASS
        )
    
    @staticmethod
    def with_attack(attack_name: str, damage: int, cost: List[str]) -> Pokemon:
        attack = create_test_attack(attack_name, damage, cost)
        return create_test_pokemon(attacks=[attack])
    
    @staticmethod
    def evolution_chain() -> tuple[Pokemon, Pokemon, Pokemon]:
        """Create Basic -> Stage 1 -> Stage 2 evolution chain"""
        basic = create_test_pokemon(
            name="Basic",
            health=70,
            subtype=Card.Subtype.BASIC
        )
        stage1 = create_test_pokemon(
            name="Stage 1",
            health=90,
            subtype=Card.Subtype.STAGE_1,
            evolves_from="Basic"
        )
        stage2 = create_test_pokemon(
            name="Stage 2",
            health=120,
            subtype=Card.Subtype.STAGE_2,
            evolves_from="Stage 1"
        )
        return basic, stage1, stage2

