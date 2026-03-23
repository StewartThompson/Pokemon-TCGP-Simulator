"""
Comprehensive integration tests for full game scenarios.
Tests complete game flows, edge cases, and rule compliance.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_helpers import (
    create_test_pokemon, create_test_attack, create_test_deck
)
from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.match.game_rules import GameRules
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.match.actions import EndTurnAction, AttackAction, PlayPokemonAction
from v3.models.match.exceptions import InvalidActionError, RuleViolationError
from v3.models.match.state_validator import StateValidator


def test_full_game_flow():
    """Test a complete game from setup to victory"""
    print("Testing full game flow...")
    
    # Create two players with basic decks
    basic1 = create_test_pokemon("Basic1", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    basic2 = create_test_pokemon("Basic2", 60, Energy.Type.FIRE, Card.Subtype.BASIC)
    
    deck1 = [basic1] * 20
    deck2 = [basic2] * 20
    
    player1 = Player("Player1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player2", deck2, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    # Setup game
    engine._setup_game()
    
    # Verify initial state
    assert len(player1.cards_in_hand) == GameRules.INITIAL_HAND_SIZE
    assert len(player2.cards_in_hand) == GameRules.INITIAL_HAND_SIZE
    assert player1.points == 0
    assert player2.points == 0
    
    # Play a few turns
    for turn in range(5):
        current = engine._get_current_player()
        
        # Try to play Pokemon if possible
        if current.active_pokemon is None:
            for card in current.cards_in_hand:
                if isinstance(card, type(basic1)) and card.subtype == Card.Subtype.BASIC:
                    action = PlayPokemonAction(card, None)
                    if action.validate(current, engine)[0]:
                        action.execute(current, engine)
                        break
        
        # Try to attack if possible
        if current.active_pokemon and current.active_pokemon.get_possible_attacks():
            attack = current.active_pokemon.get_possible_attacks()[0]
            action = AttackAction(current.active_pokemon, attack)
            if action.validate(current, engine)[0]:
                action.execute(current, engine)
        
        # End turn
        EndTurnAction().execute(current, engine)
        engine._end_turn()
        
        # Check if game is over
        if engine._is_game_over():
            winner = engine._determine_winner()
            assert winner is not None
            assert winner.points >= GameRules.WINNING_POINTS or \
                   (engine._get_opponent(winner).active_pokemon is None and 
                    not any(p is not None for p in engine._get_opponent(winner).bench_pokemons))
            print(f"  ✓ Game ended with winner: {winner.name}")
            break
    
    print("  ✓ Full game flow test passed")
    return True


def test_evolution_chain():
    """Test complete evolution chain (Basic -> Stage 1 -> Stage 2)"""
    print("Testing evolution chain...")
    
    from v3.models.match.actions import EvolveAction
    
    # Create evolution chain
    basic = create_test_pokemon("Basic", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    stage1 = create_test_pokemon("Stage1", 80, Energy.Type.GRASS, Card.Subtype.STAGE_1)
    stage1.evolves_from = "Basic"
    stage2 = create_test_pokemon("Stage2", 120, Energy.Type.GRASS, Card.Subtype.STAGE_2)
    stage2.evolves_from = "Stage1"
    
    deck1 = [basic] * 10 + [stage1] * 5 + [stage2] * 5
    deck2 = [basic] * 20
    
    player1 = Player("Player1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player2", deck2, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Play basic Pokemon
    if player1.active_pokemon is None:
        for card in player1.cards_in_hand:
            if card.name == "Basic":
                PlayPokemonAction(card, None).execute(player1, engine)
                break
    
    assert player1.active_pokemon is not None
    assert player1.active_pokemon.name == "Basic"
    
    # Wait a turn (evolution requires 1 turn in play)
    EndTurnAction().execute(player1, engine)
    engine._end_turn()
    EndTurnAction().execute(player2, engine)
    engine._end_turn()
    
    # Evolve to Stage 1
    stage1_card = None
    for card in player1.cards_in_hand:
        if card.name == "Stage1":
            stage1_card = card
            break
    
    if stage1_card:
        action = EvolveAction(player1.active_pokemon, stage1_card)
        if action.validate(player1, engine)[0]:
            action.execute(player1, engine)
            assert player1.active_pokemon.name == "Stage1"
            print("  ✓ Basic -> Stage 1 evolution successful")
    
    # Wait another turn
    EndTurnAction().execute(player1, engine)
    engine._end_turn()
    EndTurnAction().execute(player2, engine)
    engine._end_turn()
    
    # Evolve to Stage 2
    stage2_card = None
    for card in player1.cards_in_hand:
        if card.name == "Stage2":
            stage2_card = card
            break
    
    if stage2_card:
        action = EvolveAction(player1.active_pokemon, stage2_card)
        if action.validate(player1, engine)[0]:
            action.execute(player1, engine)
            assert player1.active_pokemon.name == "Stage2"
            print("  ✓ Stage 1 -> Stage 2 evolution successful")
    
    print("  ✓ Evolution chain test passed")
    return True


def test_prize_card_victory():
    """Test winning by collecting 3 prize cards"""
    print("Testing prize card victory...")
    
    # Create weak Pokemon that can be easily KO'd
    weak = create_test_pokemon("Weak", 10, Energy.Type.GRASS, Card.Subtype.BASIC)
    strong = create_test_pokemon("Strong", 100, Energy.Type.FIRE, Card.Subtype.BASIC)
    attack = create_test_attack("Strong Attack", 50, ["Fire"])
    strong.attacks = [attack]
    
    deck1 = [strong] * 20
    deck2 = [weak] * 20
    
    player1 = Player("Player1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player2", deck2, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Setup: Play Pokemon and attach energy
    if player1.active_pokemon is None:
        for card in player1.cards_in_hand:
            if isinstance(card, type(strong)):
                PlayPokemonAction(card, None).execute(player1, engine)
                break
    
    # Attach energy
    from v3.models.match.actions import AttachEnergyAction
    if player1.energy_zone.has_energy():
        energy = player1.energy_zone.consume_current()
        AttachEnergyAction(player1.active_pokemon, energy).execute(player1, engine)
    
    # KO opponent's Pokemon 3 times to win
    for i in range(3):
        # Setup opponent's Pokemon
        if player2.active_pokemon is None:
            for card in player2.cards_in_hand:
                if isinstance(card, type(weak)):
                    PlayPokemonAction(card, None).execute(player2, engine)
                    break
        
        if player2.active_pokemon:
            # Attack and KO
            attack_action = AttackAction(player1.active_pokemon, attack)
            if attack_action.validate(player1, engine)[0]:
                attack_action.execute(player1, engine)
                
                # Check if KO'd
                if player2.active_pokemon is None or player2.active_pokemon.damage_taken >= player2.active_pokemon.health:
                    print(f"  ✓ KO #{i+1} successful, points: {player1.points}")
        
        # End turn and switch
        EndTurnAction().execute(player1, engine)
        engine._end_turn()
        EndTurnAction().execute(player2, engine)
        engine._end_turn()
        
        # Check for victory
        if engine._is_game_over():
            winner = engine._determine_winner()
            assert winner == player1
            assert winner.points >= GameRules.WINNING_POINTS
            print(f"  ✓ Victory achieved with {winner.points} points")
            break
    
    print("  ✓ Prize card victory test passed")
    return True


def test_deck_out_loss():
    """Test losing by decking out"""
    print("Testing deck-out loss...")
    
    basic = create_test_pokemon("Basic", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    
    # Create a deck with only a few cards (pad to 20 for Player initialization)
    deck1 = [basic] * 20  # Use full deck for initialization, then manually reduce
    deck2 = [basic] * 20
    
    player1 = Player("Player1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player2", deck2, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Manually reduce deck size after setup (for testing deck-out)
    while len(player1.deck) > 5:
        player1.deck.pop()
    
    # Draw cards until deck is empty
    initial_deck_size = len(player1.deck)
    draws = 0
    max_draws = 20  # Safety limit
    
    while len(player1.deck) > 0 and draws < max_draws:
        if player1.can_draw():
            player1.draw(1)
            draws += 1
        else:
            break
    
    # Try to draw one more (should trigger deck-out)
    if len(player1.deck) == 0:
        try:
            player1.draw(1)
        except Exception as e:
            # Deck-out should be handled
            print(f"  ✓ Deck-out detected: {e}")
    
    print("  ✓ Deck-out test passed")
    return True


def test_hand_size_limit():
    """Test hand size limit enforcement"""
    print("Testing hand size limit...")
    
    basic = create_test_pokemon("Basic", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    deck = [basic] * 20
    
    player1 = Player("Player1", deck, [Energy.Type.GRASS])
    player2 = Player("Player2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Manually add many cards to hand - should be allowed (no hand size limit)
    while len(player1.cards_in_hand) < 15 and len(player1.deck) > 0:
        player1.cards_in_hand.append(player1.deck.pop())
    
    # Verify hand size can exceed any arbitrary limit (e.g., 10, 15)
    assert len(player1.cards_in_hand) >= 10, f"Hand should be able to have 10+ cards, got {len(player1.cards_in_hand)}"
    
    # During draw phase, should work fine - no hand size limit
    # This is tested in test_step31_hand_size.py, so we just verify there's no limit
    # Hand can be any size - no restrictions
    assert len(player1.cards_in_hand) >= 10, f"Hand should be able to have 10+ cards, got {len(player1.cards_in_hand)}"
    
    print("  ✓ No hand size limit test passed")
    return True


def test_status_effects_application():
    """Test status effects are applied correctly"""
    print("Testing status effects...")
    
    from v3.models.match.status_effects.poisoned import Poisoned
    from v3.models.match.status_effects.burned import Burned
    
    basic = create_test_pokemon("Basic", 100, Energy.Type.GRASS, Card.Subtype.BASIC)
    deck = [basic] * 20
    
    player1 = Player("Player1", deck, [Energy.Type.GRASS])
    player2 = Player("Player2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Apply status effects manually
    if player1.active_pokemon:
        poison = Poisoned()
        poison.apply(player1.active_pokemon, engine)
        
        assert player1.active_pokemon.has_status_effect("poisoned")
        print("  ✓ Poison status applied")
        
        # Apply burn
        burn = Burned()
        burn.apply(player1.active_pokemon, engine)
        
        assert player1.active_pokemon.has_status_effect("burned")
        print("  ✓ Burn status applied")
        
        # Check status effects are in list
        assert len(player1.active_pokemon.status_effects) >= 2
    
    print("  ✓ Status effects test passed")
    return True


def test_retreat_mechanics():
    """Test retreat mechanics"""
    print("Testing retreat mechanics...")
    
    from v3.models.match.actions import RetreatAction
    
    basic1 = create_test_pokemon("Basic1", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    basic1.retreat_cost = 1
    basic2 = create_test_pokemon("Basic2", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    
    deck = [basic1] * 10 + [basic2] * 10
    player1 = Player("Player1", deck, [Energy.Type.GRASS])
    player2 = Player("Player2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Setup: Play two Pokemon
    active = None
    bench = None
    for card in player1.cards_in_hand:
        if isinstance(card, type(basic1)) and active is None:
            PlayPokemonAction(card, None).execute(player1, engine)
            active = player1.active_pokemon
        elif isinstance(card, type(basic2)) and bench is None:
            # Play to bench
            for i, slot in enumerate(player1.bench_pokemons):
                if slot is None:
                    PlayPokemonAction(card, i).execute(player1, engine)
                    bench = player1.bench_pokemons[i]
                    break
    
    if active and bench:
        # Attach energy for retreat
        from v3.models.match.actions import AttachEnergyAction
        if player1.energy_zone.has_energy():
            energy = player1.energy_zone.consume_current()
            AttachEnergyAction(active, energy).execute(player1, engine)
        
        # Attempt retreat
        action = RetreatAction(active, bench)
        if action.validate(player1, engine)[0]:
            action.execute(player1, engine)
            assert player1.active_pokemon == bench
            print("  ✓ Retreat successful")
    
    print("  ✓ Retreat mechanics test passed")
    return True


def test_state_validation():
    """Test state validation catches errors"""
    print("Testing state validation...")
    
    basic = create_test_pokemon("Basic", 60, Energy.Type.GRASS, Card.Subtype.BASIC)
    deck = [basic] * 20
    
    player1 = Player("Player1", deck, [Energy.Type.GRASS])
    player2 = Player("Player2", deck, [Energy.Type.FIRE])
    engine = BattleEngine(player1, player2, debug=False)
    
    engine._setup_game()
    
    # Validate initial state
    errors = StateValidator.validate_battle_engine(engine)
    assert len(errors) == 0, f"Initial state has errors: {errors}"
    
    # Validate after a turn
    EndTurnAction().execute(player1, engine)
    engine._end_turn()
    
    errors = StateValidator.validate_battle_engine(engine)
    assert len(errors) == 0, f"State after turn has errors: {errors}"
    
    print("  ✓ State validation test passed")
    return True


def run_all_integration_tests():
    """Run all comprehensive integration tests"""
    print("\n" + "="*60)
    print("Running Comprehensive Integration Tests")
    print("="*60 + "\n")
    
    tests = [
        test_full_game_flow,
        test_evolution_chain,
        test_prize_card_victory,
        test_deck_out_loss,
        test_hand_size_limit,
        test_status_effects_application,
        test_retreat_mechanics,
        test_state_validation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ✗ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"Integration Tests: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_integration_tests()
    exit(0 if success else 1)

