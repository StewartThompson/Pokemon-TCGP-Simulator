"""Test Step 36: Complete Ability Effect Parsing"""
import sys
sys.path.insert(0, '.')

from v3.models.match.effects.effect_parser import EffectParser
from v3.models.match.effects.heal_all_effect import HealAllEffect

def test_ability_effect_parsing():
    """Test ability effect parsing"""
    # Test Powder Heal ability
    powder_heal_text = "Once during your turn, you may heal 20 damage from each of your Pokémon."
    effect = EffectParser.parse_ability_effect(powder_heal_text)
    # Should parse as HealAllEffect
    assert isinstance(effect, HealAllEffect), f"Expected HealAllEffect, got {type(effect)}"
    assert effect.amount == 20, f"Expected amount 20, got {effect.amount}"
    
    print("✓ Ability effect parsing tests passed")
    return True

if __name__ == "__main__":
    success = test_ability_effect_parsing()
    exit(0 if success else 1)

