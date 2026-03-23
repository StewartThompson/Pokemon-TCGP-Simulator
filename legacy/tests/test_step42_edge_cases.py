"""Test Step 42: Implement Edge Case Handling"""
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy

def test_empty_deck():
    """Test deck-out scenario"""
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    # Create player with empty deck
    deck = [basic] * 20
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Empty the deck
    player.deck = []
    
    # Try to draw (should handle gracefully)
    deck2 = [basic] * 20  # Fresh deck for player2
    player2 = Player("Player 2", deck2, [Energy.Type.GRASS])
    engine = BattleEngine(player, player2, debug=False)
    
    # Draw phase should handle empty deck
    engine._draw_phase(player)
    assert len(player.deck) == 0, "Deck should remain empty"
    
    print("✓ Empty deck edge case test passed")
    return True

def test_no_hand_size_limit():
    """Test that there is no hand size limit"""
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    deck = [basic] * 20
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Fill hand to 15+ cards - should be allowed
    while len(player.cards_in_hand) < 15 and len(player.deck) > 0:
        card = player.deck.pop(0)
        card.card_position = Card.Position.HAND
        player.cards_in_hand.append(card)
    
    # Draw one more (should work fine - no hand size limit)
    deck2 = [basic] * 20  # Fresh deck for player2
    player2 = Player("Player 2", deck2, [Energy.Type.GRASS])
    engine = BattleEngine(player, player2, debug=False)
    
    initial_hand_size = len(player.cards_in_hand)
    if len(player.deck) > 0:
        engine._draw_phase(player)
        # Hand should have increased by 1 (or stayed same if deck was empty)
        assert len(player.cards_in_hand) >= initial_hand_size, f"Hand size should not decrease, got {len(player.cards_in_hand)} from {initial_hand_size}"
    
    # Hand can be any size - no limit
    assert len(player.cards_in_hand) >= 15, f"Hand should be able to have 15+ cards, got {len(player.cards_in_hand)}"
    
    print("✓ No hand size limit edge case test passed")
    return True

def test_no_bench_retreat():
    """Test retreat with no bench Pokemon"""
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    deck = [basic] * 20
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player.set_active_pokemon(card)
            player.cards_in_hand.remove(card)
            break
    
    # Ensure no bench Pokemon
    player.bench_pokemons = [None, None, None]
    
    # Add energy so energy check doesn't fail first
    player.active_pokemon.equipped_energies[Energy.Type.GRASS] = 1
    
    # Try to retreat (should fail)
    from v3.models.match.actions.retreat import RetreatAction
    action = RetreatAction(0)
    deck2 = [basic] * 20  # Fresh deck for player2
    player2 = Player("Player 2", deck2, [Energy.Type.GRASS])
    engine = BattleEngine(player, player2, debug=False)
    
    is_valid, error = action.validate(player, engine)
    assert not is_valid, "Retreat should fail with no bench Pokemon"
    assert "No Pokemon on bench" in error, f"Error should mention no bench, got: {error}"
    
    print("✓ No bench retreat edge case test passed")
    return True

def run_all_edge_case_tests():
    """Run all edge case tests"""
    tests = [test_empty_deck, test_no_hand_size_limit, test_no_bench_retreat]
    results = {}
    for test in tests:
        try:
            success = test()
            results[test.__name__] = success
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            results[test.__name__] = False
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nEdge Case Tests: {passed}/{total} passed")
    return all(results.values())

if __name__ == "__main__":
    success = run_all_edge_case_tests()
    exit(0 if success else 1)

