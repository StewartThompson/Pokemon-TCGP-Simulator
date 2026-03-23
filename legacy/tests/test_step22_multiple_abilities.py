"""Test Step 22: Fix Pokemon Model - Support Multiple Abilities"""
import sys
sys.path.insert(0, '.')

from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.cards.ability import Ability

def test_multiple_abilities():
    """Test Pokemon with multiple abilities"""
    ability1 = Ability("Powder Heal", "Heal 20 damage", Ability.Target.PLAYER_ALL, Card.Position.ACTIVE)
    ability2 = Ability("Test Ability", "Test effect", Ability.Target.OPPONENT_ACTIVE, Card.Position.ACTIVE)
    
    pokemon = Pokemon("test-001", "Butterfree", Energy.Type.GRASS, Card.Type.POKEMON,
                     Card.Subtype.STAGE_2, 120, "Set", "Pack", "Rare", [], 1, Energy.Type.FIRE, "Metapod",
                     abilities=[ability1, ability2])
    
    assert len(pokemon.abilities) == 2, f"Expected 2 abilities, got {len(pokemon.abilities)}"
    assert pokemon.ability == ability1, "First ability should be stored in self.ability for backward compatibility"
    assert ability1 in pokemon.abilities, "Ability1 should be in abilities list"
    assert ability2 in pokemon.abilities, "Ability2 should be in abilities list"
    
    usable = pokemon.get_usable_abilities()
    assert len(usable) == 2, f"Expected 2 usable abilities, got {len(usable)}"
    
    pokemon.used_ability_this_turn = True
    usable2 = pokemon.get_usable_abilities()
    assert len(usable2) == 0, f"Expected 0 usable abilities after using, got {len(usable2)}"
    
    # Test single ability (backward compatibility)
    pokemon2 = Pokemon("test-002", "Test", Energy.Type.GRASS, Card.Type.POKEMON,
                      Card.Subtype.BASIC, 100, "Set", "Pack", "Common", [], 1, None, None,
                      ability=ability1)
    assert len(pokemon2.abilities) == 1, "Single ability should create list with one ability"
    assert pokemon2.ability == ability1, "Single ability should be stored correctly"
    
    print("✓ Multiple abilities tests passed")
    return True

if __name__ == "__main__":
    success = test_multiple_abilities()
    exit(0 if success else 1)

