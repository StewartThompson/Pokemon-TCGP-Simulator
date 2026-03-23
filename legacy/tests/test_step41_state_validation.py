"""Test Step 41: Implement Game State Validation Framework"""
import sys
sys.path.insert(0, '.')

from v3.models.match.state_validator import StateValidator
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy

def test_state_validation():
    """Test state validation framework"""
    # Create test players
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    deck = [basic] * 20
    
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Test valid state
    errors = StateValidator.validate_player(player)
    assert len(errors) == 0, f"Valid state should have no errors, got: {errors}"
    
    # Test that there's no hand size limit - add many cards
    while len(player.cards_in_hand) < 15 and len(player.deck) > 0:
        card = player.deck.pop(0)
        card.card_position = Card.Position.HAND
        player.cards_in_hand.append(card)
    
    # With 15+ cards in hand, there should be no hand size error
    errors = StateValidator.validate_player(player)
    assert not any("Hand size" in e for e in errors), f"Should not detect hand size error (no limit), got: {errors}"
    
    print("✓ State validation tests passed")
    return True

if __name__ == "__main__":
    success = test_state_validation()
    exit(0 if success else 1)

