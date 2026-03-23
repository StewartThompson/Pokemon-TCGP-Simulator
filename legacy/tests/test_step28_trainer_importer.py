"""Test Step 28: Complete JSON Importer for Trainer Cards"""
import sys
sys.path.insert(0, '.')

from v3.importers.json_card_importer import JsonCardImporter

def test_trainer_importer():
    """Test trainer card creation from JSON"""
    importer = JsonCardImporter()
    
    # Test Item creation
    item_data = {
        'id': 'item-001',
        'name': 'Potion',
        'type': 'Trainer',
        'subtype': 'Item',
        'effect': 'Heal 30 damage from 1 of your Pokémon.',
        'set': 'Test Set',
        'pack': 'Test Pack',
        'rarity': 'Common'
    }
    
    item = importer.create_item(item_data)
    assert item.name == 'Potion', f"Expected 'Potion', got {item.name}"
    assert item.subtype == 'Item', f"Expected 'Item', got {item.subtype}"
    assert item.ability is not None, "Item should have ability for effect"
    assert 'Heal 30' in item.ability.effect, f"Effect should contain 'Heal 30', got {item.ability.effect}"
    
    # Test Supporter creation
    supporter_data = {
        'id': 'supporter-001',
        'name': "Professor's Research",
        'type': 'Trainer',
        'subtype': 'Supporter',
        'effect': 'Discard your hand, then draw 7 cards.',
        'set': 'Test Set',
        'pack': 'Test Pack',
        'rarity': 'Uncommon'
    }
    
    supporter = importer.create_supporter(supporter_data)
    assert supporter.name == "Professor's Research", f"Expected 'Professor's Research', got {supporter.name}"
    assert supporter.subtype == 'Supporter', f"Expected 'Supporter', got {supporter.subtype}"
    assert supporter.ability is not None, "Supporter should have ability for effect"
    
    # Test Tool creation
    tool_data = {
        'id': 'tool-001',
        'name': 'Cape',
        'type': 'Trainer',
        'subtype': 'Tool',
        'effect': 'The Pokémon this card is attached to takes 20 less damage from attacks.',
        'set': 'Test Set',
        'pack': 'Test Pack',
        'rarity': 'Uncommon'
    }
    
    tool = importer.create_tool(tool_data)
    assert tool.name == 'Cape', f"Expected 'Cape', got {tool.name}"
    assert tool.subtype == 'Tool', f"Expected 'Tool', got {tool.subtype}"
    assert tool.ability is not None, "Tool should have ability for effect"
    
    print("✓ Trainer card importer tests passed")
    return True

if __name__ == "__main__":
    success = test_trainer_importer()
    exit(0 if success else 1)

