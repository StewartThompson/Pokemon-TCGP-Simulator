# Create test file: tests/test_step4_game_rules.py
import sys
sys.path.insert(0, '.')

from v3.models.match.game_rules import GameRules, GamePhase
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy

def test_game_rules():
    """Test GameRules constants and methods"""
    # Test constants
    assert GameRules.DECK_SIZE == 20
    assert GameRules.MAX_BENCH_SIZE == 3
    assert GameRules.WINNING_POINTS == 3
    assert GameRules.WEAKNESS_BONUS == 20
    
    # Test GamePhase enum
    assert GamePhase.SETUP.value == "setup"
    assert GamePhase.DRAW.value == "draw"
    
    # Test calculate_prize_value
    normal_pokemon = Pokemon("test-001", "Test", Energy.Type.GRASS, Card.Type.POKEMON,
                             Card.Subtype.BASIC, 50, "Set", "Pack", "Common", [], 1, None, None)
    ex_pokemon = Pokemon("test-002", "Test ex", Energy.Type.GRASS, Card.Type.POKEMON,
                         Card.Subtype.BASIC, 100, "Set", "Pack", "Rare", [], 1, None, None)
    
    assert GameRules.calculate_prize_value(normal_pokemon) == 1
    assert GameRules.calculate_prize_value(ex_pokemon) == 2
    assert isinstance(GameRules.calculate_prize_value(normal_pokemon), int)  # Verify return type
    
    print("✓ GameRules tests passed")
    return True

if __name__ == "__main__":
    success = test_game_rules()
    exit(0 if success else 1)

