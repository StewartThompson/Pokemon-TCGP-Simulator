"""Test Step 26: Implement Retreat Action"""
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.retreat import RetreatAction
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon

def test_retreat():
    """Test retreat action"""
    # Create Basic Pokemon for deck
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    deck = [basic] * 20
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active and bench Pokemon
    pokemon1 = None
    pokemon2 = None
    pokemon3 = None
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            if not pokemon1:
                pokemon1 = card
                player.set_active_pokemon(card)
                player.cards_in_hand.remove(card)
            elif not pokemon2:
                pokemon2 = card
                player.add_to_bench(card, 0)  # Put in bench slot 0
                player.cards_in_hand.remove(card)
            elif not pokemon3:
                pokemon3 = card
                # Don't add to bench yet - we'll retreat to slot 1
            if pokemon1 and pokemon2 and pokemon3:
                break
    
    # Attach energy for retreat cost
    player.active_pokemon.equipped_energies[Energy.Type.GRASS] = 1
    
    # Test retreat to bench slot 1 (slot 0 has pokemon2)
    action = RetreatAction(1)  # Retreat to bench slot 1
    engine = BattleEngine(player, player, debug=False)
    
    is_valid, error = action.validate(player, engine)
    assert is_valid, error
    
    old_active = player.active_pokemon
    old_bench = player.bench_pokemons[0]  # pokemon2
    action.execute(player, engine)
    
    # Check retreat occurred
    assert player.active_pokemon == old_bench, f"Active Pokemon should be {old_bench.name}, got {player.active_pokemon.name if player.active_pokemon else None}"
    assert old_active in [p for p in player.bench_pokemons if p is not None], "Old active should be on bench"
    assert player.bench_pokemons[1] == old_active, "Old active should be at bench slot 1"
    
    print("✓ Retreat tests passed")
    return True

if __name__ == "__main__":
    success = test_retreat()
    exit(0 if success else 1)

