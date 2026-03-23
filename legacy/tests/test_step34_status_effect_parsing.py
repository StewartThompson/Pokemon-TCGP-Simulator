"""Test Step 34: Implement Status Effect Application in Attacks"""
import sys
sys.path.insert(0, '.')

from v3.models.match.effects.effect_parser import EffectParser
from v3.models.match.effects.status_effect_effect import StatusEffectEffect

def test_status_effect_parsing():
    """Test status effect parsing from text"""
    # Test Asleep
    effect1 = EffectParser.parse("Your opponent's Active Pokémon is now Asleep.")
    assert isinstance(effect1, StatusEffectEffect), f"Expected StatusEffectEffect, got {type(effect1)}"
    assert effect1.status_type == "asleep", f"Expected 'asleep', got {effect1.status_type}"
    
    # Test Poisoned
    effect2 = EffectParser.parse("Your opponent's Active Pokémon is now Poisoned.")
    assert isinstance(effect2, StatusEffectEffect), f"Expected StatusEffectEffect, got {type(effect2)}"
    assert effect2.status_type == "poisoned", f"Expected 'poisoned', got {effect2.status_type}"
    
    # Test Paralyzed
    effect3 = EffectParser.parse("Your opponent's Active Pokémon is now Paralyzed.")
    assert isinstance(effect3, StatusEffectEffect), f"Expected StatusEffectEffect, got {type(effect3)}"
    assert effect3.status_type == "paralyzed", f"Expected 'paralyzed', got {effect3.status_type}"
    
    print("✓ Status effect parsing tests passed")
    return True

if __name__ == "__main__":
    success = test_status_effect_parsing()
    exit(0 if success else 1)

