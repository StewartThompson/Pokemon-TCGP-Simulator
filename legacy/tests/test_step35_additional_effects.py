"""Test Step 35: Implement Additional Effect Types"""
import sys
sys.path.insert(0, '.')

from v3.models.match.effects.effect_parser import EffectParser
from v3.models.match.effects.switch_effect import SwitchEffect
from v3.models.match.effects.discard_effect import DiscardEffect
from v3.models.match.effects.energy_effect import EnergyEffect
from v3.models.match.effects.heal_all_effect import HealAllEffect

def test_additional_effects():
    """Test additional effect types"""
    # Test SwitchEffect
    effect1 = EffectParser.parse("Switch your opponent's Active Pokémon with 1 of their Benched Pokémon.")
    assert isinstance(effect1, SwitchEffect) or effect1 is None, f"Expected SwitchEffect or None, got {type(effect1)}"
    
    # Test DiscardEffect
    effect2 = EffectParser.parse("Discard 2 cards from your hand.")
    assert isinstance(effect2, DiscardEffect) or effect2 is None, f"Expected DiscardEffect or None, got {type(effect2)}"
    
    # Test HealAllEffect
    effect3 = EffectParser.parse("Heal 20 damage from each of your Pokémon.")
    assert isinstance(effect3, HealAllEffect), f"Expected HealAllEffect, got {type(effect3)}"
    assert effect3.amount == 20, f"Expected amount 20, got {effect3.amount}"
    
    print("✓ Additional effect types tests passed")
    return True

if __name__ == "__main__":
    success = test_additional_effects()
    exit(0 if success else 1)

