"""Test Step 0.5: Testing Infrastructure"""
import sys
sys.path.insert(0, '.')

from tests.test_helpers import (
    create_test_pokemon,
    create_test_deck,
    create_test_players,
    create_test_battle_engine
)
from tests.test_validators import GameStateValidator

def test_test_utilities():
    """Test that test utilities work correctly"""
    # Test Pokemon creation
    pokemon = create_test_pokemon()
    assert pokemon.name == "Test Pokemon"
    assert pokemon.health == 100
    
    # Test deck creation
    deck = create_test_deck(20)
    assert len(deck) == 20
    
    # Test players creation
    player1, player2 = create_test_players()
    assert player1.name == "Player 1"
    assert player2.name == "Player 2"
    
    # Test battle engine creation
    engine = create_test_battle_engine()
    assert engine is not None
    
    # Test validator
    errors = GameStateValidator.validate_player_state(player1)
    # Should be empty for valid state (or have some expected errors before game setup)
    assert isinstance(errors, list)
    
    print("✓ Test utilities work correctly")
    return True

if __name__ == "__main__":
    success = test_test_utilities()
    exit(0 if success else 1)

