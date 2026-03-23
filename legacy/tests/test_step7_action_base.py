# Create test file: tests/test_step7_action_base.py
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.action import Action, ActionType

def test_action_base():
    """Test Action base class"""
    # Test ActionType enum
    assert ActionType.PLAY_POKEMON.value == "play_pokemon"
    assert ActionType.END_TURN.value == "end_turn"
    
    # Test that Action is abstract
    try:
        action = Action(ActionType.END_TURN)
        assert False, "Should not be able to instantiate abstract Action"
    except TypeError:
        pass  # Expected
    
    print("✓ Action base class tests passed")
    return True

if __name__ == "__main__":
    success = test_action_base()
    exit(0 if success else 1)

