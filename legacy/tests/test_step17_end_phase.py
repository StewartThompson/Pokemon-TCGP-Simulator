# Create test file: tests/test_step17_end_phase.py
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_end_phase():
    """Test end phase and turn switching"""
    deck = []
    for i in range(20):
        pokemon = Pokemon(f"test-{i:03d}", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                         Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
        deck.append(pokemon)
    
    player1 = Player("Player 1", deck.copy(), [Energy.Type.GRASS])
    player2 = Player("Player 2", deck.copy(), [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    # Set up Pokemon
    player1.draw_inital_hand()
    player2.draw_inital_hand()
    
    for card in player1.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player1.set_active_pokemon(card)
            player1.cards_in_hand.remove(card)
            break
    
    for card in player2.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player2.set_active_pokemon(card)
            player2.cards_in_hand.remove(card)
            break
    
    # Set some flags
    player1.active_pokemon.attacked_this_turn = True
    player1.active_pokemon.placed_or_evolved_this_turn = True
    initial_turns = player1.active_pokemon.turns_in_play
    
    # Test end turn
    engine._end_turn()
    
    # Check flags reset
    assert player1.active_pokemon.attacked_this_turn == False
    assert player1.active_pokemon.placed_or_evolved_this_turn == False
    assert player1.active_pokemon.turns_in_play == initial_turns + 1
    
    # Check player switched
    assert engine._get_current_player() == player2
    
    print("✓ End phase tests passed")
    return True

if __name__ == "__main__":
    success = test_end_phase()
    exit(0 if success else 1)

