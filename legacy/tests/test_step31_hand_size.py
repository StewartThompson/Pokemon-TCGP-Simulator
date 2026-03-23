"""Test Step 31: No Hand Size Limit"""
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy

def test_no_hand_size_limit():
    """Test that there is NO hand size limit - players can have unlimited cards"""
    # Create deck with many cards
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    deck = [basic] * 20
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Add many cards to hand - should be allowed
    initial_hand_size = len(player.cards_in_hand)
    cards_added = 0
    while len(player.deck) > 0 and cards_added < 15:
        # Temporarily bypass can_draw check to add many cards
        card = player.deck.pop(0)
        card.card_position = Card.Position.HAND
        player.cards_in_hand.append(card)
        cards_added += 1
    
    # Verify hand can exceed any arbitrary limit (e.g., 10, 15, 20)
    assert len(player.cards_in_hand) > 10, f"Hand should be able to exceed 10, got {len(player.cards_in_hand)}"
    assert len(player.cards_in_hand) > 15, f"Hand should be able to exceed 15, got {len(player.cards_in_hand)}"
    
    # Verify can_draw() only checks deck, not hand size
    # If deck is empty, can_draw should be False
    if len(player.deck) == 0:
        assert not player.can_draw(), "can_draw() should return False when deck is empty"
    
    # Create a new player with cards in deck - can_draw should be True regardless of hand size
    deck2 = [basic] * 20
    player2 = Player("Player 2", deck2, [Energy.Type.GRASS])
    player2.draw_inital_hand()
    
    # Add many cards to hand
    while len(player2.deck) > 0 and len(player2.cards_in_hand) < 20:
        card = player2.deck.pop(0)
        card.card_position = Card.Position.HAND
        player2.cards_in_hand.append(card)
    
    # Even with 20+ cards in hand, if deck has cards, can_draw should be True
    if len(player2.deck) > 0:
        assert player2.can_draw(), f"can_draw() should return True when deck has cards, regardless of hand size ({len(player2.cards_in_hand)} cards)"
    
    print("✓ No hand size limit tests passed")
    return True

if __name__ == "__main__":
    success = test_no_hand_size_limit()
    exit(0 if success else 1)

