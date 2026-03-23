#!/usr/bin/env python3

import json
import os

def to_camel_case(text):
    """Convert text to camelCase with no spaces"""
    if not text:
        return ""
    # Split by spaces and underscores, capitalize each word except the first
    words = text.replace('_', ' ').split()
    return words[0].lower() + ''.join(word.capitalize() for word in words[1:])

def analyze_cards():
    """Extract all attacks and abilities from card data, using descriptive ID as uniqueness key"""
    
    cards_dirs = ["v2/assets/cards", "assets/database/pokemon"]
    unique_attacks = {}
    unique_abilities = {}
    
    # Process card files from both directories in sorted order
    for cards_dir in cards_dirs:
        if not os.path.exists(cards_dir):
            print(f"Cards directory not found: {cards_dir}")
            continue
            
        # Sort filenames to ensure consistent processing order
        filenames = sorted([f for f in os.listdir(cards_dir) if f.endswith('.json')])
        
        for filename in filenames:
            print(f"Processing {filename}...")
            with open(os.path.join(cards_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for card in data:
                card_id = card.get('id', '')
                pokemon_name = to_camel_case(card.get('name', ''))
                
                # Process attacks
                for attack in card.get('attacks', []):
                    effect = attack.get('effect', attack.get('text', ''))
                    # Convert damage to integer, defaulting to 0 if empty or invalid
                    try:
                        damage = int(attack.get('damage', '0'))
                    except (ValueError, TypeError):
                        damage = 0
                    attack_name = to_camel_case(attack.get('name', ''))
                    position = 'active'  # Default position
                    target = 'active'  # Default target
                    
                    # Create descriptive ID
                    attack_id = f"{card_id}_{pokemon_name}_{attack_name}_{position}_{target}"
                    
                    # Use descriptive ID as uniqueness key
                    if attack_id not in unique_attacks:
                        unique_attacks[attack_id] = {
                            'damage': damage,
                            'effect': effect,
                            'id': attack_id
                        }
                
                # Process abilities
                for ability in card.get('abilities', []):
                    effect = ability.get('effect', ability.get('text', ''))
                    ability_name = to_camel_case(ability.get('name', ''))
                    position = 'active'  # Default position
                    target = 'active'  # Default target
                    
                    # Create descriptive ID
                    ability_id = f"{pokemon_name}_{ability_name}_{card_id}_{position}_{target}"
                    
                    # Use descriptive ID as uniqueness key
                    if ability_id not in unique_abilities:
                        unique_abilities[ability_id] = {
                            'effect': effect,
                            'id': ability_id
                        }
    
    # Convert to lists and sort by ID
    clean_attacks = sorted(list(unique_attacks.values()), key=lambda x: x['id'])
    clean_abilities = sorted(list(unique_abilities.values()), key=lambda x: x['id'])
    
    # Save to files
    with open('unique_attack_effects.json', 'w', encoding='utf-8') as f:
        json.dump(clean_attacks, f, indent=2, ensure_ascii=False)
    
    with open('unique_ability_effects.json', 'w', encoding='utf-8') as f:
        json.dump(clean_abilities, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {len(clean_attacks)} unique attacks and {len(clean_abilities)} unique abilities")

if __name__ == "__main__":
    analyze_cards() 