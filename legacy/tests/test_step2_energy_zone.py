# Create test file: tests/test_step2_energy_zone.py
import sys
sys.path.insert(0, '.')

from v3.models.match.energy_zone import EnergyZone
from v3.models.cards.energy import Energy

def test_energy_zone():
    """Test EnergyZone class"""
    # Test initialization
    zone = EnergyZone([Energy.Type.GRASS, Energy.Type.FIRE])
    assert zone.current is None
    assert zone.next is None
    
    # Test generation
    zone.generate_energy()
    assert zone.current is not None
    assert zone.next is not None
    assert zone.current in [Energy.Type.GRASS, Energy.Type.FIRE]
    assert zone.next in [Energy.Type.GRASS, Energy.Type.FIRE]
    
    # Test consumption
    current_before = zone.current
    next_before = zone.next
    consumed = zone.consume_current()
    assert consumed == current_before
    assert zone.current == next_before
    assert zone.next is not None  # Should regenerate
    
    # Test properties
    assert zone.current_energy == zone.current
    assert zone.next_energy == zone.next
    
    print("✓ EnergyZone tests passed")
    return True

if __name__ == "__main__":
    success = test_energy_zone()
    exit(0 if success else 1)

