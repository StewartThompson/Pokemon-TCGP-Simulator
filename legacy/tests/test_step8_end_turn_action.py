# Create test file: tests/test_step8_end_turn_action.py
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.end_turn import EndTurnAction
from v3.models.match.actions.action import ActionType  # FIX: Add this import
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_end_turn_action():
    """Test EndTurnAction"""
    # Create minimal setup
    deck = [Pokemon("test-001", "Test", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 50, "Set", "Pack", "Common", [], 1, None, None)] * 20
    player1 = Player("Player 1", deck, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    # Test action creation
    action = EndTurnAction()
    assert action.action_type == ActionType.END_TURN
    
    # Test validation
    is_valid, error = action.validate(player1, engine)
    assert is_valid
    assert error is None
    
    # Test to_string
    assert action.to_string() == "end_turn"
    
    # Test from_string
    action2 = EndTurnAction.from_string("end_turn", player1)
    assert isinstance(action2, EndTurnAction)
    
    print("✓ EndTurnAction tests passed")
    return True

if __name__ == "__main__":
    success = test_end_turn_action()
    exit(0 if success else 1)

