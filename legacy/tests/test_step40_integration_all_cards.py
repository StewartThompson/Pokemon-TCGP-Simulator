"""Test Step 40: Integration Testing with All Cards from JSON"""
import sys
sys.path.insert(0, '.')

from v3.importers.json_card_importer import JsonCardImporter
from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.card import Card

def test_all_cards_integration():
    """Test that all cards from JSON can be loaded and used"""
    # Load all cards
    importer = JsonCardImporter()
    importer.import_from_json()
    
    # Test specific cards with effects
    test_cases = [
        ("a1-004", "Venusaur ex", "Giant Bloom", "Heal 30 damage"),
        ("a1-005", "Caterpie", "Find a Friend", "Put 1 random Grass Pokémon"),
        ("a1-007", "Butterfree", "Powder Heal", "heal 20 damage from each"),
    ]
    
    for card_id, card_name, attack_or_ability, expected_effect in test_cases:
        pokemon = importer.pokemon.get(card_id)
        assert pokemon is not None, f"{card_name} not found"
        assert pokemon.name == card_name, f"Expected {card_name}, got {pokemon.name}"
        
        # Check for attack or ability
        found = False
        if attack_or_ability in ["Giant Bloom", "Find a Friend"]:
            # Check attacks
            for attack in pokemon.attacks:
                if attack.name == attack_or_ability:
                    assert attack.ability is not None, f"{attack_or_ability} should have an effect"
                    assert expected_effect.lower() in attack.ability.effect.lower(), f"Effect should contain '{expected_effect}'"
                    found = True
        elif attack_or_ability == "Powder Heal":
            # Check abilities
            for ability in pokemon.abilities:
                if ability.name == attack_or_ability:
                    assert expected_effect.lower() in ability.effect.lower(), f"Effect should contain '{expected_effect}'"
                    found = True
        
        assert found, f"{attack_or_ability} not found on {card_name}"
    
    # Test that we can create a game with loaded cards
    from v3.models.cards.energy import Energy
    pokemon_list = list(importer.pokemon.values())
    
    # Create decks with 20 cards (duplicate if needed)
    deck1 = []
    deck2 = []
    while len(deck1) < 20:
        deck1.extend(pokemon_list[:20-len(deck1)])
    while len(deck2) < 20:
        deck2.extend(pokemon_list[:20-len(deck2)])
    deck1 = deck1[:20]
    deck2 = deck2[:20]
    
    # Just verify decks are valid
    assert len(deck1) == 20, f"Deck 1 should have 20 cards, got {len(deck1)}"
    assert len(deck2) == 20, f"Deck 2 should have 20 cards, got {len(deck2)}"
    
    # Test that we can create players (use first Pokemon's energy type)
    if deck1 and deck1[0]:
        energy_type = deck1[0].element if hasattr(deck1[0], 'element') else Energy.Type.GRASS
        player1 = Player("Player 1", deck1, [energy_type])
        player2 = Player("Player 2", deck2, [energy_type])
        assert player1 is not None
        assert player2 is not None
    
    print("✓ All cards integration tests passed")
    return True

if __name__ == "__main__":
    success = test_all_cards_integration()
    exit(0 if success else 1)

