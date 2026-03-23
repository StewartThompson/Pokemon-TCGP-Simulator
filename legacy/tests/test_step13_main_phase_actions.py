# Create test file: tests/test_step13_main_phase_actions.py
import sys
sys.path.insert(0, '.')

from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.attack import Attack

def test_main_phase_actions():
    """Test main phase action generation"""
    # Create Pokemon with attack
    attack = Attack("Vine Whip", 40, Energy.from_string_list(["Grass", "Colorless"]))
    deck = []
    for i in range(20):
        pokemon = Pokemon(f"test-{i:03d}", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                         Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [attack], 1, Energy.Type.FIRE, None)
        deck.append(pokemon)
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player.set_active_pokemon(card)
            player.cards_in_hand.remove(card)
            break
    
    # Get actions
    actions = player._get_actions()
    
    # Should have end_turn
    assert "end_turn" in actions
    
    # Should have attach_energy if energy available
    player.energy_zone.generate_energy()
    actions2 = player._get_actions()
    assert "attach_energy_active" in actions2
    
    # Should have attack if energy attached
    player.active_pokemon.equipped_energies[Energy.Type.GRASS] = 1
    player.active_pokemon.equipped_energies[Energy.Type.NORMAL] = 1
    actions3 = player._get_actions()
    assert any("attack_" in a for a in actions3)
    
    print("✓ Main phase actions tests passed")
    return True

if __name__ == "__main__":
    success = test_main_phase_actions()
    exit(0 if success else 1)

