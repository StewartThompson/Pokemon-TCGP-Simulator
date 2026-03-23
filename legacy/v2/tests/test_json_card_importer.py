#!/usr/bin/env python3
"""
Comprehensive test suite for JsonCardImporter

This test script validates:
- JSON file loading and parsing
- Card creation for all types (Pokemon, Items, Supporters, Tools, Fossils)
- Energy cost parsing and validation
- Evolution relationship setting
- Error handling and edge cases
- Data integrity and statistics
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, mock_open

# Add the v2 directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from import_files.json_card_importer import JsonCardImporter
from cards.pokemon import Pokemon
from cards.fossil import Fossil
from cards.supporter import Supporter
from cards.tool import Tool
from cards.item import Item
from cards.attack import Attack
from cards.ability import Ability

class TestJsonCardImporter(unittest.TestCase):
    """Main test class for JsonCardImporter functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.importer = JsonCardImporter()
        self.test_dir = None
        self.sample_cards = self.load_sample_cards()
    
    def tearDown(self):
        """Clean up after each test method"""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def load_sample_cards(self):
        """Load sample cards from the test data file"""
        sample_file = os.path.join(os.path.dirname(__file__), 'test_data', 'sample_cards.json')
        with open(sample_file, 'r') as f:
            cards = json.load(f)
        return {card['id']: card for card in cards}
    
    def get_card_by_id(self, card_id):
        """Get a specific card by ID from sample data"""
        if card_id not in self.sample_cards:
            raise ValueError(f"Card ID {card_id} not found in sample data")
        return self.sample_cards[card_id]
    
    def get_pokemon_cards(self):
        """Get all Pokemon cards from sample data"""
        return [card for card in self.sample_cards.values() if card.get('type') == 'Pokemon']
    
    def get_trainer_cards(self):
        """Get all Trainer cards from sample data"""
        return [card for card in self.sample_cards.values() if card.get('type') == 'Trainer']
    
    def create_temp_json_files(self, cards_data_dict):
        """Create temporary JSON files for testing"""
        self.test_dir = tempfile.mkdtemp()
        
        for filename, cards_data in cards_data_dict.items():
            file_path = os.path.join(self.test_dir, filename)
            with open(file_path, 'w') as f:
                json.dump(cards_data, f)
        
        return self.test_dir

class TestCardCreation(TestJsonCardImporter):
    """Test card creation functionality"""
    
    def test_create_pokemon_basic(self):
        """Test creating a basic Pokemon card"""
        pokemon_data = self.get_card_by_id("a1-094")  # Pikachu
        pokemon = self.importer.create_pokemon(pokemon_data)
        
        # Verify basic attributes
        self.assertEqual(pokemon.id, "a1-094")
        self.assertEqual(pokemon.name, "Pikachu")
        self.assertEqual(pokemon.type, "electric")  # Mapped from Lightning
        self.assertEqual(pokemon.stage, "basic")
        self.assertEqual(pokemon.max_hp, 60)
        self.assertEqual(pokemon.retreat_cost, 1)
        self.assertEqual(pokemon.weakness, "rock")  # Mapped from Fighting
        
        # Verify attacks
        self.assertEqual(len(pokemon.attacks), 1)
        self.assertEqual(pokemon.attacks[0].name, "Gnaw")
        self.assertEqual(pokemon.attacks[0].damage, "20")
        
        # Verify abilities (empty in this case)
        self.assertEqual(len(pokemon.abilities), 0)
    
    def test_create_supporter(self):
        """Test creating a supporter card"""
        supporter_data = self.get_card_by_id("pa-007")  # Professor's Research
        supporter = self.importer.create_supporter(supporter_data)
        
        self.assertEqual(supporter.id, "pa-007")
        self.assertEqual(supporter.name, "Professor's Research")
        self.assertEqual(supporter.type, "Trainer")
        self.assertEqual(supporter.subtype, "Supporter")
        self.assertEqual(supporter.ability.name, "Draw 2 cards")
    
    def test_create_item(self):
        """Test creating an item card"""
        item_data = self.get_card_by_id("pa-001")  # Potion
        item = self.importer.create_item(item_data)
        
        self.assertEqual(item.id, "pa-001")
        self.assertEqual(item.name, "Potion")
        self.assertEqual(item.type, "Trainer")
        self.assertEqual(item.subtype, "Item")
        self.assertEqual(item.ability.effect, "Heal 20 damage from 1 of your Pokémon.")
    
    def test_create_tool(self):
        """Test creating a tool card"""
        tool_data = self.get_card_by_id("a2-147")  # Giant Cape
        tool = self.importer.create_tool(tool_data)
        
        self.assertEqual(tool.id, "a2-147")
        self.assertEqual(tool.name, "Giant Cape")
        self.assertEqual(tool.type, "Trainer")
        self.assertEqual(tool.subtype, "Tool")
        # This tool has no abilities in the sample data
        self.assertFalse(hasattr(tool, 'ability') and tool.ability)
    
    def test_create_fossil(self):
        """Test creating a fossil card"""
        fossil_data = self.get_card_by_id("a1-216")  # Helix Fossil
        fossil = self.importer.create_fossil(fossil_data)
        
        self.assertEqual(fossil.id, "a1-216")
        self.assertEqual(fossil.name, "Helix Fossil")
        self.assertEqual(fossil.max_hp, 40)  # Default fossil HP
        self.assertEqual(len(fossil.abilities), 1)
        self.assertEqual(fossil.abilities[0].name, "Fossil Ability")

class TestEnergyParsing(TestJsonCardImporter):
    """Test energy cost parsing functionality"""
    
    def test_parse_single_energy_cost(self):
        """Test parsing single energy cost"""
        cost = self.importer.parse_energy_cost(["Fire"])
        expected = dict.fromkeys(['fire', 'water', 'rock', 'grass', 'normal', 
                                'electric', 'psychic', 'dark', 'metal', 'dragon'], 0)
        expected['fire'] = 1
        self.assertEqual(cost, expected)
    
    def test_parse_multiple_energy_cost(self):
        """Test parsing multiple energy costs"""
        cost = self.importer.parse_energy_cost(["Lightning", "Lightning", "Colorless"])
        expected = dict.fromkeys(['fire', 'water', 'rock', 'grass', 'normal', 
                                'electric', 'psychic', 'dark', 'metal', 'dragon'], 0)
        expected['electric'] = 2
        expected['normal'] = 1
        self.assertEqual(cost, expected)
    
    def test_parse_unknown_energy_type(self):
        """Test parsing unknown energy type raises error"""
        with self.assertRaises(ValueError):
            self.importer.parse_energy_cost(["UnknownEnergy"])
    
    def test_energy_mapping(self):
        """Test energy type mapping correctness"""
        test_cases = [
            ("Grass", "grass"),
            ("Fire", "fire"),
            ("Water", "water"),
            ("Lightning", "electric"),
            ("Electric", "electric"),
            ("Psychic", "psychic"),
            ("Fighting", "rock"),
            ("Darkness", "dark"),
            ("Metal", "metal"),
            ("Dragon", "dragon"),
            ("Colorless", "normal")
        ]
        
        for json_type, internal_type in test_cases:
            self.assertEqual(self.importer.energy_mapping[json_type], internal_type)

class TestEvolutionRelationships(TestJsonCardImporter):
    """Test evolution relationship functionality"""
    
    def test_set_evolution_relationships(self):
        """Test setting evolution relationships between Pokemon"""
        # Get evolution chain: Charmander -> Charmeleon -> Charizard
        charmander_data = self.get_card_by_id("a1-033")
        charmeleon_data = self.get_card_by_id("a1-034") 
        charizard_data = self.get_card_by_id("a1-035")
        
        # Create Pokemon objects
        charmander = self.importer.create_pokemon(charmander_data)
        charmeleon = self.importer.create_pokemon(charmeleon_data)
        charizard = self.importer.create_pokemon(charizard_data)
        
        # Add to importer
        self.importer.pokemon[charmander.id] = charmander
        self.importer.pokemon[charmeleon.id] = charmeleon
        self.importer.pokemon[charizard.id] = charizard
        
        # Set evolution relationships
        self.importer._set_evolution_relationships()
        
        # Verify relationships were set correctly
        # Charmeleon evolves from Charmander
        self.assertIn(charmander.id, charmeleon.evolves_from_ids)
        self.assertIn(charmeleon.id, charmander.evolves_to_ids)
        
        # Charizard evolves from Charmeleon  
        self.assertIn(charmeleon.id, charizard.evolves_from_ids)
        self.assertIn(charizard.id, charmeleon.evolves_to_ids)

class TestFileImport(TestJsonCardImporter):
    """Test file import functionality"""
    
    def test_import_from_json_success(self):
        """Test successful import from JSON files"""
        # Create test data using sample cards
        pokemon_cards = self.get_pokemon_cards()[:2]  # Get first 2 Pokemon
        trainer_cards = self.get_trainer_cards()[:2]  # Get first 2 Trainers
        
        test_data = {
            "pokemon.json": pokemon_cards,
            "trainers.json": trainer_cards
        }
        
        # Create temp files
        test_dir = self.create_temp_json_files(test_data)
        
        # Import from files
        self.importer.import_from_json(test_dir)
        
        # Verify imports - should have imported the Pokemon and Trainers
        self.assertGreater(len(self.importer.pokemon), 0)
        self.assertGreater(len(self.importer.supporters) + 
                          len(self.importer.items) + 
                          len(self.importer.tools) + 
                          len(self.importer.fossils), 0)
        
        # Verify counters
        self.assertGreater(self.importer.attack_counter, 0)
        self.assertGreater(self.importer.ability_counter, 0)
    
    def test_import_invalid_json_file(self):
        """Test handling of invalid JSON files"""
        # Create directory with invalid JSON
        self.test_dir = tempfile.mkdtemp()
        invalid_file = os.path.join(self.test_dir, "invalid.json")
        
        with open(invalid_file, 'w') as f:
            f.write("{ invalid json content")
        
        # Should not crash on invalid JSON
        try:
            self.importer.import_from_json(self.test_dir)
        except Exception as e:
            self.fail(f"Import should handle invalid JSON gracefully, but raised: {e}")
    
    def test_import_empty_directory(self):
        """Test import from empty directory"""
        self.test_dir = tempfile.mkdtemp()
        
        # Should complete without errors
        self.importer.import_from_json(self.test_dir)
        
        # Should have no cards imported
        self.assertEqual(len(self.importer.pokemon), 0)
        self.assertEqual(len(self.importer.supporters), 0)

class TestErrorHandling(TestJsonCardImporter):
    """Test error handling and edge cases"""
    
    def test_create_pokemon_missing_required_fields(self):
        """Test creating Pokemon with missing required fields"""
        incomplete_data = {"name": "Incomplete Pokemon"}
        
        with self.assertRaises(Exception):
            self.importer.create_pokemon(incomplete_data)
    
    def test_create_pokemon_invalid_element(self):
        """Test creating Pokemon with invalid element"""
        # Start with valid Pokemon data and make it invalid
        invalid_data = self.get_card_by_id("a1-094").copy()  # Pikachu
        invalid_data["element"] = "InvalidElement"
        
        with self.assertRaises(ValueError):
            self.importer.create_pokemon(invalid_data)
    
    def test_create_pokemon_invalid_stage(self):
        """Test creating Pokemon with invalid stage"""
        # Start with valid Pokemon data and make it invalid
        invalid_data = self.get_card_by_id("a1-094").copy()  # Pikachu
        invalid_data["subtype"] = "InvalidStage"
        
        with self.assertRaises(ValueError):
            self.importer.create_pokemon(invalid_data)

class TestDataValidation(TestJsonCardImporter):
    """Test data validation and integrity"""
    
    def test_attack_creation_with_all_fields(self):
        """Test attack creation with all fields present"""
        attack_data = {
            "name": "Test Attack",
            "damage": "50",
            "cost": ["Fire", "Colorless"],
            "effect": "Test effect",
            "handler": "test_handler"
        }
        
        attack = self.importer.create_attack(attack_data)
        
        self.assertEqual(attack.name, "Test Attack")
        self.assertEqual(attack.damage, "50")
        self.assertEqual(attack.effect, "Test effect")
        self.assertEqual(attack.handler, "test_handler")
        
        # Check energy cost
        self.assertEqual(attack.cost['fire'], 1)
        self.assertEqual(attack.cost['normal'], 1)
    
    def test_ability_creation_with_all_fields(self):
        """Test ability creation with all fields present"""
        ability_data = {
            "name": "Test Ability",
            "effect": "Test ability effect",
            "handler": "test_ability_handler"
        }
        
        ability = self.importer.create_ability(ability_data)
        
        self.assertEqual(ability.name, "Test Ability")
        self.assertEqual(ability.effect, "Test ability effect")
        self.assertEqual(ability.handler, "test_ability_handler")
    
    def test_counters_increment_correctly(self):
        """Test that attack and ability counters increment"""
        initial_attack_count = self.importer.attack_counter
        initial_ability_count = self.importer.ability_counter
        
        # Create attack and ability
        attack_data = {"name": "Test", "damage": "10", "cost": []}
        ability_data = {"name": "Test", "effect": "Test"}
        
        self.importer.create_attack(attack_data)
        self.importer.create_ability(ability_data)
        
        self.assertEqual(self.importer.attack_counter, initial_attack_count + 1)
        self.assertEqual(self.importer.ability_counter, initial_ability_count + 1)


def run_comprehensive_test():
    """Run all tests and provide detailed report"""
    print("=" * 60)
    print("POKEMON TCG JSON CARD IMPORTER - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestCardCreation,
        TestEnergyParsing, 
        TestEvolutionRelationships,
        TestFileImport,
        TestErrorHandling,
        TestDataValidation
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    return result.wasSuccessful()

def run_integration_test():
    """Run integration test with real files (if available)"""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST - TESTING WITH REAL JSON FILES")
    print("=" * 60)
    
    assets_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'cards')
    
    if not os.path.exists(assets_path):
        print(f"❌ Assets folder not found at {assets_path}")
        print("Skipping integration test.")
        return False
    
    json_files = [f for f in os.listdir(assets_path) if f.endswith('.json')]
    if not json_files:
        print(f"❌ No JSON files found in {assets_path}")
        print("Skipping integration test.")
        return False
    
    print(f"Found {len(json_files)} JSON files in assets folder")
    
    try:
        # Create fresh importer
        importer = JsonCardImporter()
        
        # Import all cards
        print("Importing cards...")
        importer.import_from_json(assets_path)
        
        return True
        
    except Exception as e:
        print(f"❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    """Main test execution"""
    print("Starting JSON Card Importer Test Suite...")
    
    # Run comprehensive unit tests
    unit_test_success = run_comprehensive_test()
    
    # Run integration test
    integration_test_success = run_integration_test()
    
    # Final report
    print("\n" + "=" * 60)
    print("FINAL TEST REPORT")
    print("=" * 60)
    print(f"Unit Tests: {'✅ PASSED' if unit_test_success else '❌ FAILED'}")
    print(f"Integration Test: {'✅ PASSED' if integration_test_success else '❌ FAILED'}")
    
    overall_success = unit_test_success and integration_test_success
    print(f"Overall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    # Exit with appropriate code
    exit_code = 0 if overall_success else 1
    sys.exit(exit_code)
