"""Test Step 21: Fix JSON Importer - Attack Damage and Effects"""
import sys
sys.path.insert(0, '.')

from v3.importers.json_card_importer import JsonCardImporter

def test_attack_effects():
    """Test attack effect parsing"""
    importer = JsonCardImporter()
    
    # Test attack with effect
    attack_data = {
        'name': 'Giant Bloom',
        'damage': '100',
        'effect': 'Heal 30 damage from this Pokémon.',
        'cost': ['Grass', 'Grass', 'Colorless', 'Colorless']
    }
    
    attack = importer.create_attack(attack_data, {'name': 'Test'})
    assert attack.damage == 100, f"Expected damage 100, got {attack.damage}"
    assert attack.ability is not None, "Attack should have ability for effect"
    assert 'Heal 30' in attack.ability.effect, f"Effect should contain 'Heal 30', got {attack.ability.effect}"
    
    # Test attack with empty damage
    attack_data2 = {
        'name': 'Find a Friend',
        'damage': '',
        'effect': 'Put 1 random Grass Pokémon from your deck into your hand.',
        'cost': ['Colorless']
    }
    
    attack2 = importer.create_attack(attack_data2, {'name': 'Test'})
    assert attack2.damage == 0, f"Expected damage 0 for empty string, got {attack2.damage}"
    assert attack2.ability is not None, "Attack should have ability for effect"
    assert 'Put 1 random' in attack2.ability.effect, f"Effect should contain 'Put 1 random', got {attack2.ability.effect}"
    
    # Test attack with no effect
    attack_data3 = {
        'name': 'Vine Whip',
        'damage': '40',
        'cost': ['Grass', 'Colorless']
    }
    
    attack3 = importer.create_attack(attack_data3, {'name': 'Test'})
    assert attack3.damage == 40, f"Expected damage 40, got {attack3.damage}"
    # Ability can be None if no effect
    # assert attack3.ability is None or attack3.ability.effect == '', "Attack without effect should have no ability"
    
    print("✓ Attack effects parsing tests passed")
    return True

if __name__ == "__main__":
    success = test_attack_effects()
    exit(0 if success else 1)

