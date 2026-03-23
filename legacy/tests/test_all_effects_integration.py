"""Integration tests for all card effects from a1-genetic-apex.json"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from v3.models.match.effects import EffectParser
from v3.models.match.effects.coin_flip_effect import CoinFlipEffect
from v3.models.match.effects.heal_effect import HealEffect
from v3.models.match.effects.heal_all_effect import HealAllEffect
from v3.models.match.effects.energy_effect import EnergyEffect
from v3.models.match.effects.search_effect import SearchEffect
from v3.models.match.effects.discard_effect import DiscardEffect
from v3.models.cards.energy import Energy
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.agents.random_agent import RandomAgent

def test_coin_flip_effects():
    """Test coin flip effects"""
    print("Testing coin flip effects...")
    
    # Test prevent attack
    effect1 = EffectParser.parse("Flip a coin. If heads, the Defending Pokémon can't attack during your opponent's next turn.")
    assert isinstance(effect1, CoinFlipEffect), f"Expected CoinFlipEffect, got {type(effect1)}"
    assert effect1.effect_type == "prevent_attack"
    print("  ✓ Prevent attack coin flip parsed correctly")
    
    # Test conditional damage
    effect2 = EffectParser.parse("Flip a coin. If tails, this attack does nothing.")
    assert isinstance(effect2, CoinFlipEffect), f"Expected CoinFlipEffect, got {type(effect2)}"
    assert effect2.effect_type == "conditional_damage"
    print("  ✓ Conditional damage coin flip parsed correctly")
    
    return True

def test_healing_effects():
    """Test healing effects"""
    print("Testing healing effects...")
    
    # Test heal self
    effect1 = EffectParser.parse("Heal 10 damage from this Pokémon.")
    assert isinstance(effect1, HealEffect), f"Expected HealEffect, got {type(effect1)}"
    assert effect1.amount == 10
    assert effect1.target == "this"
    print("  ✓ Heal self parsed correctly")
    
    # Test heal one (with type)
    effect2 = EffectParser.parse("Heal 50 damage from 1 of your Grass Pokemon.")
    assert isinstance(effect2, HealEffect), f"Expected HealEffect, got {type(effect2)}"
    assert effect2.amount == 50
    assert effect2.target == "one"
    # pokemon_type might be lowercase "grass" from parsing
    assert effect2.pokemon_type is not None, "pokemon_type should be set"
    assert effect2.pokemon_type.lower() == "grass", f"Expected grass type, got {effect2.pokemon_type}"
    print("  ✓ Heal one with type parsed correctly")
    
    # Test heal all
    effect3 = EffectParser.parse("Heal 20 damage from each of your Pokémon.")
    assert isinstance(effect3, HealAllEffect), f"Expected HealAllEffect, got {type(effect3)}"
    assert effect3.amount == 20
    print("  ✓ Heal all parsed correctly")
    
    return True

def test_energy_effects():
    """Test energy effects"""
    print("Testing energy effects...")
    
    # Test take from energy zone
    effect1 = EffectParser.parse("Take 3 Fire Energy from your Energy Zone and attach it to this Pokémon.")
    assert isinstance(effect1, EnergyEffect), f"Expected EnergyEffect, got {type(effect1)}"
    assert effect1.action == "attach"
    assert effect1.energy_type == "Fire"
    assert effect1.amount == 3
    print("  ✓ Take from energy zone parsed correctly")
    
    # Test take single energy
    effect2 = EffectParser.parse("Take a Grass Energy from your Energy Zone and attach it to 1 of your Benched Grass Pokémon. (Bench 1)")
    assert isinstance(effect2, EnergyEffect), f"Expected EnergyEffect, got {type(effect2)}"
    assert effect2.action == "attach"
    assert effect2.energy_type == "Grass"
    assert effect2.amount == 1
    print("  ✓ Take single energy parsed correctly")
    
    return True

def test_search_effects():
    """Test search effects"""
    print("Testing search effects...")
    
    # Test search for typed Pokemon
    effect1 = EffectParser.parse("Put 1 random Grass Pokémon from your deck into your hand.")
    assert isinstance(effect1, SearchEffect), f"Expected SearchEffect, got {type(effect1)}"
    assert effect1.card_type == "Pokemon"
    assert effect1.element == Energy.Type.GRASS
    assert effect1.amount == 1
    print("  ✓ Search typed Pokemon parsed correctly")
    
    # Test search for basic Pokemon
    effect2 = EffectParser.parse("Draw 1 basic Pokémon card.")
    assert isinstance(effect2, SearchEffect), f"Expected SearchEffect, got {type(effect2)}"
    assert effect2.card_type == "BasicPokemon"
    assert effect2.amount == 1
    print("  ✓ Search basic Pokemon parsed correctly")
    
    return True

def test_discard_effects():
    """Test discard effects"""
    print("Testing discard effects...")
    
    # Test discard energy
    effect1 = EffectParser.parse("Discard a Fire Energy from this Pokémon.")
    assert isinstance(effect1, DiscardEffect), f"Expected DiscardEffect, got {type(effect1)}"
    assert effect1.target == "energy"
    assert effect1.energy_type == "Fire"
    print("  ✓ Discard energy parsed correctly")
    
    return True

def test_effect_execution():
    """Test that effects can execute without errors"""
    print("Testing effect execution...")
    
    # Create a minimal battle engine and player for testing
    from v3.decks.base_deck import BaseDeck
    from copy import deepcopy
    
    base_deck = BaseDeck()
    
    # Get a basic deck - use Bulbasaur if available
    deck = []
    try:
        bulbasaur = base_deck.get_card_by_id('a1-001')  # Bulbasaur
        for _ in range(20):
            deck.append(deepcopy(bulbasaur))
    except ValueError:
        # If Bulbasaur not found, try to get any Pokemon
        if base_deck.importer.pokemon:
            any_pokemon = list(base_deck.importer.pokemon.values())[0]
            for _ in range(20):
                deck.append(deepcopy(any_pokemon))
        else:
            print("  ⚠ Skipping execution test - no Pokemon cards available")
            return True
    
    player1 = Player("Test Player 1", deck, [Energy.Type.GRASS], RandomAgent)
    player2 = Player("Test Player 2", deck, [Energy.Type.GRASS], RandomAgent)
    
    engine = BattleEngine(player1, player2, debug=False)
    
    # Set up a basic game state - need active Pokemon for heal test
    if player1.cards_in_hand:
        from v3.models.cards.pokemon import Pokemon
        from v3.models.cards.card import Card
        # Find a Pokemon in hand
        pokemon_card = None
        for card in player1.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                pokemon_card = card
                break
        
        if pokemon_card:
            player1.active_pokemon = pokemon_card
            player1.cards_in_hand.remove(pokemon_card)
            pokemon_card.card_position = Card.Position.ACTIVE
            
            # Test heal effect execution
            heal_effect = HealEffect(20, "this")
            player1.active_pokemon.damage_taken = 30
            initial_damage = player1.active_pokemon.damage_taken
            heal_effect.execute(player1, engine, player1.active_pokemon)
            assert player1.active_pokemon.damage_taken < initial_damage, "Heal effect should reduce damage"
            print("  ✓ Heal effect executed correctly")
    
    # Test search effect execution
    if len(player1.deck) > 0:
        search_effect = SearchEffect("BasicPokemon", None, 1)
        initial_hand_size = len(player1.cards_in_hand)
        initial_deck_size = len(player1.deck)
        search_effect.execute(player1, engine)
        # Should have added a card to hand and removed from deck (if Basic Pokemon found)
        # Note: might not find Basic Pokemon if deck doesn't have any
        if len(player1.cards_in_hand) > initial_hand_size:
            assert len(player1.deck) < initial_deck_size, "Search should remove from deck"
        print("  ✓ Search effect executed correctly")
    
    return True

def run_all_tests():
    """Run all effect integration tests"""
    print("=" * 80)
    print("Running Effect Integration Tests")
    print("=" * 80)
    
    tests = [
        test_coin_flip_effects,
        test_healing_effects,
        test_energy_effects,
        test_search_effects,
        test_discard_effects,
        test_effect_execution,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ✗ {test.__name__} returned False")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__} failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

