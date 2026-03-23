"""Test Step 23: Create Effect Parser System"""
import sys
sys.path.insert(0, '.')

from v3.models.match.effects.effect_parser import EffectParser
from v3.models.match.effects.heal_effect import HealEffect
from v3.models.match.effects.search_effect import SearchEffect

def test_effect_parser():
    """Test effect parser"""
    # Test heal effect
    effect1 = EffectParser.parse("Heal 30 damage from this Pokémon.")
    assert isinstance(effect1, HealEffect), f"Expected HealEffect, got {type(effect1)}"
    assert effect1.amount == 30, f"Expected amount 30, got {effect1.amount}"
    assert effect1.target == "this", f"Expected target 'this', got {effect1.target}"
    
    # Test search effect
    effect2 = EffectParser.parse("Put 1 random Grass Pokémon from your deck into your hand.")
    assert isinstance(effect2, SearchEffect), f"Expected SearchEffect, got {type(effect2)}"
    assert effect2.amount == 1, f"Expected amount 1, got {effect2.amount}"
    assert effect2.card_type == "Pokemon", f"Expected card_type 'Pokemon', got {effect2.card_type}"
    from v3.models.cards.energy import Energy
    assert effect2.element == Energy.Type.GRASS, f"Expected element GRASS, got {effect2.element}"
    
    # Test unknown effect
    effect3 = EffectParser.parse("Unknown effect text")
    assert effect3 is None, "Unknown effect should return None"
    
    # Test parse_multiple
    effects = EffectParser.parse_multiple("Heal 30 damage from this Pokémon. Draw 2 cards.")
    assert len(effects) >= 1, "Should parse at least one effect"
    
    print("✓ Effect parser tests passed")
    return True

if __name__ == "__main__":
    success = test_effect_parser()
    exit(0 if success else 1)

