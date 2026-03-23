"""Test Step 33: Implement Status Effects System"""
import sys
sys.path.insert(0, '.')

from v3.models.match.status_effects.asleep import Asleep
from v3.models.match.status_effects.poisoned import Poisoned
from v3.models.match.status_effects.burned import Burned
from v3.models.match.status_effects.paralyzed import Paralyzed
from v3.models.match.status_effects.confused import Confused
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player

class MockBattleEngine:
    """Mock battle engine for testing"""
    def __init__(self):
        self.logs = []
    
    def log(self, message):
        self.logs.append(message)
    
    def _handle_knockout(self, pokemon, player):
        pass
    
    def _get_player_with_pokemon(self, pokemon):
        return None

def test_status_effects():
    """Test status effects system"""
    # Create test Pokemon
    pokemon = Pokemon("test-001", "Test", Energy.Type.GRASS, Card.Type.POKEMON,
                     Card.Subtype.BASIC, 100, "Set", "Pack", "Common", [], 1, None, None)
    
    engine = MockBattleEngine()
    
    # Test Asleep
    asleep = Asleep()
    assert not pokemon.has_status_effect(Asleep), "Pokemon should not have Asleep initially"
    asleep.apply(pokemon, engine)
    assert pokemon.has_status_effect(Asleep), "Pokemon should have Asleep after applying"
    assert not pokemon.can_attack(), "Pokemon should not be able to attack when Asleep"
    
    # Test Poisoned
    poisoned = Poisoned()
    initial_damage = pokemon.damage_taken
    poisoned.apply(pokemon, engine)
    assert pokemon.has_status_effect(Poisoned), "Pokemon should have Poisoned"
    poisoned.apply_damage(pokemon, engine)
    assert pokemon.damage_taken > initial_damage, "Poison should deal damage"
    
    # Test Paralyzed
    paralyzed = Paralyzed()
    paralyzed.apply(pokemon, engine)
    assert pokemon.has_status_effect(Paralyzed), "Pokemon should have Paralyzed"
    assert not pokemon.can_attack(), "Pokemon should not be able to attack when Paralyzed"
    assert not pokemon.can_retreat(), "Pokemon should not be able to retreat when Paralyzed"
    
    # Test Burned
    burned = Burned()
    burned.apply(pokemon, engine)
    assert pokemon.has_status_effect(Burned), "Pokemon should have Burned"
    
    # Test Confused
    confused = Confused()
    confused.apply(pokemon, engine)
    assert pokemon.has_status_effect(Confused), "Pokemon should have Confused"
    
    # Test removal
    paralyzed.remove(pokemon)
    assert not pokemon.has_status_effect(Paralyzed), "Paralyzed should be removed"
    
    print("✓ Status effects tests passed")
    return True

if __name__ == "__main__":
    success = test_status_effects()
    exit(0 if success else 1)

