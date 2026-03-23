import json
import os
import sys
from typing import Dict, List
from ..models.cards.energy import Energy
from ..models.cards.attack import Attack
from ..models.cards.ability import Ability
from ..models.cards.card import Card
from ..models.cards.pokemon import Pokemon
class JsonCardImporter:
    def __init__(self):
        # Card types
        self.items = {}
        self.pokemon = {}
        self.supporters = {}
        self.tools = {}

    def import_from_json(self):
        """Import cards from all JSON files in a folder"""
        # Get the directory of this file, then go to v3/assets
        current_dir = os.path.dirname(os.path.abspath(__file__))
        folder_path = os.path.join(current_dir, '..', 'assets')
        folder_path = os.path.abspath(folder_path)

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
        # (Will be implemented when evolution system is added)
        # self._set_evolution_relationships()
        
        print(f"Import complete!")
        print(f"Created {len(self.pokemon)} Pokemon")
        print(f"Created {len(self.supporters)} supporters")
        print(f"Created {len(self.tools)} tools")
        print(f"Created {len(self.items)} items")
    
    def parse_energy_cost(self, cost_list: List[str]) -> Dict[str, int]:
        """Convert JSON energy cost array to internal energy cost dict"""
        energy = Energy.from_string_list(cost_list)
        return energy.cost

    def create_attack(self, attack_data: dict, card_data: dict) -> Attack:
        """Create an Attack object"""
        
        name = attack_data.get('name', '')
        if not name:
            raise ValueError(f"Attack name cannot be empty for card {card_data.get('name', 'Unknown')}")
       
        # Handle damage - convert string to int, handle empty string
        damage_str = attack_data.get('damage', '0')
        if damage_str == '' or damage_str is None:
            damage = 0
        else:
            try:
                damage = int(damage_str)
            except (ValueError, TypeError):
                damage = 0
        
        # Handle attack effect - create ability if effect exists
        attack_effect = attack_data.get('effect', '')
        ability = None
        
        # If attack has an explicit ability field, use that
        if attack_data.get('ability'):
            ability = self.create_ability(attack_data.get('ability', {}), card_data)
        # Otherwise, if attack has an effect field, create ability for it
        elif attack_effect:
            ability = Ability(
                name=f"{name} Effect",
                effect=attack_effect,
                target=Ability.Target.OPPONENT_ACTIVE,  # Default, may need parsing
                position=Card.Position.ACTIVE
            )
        
        # Parse energy cost
        energy_cost = self.parse_energy_cost(attack_data.get('cost', []))
        energy = Energy(energy_cost)
        
        return Attack(
            name=name,
            ability=ability,
            damage=damage,
            cost=energy
        )

    def create_ability(self, ability_data: dict, card_data: dict) -> Ability:
        """Create an Ability object"""
        # Handle empty dict
        if not ability_data:
            return None
        
        name = ability_data.get('name', '')
        if not name:
            return None  # Return None if no name
            
        effect = ability_data.get('effect', '')
        if not effect:
            return None  # Return None if no effect
            
        return Ability(
            name=name,
            effect=effect,
            target=ability_data.get('target', Ability.Target.OPPONENT_ACTIVE),
            position=ability_data.get('position', Card.Position.ACTIVE)
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
        if not element:
            raise ValueError(f"Element cannot be empty for card {card_data.get('name', 'Unknown')}")

        # Convert string element to Energy.Type enum using mapping
        energy_map = {
            'FIRE': Energy.Type.FIRE,
            'WATER': Energy.Type.WATER,
            'ROCK': Energy.Type.ROCK,
            'GRASS': Energy.Type.GRASS,
            'NORMAL': Energy.Type.NORMAL,
            'COLORLESS': Energy.Type.NORMAL,
            'ELECTRIC': Energy.Type.ELECTRIC,
            'PSYCHIC': Energy.Type.PSYCHIC,
            'DARK': Energy.Type.DARK,
            'DARKNESS': Energy.Type.DARK,
            'METAL': Energy.Type.METAL,
        }
        
        element_upper = element.upper()
        pokemon_type = energy_map.get(element_upper)
        if pokemon_type is None:
            if card_data.get('subtype') != 'Fossil':
                raise ValueError(f"Unknown element type: {element}")
            pokemon_type = None
        
        weakness_type = card_data.get('weakness')
        weakness = None
        if weakness_type:
            weakness_upper = weakness_type.upper()
            weakness = energy_map.get(weakness_upper)
            if weakness is None:
                raise ValueError(f"Unknown weakness type: {weakness_type}")

        subtype_str = card_data.get('subtype')
        if subtype_str not in ['Basic', 'Stage 1', 'Stage 2', 'Fossil']:
            raise ValueError(f"Unknown stage type: {subtype_str}")
        
        # Convert subtype string to Card.Subtype enum
        from v3.models.cards.card import Card
        subtype_map = {
            'Basic': Card.Subtype.BASIC,
            'Stage 1': Card.Subtype.STAGE_1,
            'Stage 2': Card.Subtype.STAGE_2,
            'Fossil': Card.Subtype.BASIC  # Fossils are treated as Basic
        }
        subtype = subtype_map.get(subtype_str, Card.Subtype.BASIC)
        
        # Pass abilities as list (Pokemon now supports multiple abilities)
        pokemon = Pokemon(
            id=card_data.get('id'),
            name=card_data.get('name'),
            element=pokemon_type,  # Use pokemon_type (Energy.Type enum) not element (string)
            type=Card.Type.POKEMON,
            subtype=subtype,
            health=card_data.get('health'),
            set=card_data.get('set'),
            pack=card_data.get('pack'),
            rarity=card_data.get('rarity'),
            attacks=attacks,
            retreat_cost=card_data.get('retreatCost'),
            weakness=weakness,
            evolves_from=card_data.get('evolvesFrom'),
            abilities=abilities
        )
        
        return pokemon
    
    def create_item(self, card_data: dict):
        """Create an Item card from JSON data"""
        from v3.models.cards.item import Item
        from v3.models.cards.card import Card
        
        # Handle abilities - items can have abilities with effects
        abilities_data = card_data.get('abilities', [])
        ability = None
        
        if abilities_data and len(abilities_data) > 0:
            # Use first ability (items typically have one)
            ability_data = abilities_data[0]
            ability_name = ability_data.get('name', f"{card_data.get('name', 'Item')} Effect")
            effect_text = ability_data.get('effect', '')
            if effect_text:
                ability = Ability(
                    name=ability_name,
                    effect=effect_text,
                    target=Ability.Target.PLAYER_ACTIVE,  # Default
                    position=Card.Position.ACTIVE
                )
        else:
            # Fallback: check for top-level effect (for backward compatibility)
            effect_text = card_data.get('effect', '')
            if effect_text:
                ability = Ability(
                    name=f"{card_data.get('name', 'Item')} Effect",
                    effect=effect_text,
                    target=Ability.Target.PLAYER_ACTIVE,  # Default
                    position=Card.Position.ACTIVE
                )
        
        return Item(
            id=card_data.get('id'),
            name=card_data.get('name'),
            type=Card.Type.TRAINER,
            subtype=Card.Subtype.ITEM,
            set=card_data.get('set', ''),
            pack=card_data.get('pack', ''),
            rarity=card_data.get('rarity', ''),
            image_url=card_data.get('image_url'),
            ability=ability
        )
    
    def create_supporter(self, card_data: dict):
        """Create a Supporter card from JSON data"""
        from v3.models.cards.supporter import Supporter
        from v3.models.cards.card import Card
        
        # Handle abilities - supporters can have abilities with effects
        abilities_data = card_data.get('abilities', [])
        ability = None
        
        if abilities_data and len(abilities_data) > 0:
            # Use first ability (supporters typically have one)
            ability_data = abilities_data[0]
            ability_name = ability_data.get('name', f"{card_data.get('name', 'Supporter')} Effect")
            effect_text = ability_data.get('effect', '')
            if effect_text:
                ability = Ability(
                    name=ability_name,
                    effect=effect_text,
                    target=Ability.Target.PLAYER_ACTIVE,  # Default
                    position=Card.Position.ACTIVE
                )
        else:
            # Fallback: check for top-level effect (for backward compatibility)
            effect_text = card_data.get('effect', '')
            if effect_text:
                ability = Ability(
                    name=f"{card_data.get('name', 'Supporter')} Effect",
                    effect=effect_text,
                    target=Ability.Target.PLAYER_ACTIVE,  # Default
                    position=Card.Position.ACTIVE
                )
        
        return Supporter(
            id=card_data.get('id'),
            name=card_data.get('name'),
            type=Card.Type.TRAINER,
            subtype=Card.Subtype.SUPPORTER,
            set=card_data.get('set', ''),
            pack=card_data.get('pack', ''),
            rarity=card_data.get('rarity', ''),
            image_url=card_data.get('image_url'),
            ability=ability
        )
    
    def create_tool(self, card_data: dict):
        """Create a Tool card from JSON data"""
        from v3.models.cards.tool import Tool
        from v3.models.cards.card import Card
        
        # Handle abilities - tools can have abilities with effects
        abilities_data = card_data.get('abilities', [])
        ability = None
        
        if abilities_data and len(abilities_data) > 0:
            # Use first ability (tools typically have one)
            ability_data = abilities_data[0]
            ability_name = ability_data.get('name', f"{card_data.get('name', 'Tool')} Effect")
            effect_text = ability_data.get('effect', '')
            if effect_text:
                ability = Ability(
                    name=ability_name,
                    effect=effect_text,
                    target=Ability.Target.PLAYER_ACTIVE,  # Default
                    position=Card.Position.ACTIVE
                )
        else:
            # Fallback: check for top-level effect (for backward compatibility)
            effect_text = card_data.get('effect', '')
            if effect_text:
                ability = Ability(
                    name=f"{card_data.get('name', 'Tool')} Effect",
                    effect=effect_text,
                    target=Ability.Target.PLAYER_ACTIVE,  # Default
                    position=Card.Position.ACTIVE
                )
        
        return Tool(
            id=card_data.get('id'),
            name=card_data.get('name'),
            type=Card.Type.TRAINER,
            subtype=Card.Subtype.TOOL,
            set=card_data.get('set', ''),
            pack=card_data.get('pack', ''),
            rarity=card_data.get('rarity', ''),
            image_url=card_data.get('image_url'),
            ability=ability
        )
