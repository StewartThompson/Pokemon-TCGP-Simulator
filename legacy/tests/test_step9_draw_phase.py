# Create test file: tests/test_step9_draw_phase.py
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_draw_phase():
    """Test draw phase"""
    # Create decks
    deck1 = [Pokemon("test-001", "Test", Energy.Type.GRASS, Card.Type.POKEMON,
                    Card.Subtype.BASIC, 50, "Set", "Pack", "Common", [], 1, None, None)] * 20
    deck2 = deck1.copy()
    
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    # Setup game
    engine._setup_game()
    
    # Test draw phase
    initial_hand_size = len(player1.cards_in_hand)
    initial_deck_size = len(player1.deck)
    
    engine._draw_phase(player1)
    
    # Check card was drawn
    assert len(player1.cards_in_hand) == initial_hand_size + 1
    assert len(player1.deck) == initial_deck_size - 1
    
    # Test deck-out
    player1.deck = []  # Empty deck
    engine._draw_phase(player1)
    # Should not crash, game should end
    
    print("✓ Draw phase tests passed")
    return True

if __name__ == "__main__":
    success = test_draw_phase()
    exit(0 if success else 1)

