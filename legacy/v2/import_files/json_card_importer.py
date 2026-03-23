import json
import os
import sys
from typing import Dict, List

# Add the v2 directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from cards.pokemon import Pokemon
from cards.supporter import Supporter
from cards.tool import Tool
from cards.item import Item
# Use a more explicit import to avoid conflicts
from cards.attack import Attack as CardAttack
from cards.ability import Ability
from game.ids.action_id_generation import ActionIdGenerator


class JsonCardImporter:
    def __init__(self):
        # Storage for all created objects

        self.abilities = {}
        self.attacks = {}

        # Card types
        self.items = {}
        self.pokemon = {}
        self.supporters = {}
        self.tools = {}
        
        # Counters for how many of each object we've created
        self.attack_counter = 0
        self.ability_counter = 0
        
        # Energy type mapping from JSON to internal format
        self.energy_mapping = {
            'Grass': 'grass',
            'Fire': 'fire', 
            'Water': 'water',
            'Lightning': 'electric',
            'Electric': 'electric',
            'Psychic': 'psychic',
            'Fighting': 'rock',
            'Darkness': 'dark',
            'Metal': 'metal',
            'Dragon': 'dragon',
            'Colorless': 'normal'
        }

    def import_from_json(self, folder_path=None):
        """Import cards from all JSON files in a folder"""
        if not folder_path:
            folder_path = "/Users/stewartthompson/Documents/repos/PokemonTCGP-BattleSimulator/v2/assets/cards"

        print(f"Loading cards from {folder_path}...")
        
        cards_data = []
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        
        for json_file in json_files:
            file_path = os.path.join(folder_path, json_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_cards = json.load(file)
                    cards_data.extend(file_cards)
                    print(f"✓ Loaded {len(file_cards)} cards from {json_file}")
            except Exception as e:
                print(f"❌ Error with {json_file}: {e}")
                continue
                
        print(f"Found {len(cards_data)} total cards to process...")
        
        # Process each card
        for card_data in cards_data:
            try:
                card_type = card_data.get('type', '').lower()
                card_subtype = card_data.get('subtype', '').lower()
                
                # Handle Pokemon cards
                if card_type == 'pokemon':
                    pokemon = self.create_pokemon(card_data)
                    self.pokemon[pokemon.id] = pokemon
                    
                # Handle Trainer cards
                elif card_type == 'trainer':
                    # Handle regular items
                    if card_subtype == 'item':
                        item = self.create_item(card_data)
                        self.items[item.id] = item
                        
                    # Handle supporters
                    elif card_subtype == 'supporter':
                        supporter = self.create_supporter(card_data)
                        self.supporters[supporter.id] = supporter
                        
                    # Handle tools
                    elif card_subtype == 'tool':
                        tool = self.create_tool(card_data)
                        self.tools[tool.id] = tool

            except Exception as e:
                print(f"⚠️ Error processing card {card_data.get('name', 'Unknown')}: {e}")
                continue
        
        # Set evolution relationships after processing all cards
        self._set_evolution_relationships()
        
        print(f"Import complete!")
        print(f"Created {len(self.pokemon)} Pokemon")
        print(f"Created {self.attack_counter} unique attacks")
        print(f"Created {self.ability_counter} unique abilities")
        print(f"Created {len(self.supporters)} supporters")
        print(f"Created {len(self.tools)} tools")
        print(f"Created {len(self.items)} items")


    def parse_energy_cost(self, cost_list: List[str]) -> Dict[str, int]:
        """Convert JSON energy cost array to internal energy cost dict"""
        # Initialize all energy types to 0
        energy_cost = dict.fromkeys(['fire', 'water', 'rock', 'grass', 'normal', 
                                   'electric', 'psychic', 'dark', 'metal', 'dragon'], 0)
        
        # Count each energy type
        for energy in cost_list:
            energy_type = self.energy_mapping.get(energy)
            if not energy_type:
                raise ValueError(f"Unknown energy type: {energy}")
            energy_cost[energy_type] += 1
            
        return energy_cost

    def create_attack(self, attack_data: dict, card_data: dict) -> CardAttack:
        """Create an Attack object"""
        attack_id = ActionIdGenerator.get_attack_id(card_data, attack_data)

        self.attack_counter += 1
        return CardAttack(
            id=attack_id,
            name=attack_data.get('name', ''),
            effect=attack_data.get('effect', ''),
            damage=attack_data.get('damage', '0'),
            cost=self.parse_energy_cost(attack_data.get('cost', []))
        )

    def create_ability(self, ability_data: dict, card_data: dict) -> Ability:
        """Create an Ability object"""
        ability_id = ActionIdGenerator.get_ability_id(card_data, ability_data)
        self.ability_counter += 1
        return Ability(
            id=ability_id,
            name=ability_data.get('name', ''),
            effect=ability_data.get('effect', '')
        )

    def create_pokemon(self, card_data: dict) -> Pokemon:
        """Create a Pokemon object from JSON card data"""
        # Handle attacks
        attacks = []
        for attack_data in card_data.get('attacks', []):
            attack = self.create_attack(attack_data, card_data)
            attacks.append(attack)
        
        # Handle abilities
        abilities = []
        abilities_list = card_data.get('abilities', [])
        for ability_data in abilities_list:
            ability = self.create_ability(ability_data, card_data)
            abilities.append(ability)

        
        # Get pokemon type and weakness
        element = card_data.get('element')
        weakness_type = card_data.get('weakness')

        if element not in self.energy_mapping and card_data.get('subtype') != 'Fossil':
            raise ValueError(f"Unknown element type: {element}")
        
        pokemon_type = self.energy_mapping.get(element) if element else None
        weakness = self.energy_mapping.get(weakness_type) if weakness_type else None

        subtype = card_data.get('subtype')
        if subtype not in ['Basic', 'Stage 1', 'Stage 2', 'Fossil']:
            raise ValueError(f"Unknown stage type: {subtype}")
        stage = subtype.lower().replace(' ', '')

        action_ids = []
        for action_id in ActionIdGenerator.get_all_action_ids_for_card(card_data):
            action_ids.append(action_id)
        
        pokemon = Pokemon(
            id=card_data.get('id'),
            name=card_data.get('name'),
            element=element,
            type=pokemon_type,
            subtype=subtype,
            stage=stage,
            health=card_data.get('health'),
            set=card_data.get('set'),
            pack=card_data.get('pack'),
            attacks=attacks,
            retreat_cost=card_data.get('retreatCost'),
            weakness=weakness,
            abilities=abilities,
            evolves_from=card_data.get('evolvesFrom'),
            rarity=card_data.get('rarity'),
            action_ids=action_ids
        )
        
        return pokemon

    def create_supporter(self, card_data: dict) -> Supporter:
        """Create a Supporter object from JSON card data"""
        abilities = card_data.get('abilities', [])
        
        # Handle abilities
        abilities = []
        abilities_list = card_data.get('abilities', [])
        for ability_data in abilities_list:
            ability = self.create_ability(ability_data, card_data)
            abilities.append(ability)

        action_ids = []
        for action_id in ActionIdGenerator.get_all_action_ids_for_card(card_data):
            action_ids.append(action_id)
        
        item = Supporter(
            id=card_data.get('id'),
            name=card_data.get('name'),
            type=card_data.get('type'),
            subtype=card_data.get('subtype'),
            set=card_data.get('set'),
            pack=card_data.get('pack'),
            rarity=card_data.get('rarity'),
            abilities=abilities,
            action_ids=action_ids
        )
        
        return item

    def create_tool(self, card_data: dict) -> Tool:
        """Create an Tool object from JSON card data"""
        abilities = card_data.get('abilities', [])
        
        # Handle abilities
        abilities = []
        abilities_list = card_data.get('abilities', [])
        for ability_data in abilities_list:
            ability = self.create_ability(ability_data, card_data)
            abilities.append(ability)
        
        action_ids = []
        for action_id in ActionIdGenerator.get_all_action_ids_for_card(card_data):
            action_ids.append(action_id)
        
        item = Tool(
            id=card_data.get('id'),
            name=card_data.get('name'),
            type=card_data.get('type'),
            subtype=card_data.get('subtype'),
            set=card_data.get('set'),
            pack=card_data.get('pack'),
            rarity=card_data.get('rarity'),
            abilities=abilities,
            action_ids=action_ids
        )
        
        return item

    def create_item(self, card_data: dict) -> Item:
        """Create an Item object from JSON card data"""
        abilities = card_data.get('abilities', [])
        
        # Handle abilities
        abilities = []
        abilities_list = card_data.get('abilities', [])
        for ability_data in abilities_list:
            ability = self.create_ability(ability_data, card_data)
            abilities.append(ability)

        action_ids = []
        for action_id in ActionIdGenerator.get_all_action_ids_for_card(card_data):
            action_ids.append(action_id)
        
        item = Item(
            id=card_data.get('id'),
            name=card_data.get('name'),
            type=card_data.get('type'),
            subtype=card_data.get('subtype'),
            set=card_data.get('set'),
            pack=card_data.get('pack'),
            rarity=card_data.get('rarity'),
            abilities=abilities,
            action_ids=action_ids
        )
        
        return item

    def initialize_from_folder(self, folder_path: str) -> Dict:
        """Initialize card database from a folder of JSON files"""
        print(f"Initializing cards from {folder_path}...")
        
        try:
            json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
            successful_imports = sum(1 for f in json_files 
                if os.path.getsize(os.path.join(folder_path, f)) > 0 
                and self._try_import_file(os.path.join(folder_path, f)))
            
            print(f"✅ Successfully imported {successful_imports} out of {len(json_files)} JSON files")
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")

    def _set_evolution_relationships(self):
        """Set evolution relationships between Pokemon cards."""
        
        # Create a combined lookup of all cards that can be part of evolution chains
        all_cards = {}
        for pokemon in self.pokemon.values():
            all_cards[pokemon.name] = pokemon
        
        evolution_count = 0
        
        # Go through each Pokemon and set evolution relationships
        for pokemon in self.pokemon.values():
            if hasattr(pokemon, 'evolves_from') and pokemon.evolves_from:
                # Find the pre-evolution card
                pre_evolution = all_cards.get(pokemon.evolves_from)
                if pre_evolution:
                    # Set bidirectional evolution relationship
                    pokemon.add_evolves_from_id(pre_evolution.id)
                    pre_evolution.add_evolves_to_id(pokemon.id)
                    evolution_count += 1
        
        print(f"Set {evolution_count} evolution relationships")


# Example usage
if __name__ == "__main__":
    # Create importer and import cards
    importer = JsonCardImporter()
    importer.import_from_json()