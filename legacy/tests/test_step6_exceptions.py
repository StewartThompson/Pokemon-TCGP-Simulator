# Create test file: tests/test_step6_exceptions.py
import sys
sys.path.insert(0, '.')

from v3.models.match.exceptions import (
    BattleEngineError, InvalidActionError, RuleViolationError, StateError
)

def test_exceptions():
    """Test exception classes"""
    # Test InvalidActionError
    try:
        raise InvalidActionError("play_pokemon_test", "Card not in hand")
    except InvalidActionError as e:
        assert e.action == "play_pokemon_test"
        assert e.reason == "Card not in hand"
        assert isinstance(e, BattleEngineError)
    
    # Test RuleViolationError
    try:
        raise RuleViolationError("Cannot evolve", "Pokemon not in play long enough")
    except RuleViolationError as e:
        assert e.rule == "Cannot evolve"
        assert isinstance(e, BattleEngineError)
    
    # Test StateError
    try:
        raise StateError("Player has negative points")
    except StateError as e:
        assert "negative points" in e.message
        assert isinstance(e, BattleEngineError)
    
    print("✓ Exception classes tests passed")
    return True

if __name__ == "__main__":
    success = test_exceptions()
    exit(0 if success else 1)

