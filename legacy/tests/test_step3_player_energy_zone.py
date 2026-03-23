# Create test file: tests/test_step3_player_energy_zone.py
import sys
sys.path.insert(0, '.')

from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_player_energy_zone():
    """Test Player with EnergyZone"""
    # Create minimal deck (just for testing)
    deck = [Pokemon("test-001", "Test", Energy.Type.GRASS, Card.Type.POKEMON, 
                    Card.Subtype.BASIC, 50, "Set", "Pack", "Common", [], 1, None, None)]
    deck = deck * 20  # Make 20 cards
    
    player = Player("Test Player", deck, [Energy.Type.GRASS, Energy.Type.FIRE])
    
    # Test EnergyZone is created
    assert player.energy_zone is not None
    assert hasattr(player.energy_zone, 'current_energy')
    
    # Test properties
    player.energy_zone.generate_energy()
    assert player.energy_zone_current_energy is not None
    assert player.energy_zone_next_energy is not None
    
    print("✓ Player EnergyZone tests passed")
    return True

if __name__ == "__main__":
    success = test_player_energy_zone()
    exit(0 if success else 1)

