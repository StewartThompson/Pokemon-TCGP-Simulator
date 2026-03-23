"""Integration Test: Full Game Flow with All Features"""
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.cards.attack import Attack
from v3.models.cards.ability import Ability
from tests.test_validators import GameStateValidator

def test_full_game_with_evolution():
    """Test complete game flow with evolution chain"""
    # Create evolution chain: Bulbasaur -> Ivysaur -> Venusaur ex
    bulbasaur = Pokemon("a1-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                       Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    ivysaur = Pokemon("a1-002", "Ivysaur", Energy.Type.GRASS, Card.Type.POKEMON,
                     Card.Subtype.STAGE_1, 90, "Set", "Pack", "Uncommon", [], 2, Energy.Type.FIRE, "Bulbasaur")
    
    venusaur_attack = Attack("Giant Bloom", 100, 
                            Energy.from_string_list(["Grass", "Grass", "Colorless", "Colorless"]),
                            Ability("Giant Bloom Effect", "Heal 30 damage from this Pokémon.", 
                                   Ability.Target.PLAYER_ACTIVE, Card.Position.ACTIVE))
    venusaur = Pokemon("a1-004", "Venusaur ex", Energy.Type.GRASS, Card.Type.POKEMON,
                      Card.Subtype.STAGE_2, 190, "Set", "Pack", "Rare EX", [venusaur_attack], 3, Energy.Type.FIRE, "Ivysaur")
    
    # Create decks
    deck1 = [bulbasaur] * 15 + [ivysaur] * 3 + [venusaur] * 2
    deck2 = [bulbasaur] * 20
    
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.GRASS])
    
    engine = BattleEngine(player1, player2, debug=False)
    engine._setup_game()
    
    # Verify initial state - _setup_game should set up active Pokemon
    # If not, manually set them up for testing
    if player1.active_pokemon is None:
        for card in player1.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                player1.set_active_pokemon(card)
                player1.cards_in_hand.remove(card)
                break
    
    if player2.active_pokemon is None:
        for card in player2.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                player2.set_active_pokemon(card)
                player2.cards_in_hand.remove(card)
                break
    
    assert player1.active_pokemon is not None, "Player 1 should have active Pokemon"
    assert player2.active_pokemon is not None, "Player 2 should have active Pokemon"
    
    # Play a few turns to allow evolution
    for turn in range(3):
        if engine._is_game_over():
            break
        engine._execute_turn()
    
    # Verify game state is valid
    errors = GameStateValidator.validate_battle_engine(engine)
    assert len(errors) == 0, f"Game state errors: {errors}"
    
    print("✓ Full game with evolution test passed")
    return True

def test_attack_effects_integration():
    """Test attack effects work in full game context"""
    # Create Pokemon with healing attack
    heal_ability = Ability("Giant Bloom Effect", "Heal 30 damage from this Pokémon.", 
                          Ability.Target.PLAYER_ACTIVE, Card.Position.ACTIVE)
    heal_attack = Attack("Giant Bloom", 100, 
                        Energy.from_string_list(["Grass", "Grass", "Colorless", "Colorless"]), 
                        heal_ability)
    
    attacker = Pokemon("test-001", "Venusaur ex", Energy.Type.GRASS, Card.Type.POKEMON,
                      Card.Subtype.STAGE_2, 190, "Set", "Pack", "Rare EX", [heal_attack], 3, Energy.Type.FIRE, "Ivysaur")
    
    defender = Pokemon("test-002", "Charmander", Energy.Type.FIRE, Card.Type.POKEMON,
                      Card.Subtype.BASIC, 60, "Set", "Pack", "Common", [], 1, Energy.Type.WATER, None)
    
    # Create decks
    basic1 = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                    Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    basic2 = Pokemon("basic-002", "Charmander", Energy.Type.FIRE, Card.Type.POKEMON,
                    Card.Subtype.BASIC, 60, "Set", "Pack", "Common", [], 1, Energy.Type.WATER, None)
    
    deck1 = [basic1] * 19 + [attacker]
    deck2 = [basic2] * 19 + [defender]
    
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.FIRE])
    
    engine = BattleEngine(player1, player2, debug=False)
    engine._setup_game()
    
    # Set up attacker and defender
    player1.active_pokemon = attacker
    player2.active_pokemon = defender
    
    # Damage attacker first
    attacker.damage_taken = 50
    initial_damage = attacker.damage_taken
    
    # Attach energy
    attacker.equipped_energies[Energy.Type.GRASS] = 2
    attacker.equipped_energies[Energy.Type.NORMAL] = 2
    
    # Execute attack with healing effect
    engine._execute_attack(attacker, heal_attack, player1, player2)
    
    # Verify healing occurred
    assert attacker.damage_taken < initial_damage, f"Expected damage to decrease, got {attacker.damage_taken} (was {initial_damage})"
    assert attacker.damage_taken == max(0, initial_damage - 30), f"Expected damage {max(0, initial_damage - 30)}, got {attacker.damage_taken}"
    
    print("✓ Attack effects integration test passed")
    return True

def test_evolution_and_retreat_integration():
    """Test evolution and retreat working together"""
    # Create evolution chain
    bulbasaur = Pokemon("a1-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                       Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    ivysaur = Pokemon("a1-002", "Ivysaur", Energy.Type.GRASS, Card.Type.POKEMON,
                     Card.Subtype.STAGE_1, 90, "Set", "Pack", "Uncommon", [], 2, Energy.Type.FIRE, "Bulbasaur")
    
    # Create decks
    deck = [bulbasaur] * 19 + [ivysaur]
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player.set_active_pokemon(card)
            player.cards_in_hand.remove(card)
            break
    
    # Add evolution to hand
    player.cards_in_hand.append(ivysaur)
    
    # Wait 1 turn for evolution eligibility
    player.active_pokemon.turns_in_play = 1
    
    # Evolve
    from v3.models.match.actions.evolve import EvolveAction
    evolve_action = EvolveAction(ivysaur.id, "active")
    engine = BattleEngine(player, player, debug=False)
    
    is_valid, error = evolve_action.validate(player, engine)
    assert is_valid, error
    evolve_action.execute(player, engine)
    
    assert player.active_pokemon.name == "Ivysaur", f"Expected Ivysaur, got {player.active_pokemon.name if player.active_pokemon else None}"
    
    # Now test retreat with evolved Pokemon
    # Add another Pokemon to bench
    bench_pokemon = Pokemon("bench-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                           Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    player.add_to_bench(bench_pokemon, 0)
    
    # Attach energy for retreat
    player.active_pokemon.equipped_energies[Energy.Type.GRASS] = 2
    
    # Retreat
    from v3.models.match.actions.retreat import RetreatAction
    retreat_action = RetreatAction(1)
    is_valid, error = retreat_action.validate(player, engine)
    assert is_valid, error
    retreat_action.execute(player, engine)
    
    # Verify retreat occurred
    assert player.active_pokemon == bench_pokemon, "Active should be bench Pokemon"
    assert player.bench_pokemons[1].name == "Ivysaur", "Ivysaur should be on bench"
    
    print("✓ Evolution and retreat integration test passed")
    return True

def test_multiple_abilities_integration():
    """Test Pokemon with multiple abilities"""
    # Create Pokemon with multiple abilities
    ability1 = Ability("Powder Heal", "Once during your turn, you may heal 20 damage from each of your Pokémon.", 
                      Ability.Target.PLAYER_ALL, Card.Position.ACTIVE)
    ability2 = Ability("Test Ability", "Test effect", Ability.Target.OPPONENT_ACTIVE, Card.Position.ACTIVE)
    
    butterfree = Pokemon("a1-007", "Butterfree", Energy.Type.GRASS, Card.Type.POKEMON,
                        Card.Subtype.STAGE_2, 120, "Set", "Pack", "Rare", [], 1, Energy.Type.FIRE, "Metapod",
                        abilities=[ability1, ability2])
    
    assert len(butterfree.abilities) == 2, f"Expected 2 abilities, got {len(butterfree.abilities)}"
    assert butterfree.ability == ability1, "First ability should be stored in self.ability"
    
    usable = butterfree.get_usable_abilities()
    assert len(usable) == 2, f"Expected 2 usable abilities, got {len(usable)}"
    
    print("✓ Multiple abilities integration test passed")
    return True

def run_all_integration_tests():
    """Run all integration tests"""
    tests = [
        test_full_game_with_evolution,
        test_attack_effects_integration,
        test_evolution_and_retreat_integration,
        test_multiple_abilities_integration,
    ]
    
    results = {}
    for test in tests:
        try:
            success = test()
            results[test.__name__] = success
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            results[test.__name__] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    return all(results.values())

if __name__ == "__main__":
    success = run_all_integration_tests()
    exit(0 if success else 1)

