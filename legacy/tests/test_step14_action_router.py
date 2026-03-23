# Create test file: tests/test_step14_action_router.py
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_action_router():
    """Test action execution router"""
    # Create setup
    deck = []
    for i in range(20):
        pokemon = Pokemon(f"test-{i:03d}", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                         Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
        deck.append(pokemon)
    player1 = Player("Player 1", deck, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    engine._setup_game()
    
    # Test end_turn action
    success = engine._execute_action("end_turn", player1)
    assert success
    
    # Test play_pokemon action
    if player1.cards_in_hand:
        for card in player1.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                # If active already exists, try bench instead
                if player1.active_pokemon:
                    action_str = f"play_pokemon_{card.id}_bench_0"
                    # Check if bench slot 0 is empty
                    if player1.bench_pokemons[0] is None:
                        success = engine._execute_action(action_str, player1)
                        assert success, f"Failed to play Pokemon to bench: {action_str}"
                        assert player1.bench_pokemons[0] == card
                else:
                    action_str = f"play_pokemon_{card.id}_active"
                    success = engine._execute_action(action_str, player1)
                    assert success, f"Failed to play Pokemon to active: {action_str}"
                    assert player1.active_pokemon == card
                break
    
    print("✓ Action router tests passed")
    return True

if __name__ == "__main__":
    success = test_action_router()
    exit(0 if success else 1)

