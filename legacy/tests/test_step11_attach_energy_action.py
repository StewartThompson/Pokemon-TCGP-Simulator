# Create test file: tests/test_step11_attach_energy_action.py
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.attach_energy import AttachEnergyAction
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_attach_energy_action():
    """Test AttachEnergyAction"""
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
    
    # Set active Pokemon
    if player1.cards_in_hand:
        pokemon_card = None
        for card in player1.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                pokemon_card = card
                break
        if pokemon_card:
            player1.set_active_pokemon(pokemon_card)
            player1.cards_in_hand.remove(pokemon_card)
    
    # Generate energy
    player1.energy_zone.generate_energy()
    
    # Test action
    action = AttachEnergyAction("active")
    is_valid, error = action.validate(player1, engine)
    assert is_valid, f"Validation failed: {error}"
    
    # Check initial energy
    initial_energy = player1.active_pokemon.equipped_energies[Energy.Type.GRASS]
    
    # Execute
    action.execute(player1, engine)
    
    # Verify energy attached
    assert player1.active_pokemon.equipped_energies[Energy.Type.GRASS] == initial_energy + 1
    
    print("✓ AttachEnergyAction tests passed")
    return True

if __name__ == "__main__":
    success = test_attach_energy_action()
    exit(0 if success else 1)

