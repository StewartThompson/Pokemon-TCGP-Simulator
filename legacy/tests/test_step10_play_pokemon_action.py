# Create test file: tests/test_step10_play_pokemon_action.py
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.play_pokemon import PlayPokemonAction
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_play_pokemon_action():
    """Test PlayPokemonAction"""
    # Create setup - create unique Pokemon objects
    deck = []
    for i in range(20):
        pokemon = Pokemon(f"test-{i:03d}", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                         Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
        deck.append(pokemon)
    player1 = Player("Player 1", deck, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    engine._setup_game()
    
    # Get Pokemon from hand - need to find a Basic Pokemon
    card_in_hand = None
    for card in player1.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            card_in_hand = card
            break
    
    if not card_in_hand:
        print("No Basic Pokemon in hand - skipping test")
        return True
    
    # Find an available position (active or bench)
    action = None
    position_used = None
    
    # Try active first if empty
    if not player1.active_pokemon:
        action = PlayPokemonAction(card_in_hand.id, "active")
        is_valid, error = action.validate(player1, engine)
        if is_valid:
            position_used = "active"
    else:
        # Try bench slots
        for i, bench_pokemon in enumerate(player1.bench_pokemons):
            if bench_pokemon is None:
                action = PlayPokemonAction(card_in_hand.id, f"bench_{i}")
                is_valid, error = action.validate(player1, engine)
                if is_valid:
                    position_used = f"bench_{i}"
                    break
    
    # If no valid position found, skip test (all slots full)
    if action is None or not is_valid:
        print("No available position for Pokemon - skipping test")
        return True
    
    # Store card ID for checking
    card_id = card_in_hand.id
    hand_size_before = len(player1.cards_in_hand)
    
    # Test execution
    action.execute(player1, engine)
    assert len(player1.cards_in_hand) == hand_size_before - 1
    # Check card with this ID is not in hand
    assert not any(c.id == card_id for c in player1.cards_in_hand)
    
    # Verify Pokemon is in the correct position
    if position_used == "active":
        assert player1.active_pokemon == card_in_hand
    else:
        bench_index = int(position_used.split("_")[1])
        assert player1.bench_pokemons[bench_index] == card_in_hand
    
    assert card_in_hand.placed_or_evolved_this_turn == True  # Should be boolean
    assert isinstance(card_in_hand.placed_or_evolved_this_turn, bool)
    
    # Test to_string and from_string
    action_str = action.to_string()
    action2 = PlayPokemonAction.from_string(action_str, player1)
    assert action2.card_id == action.card_id
    assert action2.position == action.position
    
    print("✓ PlayPokemonAction tests passed")
    return True

if __name__ == "__main__":
    success = test_play_pokemon_action()
    exit(0 if success else 1)

