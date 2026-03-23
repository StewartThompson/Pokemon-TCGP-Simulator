# Create test file: tests/test_step15_attack.py
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.attack import Attack

def test_attack():
    """Test attack execution"""
    # Create Pokemon with attack
    attack = Attack("Vine Whip", 40, Energy.from_string_list(["Grass", "Colorless"]))
    deck1 = []
    deck2 = []
    for i in range(20):
        attacker_pokemon = Pokemon(f"test-{i:03d}", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                                  Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [attack], 1, Energy.Type.FIRE, None)
        defender_pokemon = Pokemon(f"def-{i:03d}", "Charmander", Energy.Type.FIRE, Card.Type.POKEMON,
                                  Card.Subtype.BASIC, 60, "Set", "Pack", "Common", [], 1, Energy.Type.WATER, None)
        deck1.append(attacker_pokemon)
        deck2.append(defender_pokemon)
    
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.FIRE])
    
    # Set up Pokemon BEFORE creating engine (to avoid turn_zero issues)
    player1.draw_inital_hand()
    player2.draw_inital_hand()
    
    for card in player1.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player1.set_active_pokemon(card)
            player1.cards_in_hand.remove(card)
            break
    
    for card in player2.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player2.set_active_pokemon(card)
            player2.cards_in_hand.remove(card)
            break
    
    engine = BattleEngine(player1, player2, debug=False)
    
    # Attach energy
    player1.active_pokemon.equipped_energies[Energy.Type.GRASS] = 1
    player1.active_pokemon.equipped_energies[Energy.Type.NORMAL] = 1
    
    # Test damage calculation
    damage = engine._calculate_damage(player1.active_pokemon, player2.active_pokemon, 40)
    # Should be 40 (no weakness - Fire is weak to Water, not Grass)
    assert damage == 40
    
    # Test with weakness
    player2.active_pokemon.weakness = Energy.Type.GRASS
    damage2 = engine._calculate_damage(player1.active_pokemon, player2.active_pokemon, 40)
    # Should be 40 + 20 = 60
    assert damage2 == 60
    
    # Test attack execution - reset weakness for this test
    player2.active_pokemon.weakness = Energy.Type.WATER  # Not weak to Grass
    assert player2.active_pokemon is not None, "Player 2 should have active Pokemon"
    initial_damage = player2.active_pokemon.damage_taken
    engine._execute_attack(player1.active_pokemon, attack, player1, player2)
    # Should have taken damage but not KO'd (40 damage < 60 HP)
    assert player2.active_pokemon is not None, "Pokemon should not be KO'd"
    assert player2.active_pokemon.damage_taken > initial_damage, "Damage should have been applied"
    
    print("✓ Attack tests passed")
    return True

if __name__ == "__main__":
    success = test_attack()
    exit(0 if success else 1)

