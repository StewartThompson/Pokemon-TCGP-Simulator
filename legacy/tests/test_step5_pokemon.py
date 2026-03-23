# Create test file: tests/test_step5_pokemon.py
import sys
sys.path.insert(0, '.')

from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.cards.attack import Attack

def test_pokemon():
    """Test Pokemon model fixes"""
    # Create test Pokemon - NOTE: Attack.damage must be int, not string
    attacks = [Attack("Test Attack", 40, Energy.from_string_list(["Grass", "Colorless"]))]
    pokemon = Pokemon("test-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                     Card.Subtype.BASIC, 70, "Set", "Pack", "Common", attacks, 1, Energy.Type.FIRE, None)
    
    # Test turns_in_play
    assert hasattr(pokemon, 'turns_in_play')
    assert pokemon.turns_in_play == 0
    assert isinstance(pokemon.turns_in_play, int)
    
    # Test attacked_this_turn
    assert hasattr(pokemon, 'attacked_this_turn')
    assert pokemon.attacked_this_turn == False
    assert isinstance(pokemon.attacked_this_turn, bool)
    
    # Test placed_or_evolved_this_turn is now boolean
    assert isinstance(pokemon.placed_or_evolved_this_turn, bool)
    assert pokemon.placed_or_evolved_this_turn == False
    
    # Test is_ex property
    assert not pokemon.is_ex
    ex_pokemon = Pokemon("test-002", "Venusaur ex", Energy.Type.GRASS, Card.Type.POKEMON,
                        Card.Subtype.STAGE_2, 190, "Set", "Pack", "Rare", [], 3, Energy.Type.FIRE, "Ivysaur")
    assert ex_pokemon.is_ex
    
    # Test equipped_energies uses Energy.Type
    assert isinstance(pokemon.equipped_energies, dict)
    assert Energy.Type.GRASS in pokemon.equipped_energies
    # Note: Energy.Type.GRASS is actually the string 'grass', so this check is valid
    # The important thing is we're using Energy.Type constants, not hardcoded strings
    
    # Test get_possible_attacks (no energy, should return empty)
    assert len(pokemon.get_possible_attacks()) == 0
    
    # Add energy and test again
    pokemon.equipped_energies[Energy.Type.GRASS] = 1
    pokemon.equipped_energies[Energy.Type.NORMAL] = 1
    possible = pokemon.get_possible_attacks()
    assert len(possible) == 1
    
    print("✓ Pokemon model tests passed")
    return True

if __name__ == "__main__":
    success = test_pokemon()
    exit(0 if success else 1)

