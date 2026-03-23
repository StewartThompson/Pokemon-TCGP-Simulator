"""Test Step 24: Integrate Effect Parser into Attack Execution"""
import sys
sys.path.insert(0, '.')

from v3.models.match.battle_engine import BattleEngine
from v3.models.match.player import Player
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.cards.attack import Attack
from v3.models.cards.ability import Ability
from v3.models.agents.random_agent import RandomAgent

def test_attack_effects():
    """Test attack effects are executed"""
    # Create Basic Pokemon for deck
    basic1 = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                    Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    basic2 = Pokemon("basic-002", "Charmander", Energy.Type.FIRE, Card.Type.POKEMON,
                    Card.Subtype.BASIC, 60, "Set", "Pack", "Common", [], 1, Energy.Type.WATER, None)
    
    # Create Pokemon with heal attack
    heal_ability = Ability("Giant Bloom Effect", "Heal 30 damage from this Pokémon.", 
                          Ability.Target.PLAYER_ACTIVE, Card.Position.ACTIVE)
    heal_attack = Attack("Giant Bloom", 100, Energy.from_string_list(["Grass", "Grass", "Colorless", "Colorless"]), heal_ability)
    
    attacker = Pokemon("test-001", "Venusaur ex", Energy.Type.GRASS, Card.Type.POKEMON,
                      Card.Subtype.STAGE_2, 190, "Set", "Pack", "Rare EX", [heal_attack], 3, Energy.Type.FIRE, "Ivysaur")
    
    # Damage the attacker first
    attacker.damage_taken = 50
    
    # Create defender
    defender = Pokemon("test-002", "Charmander", Energy.Type.FIRE, Card.Type.POKEMON,
                      Card.Subtype.BASIC, 60, "Set", "Pack", "Common", [], 1, Energy.Type.WATER, None)
    
    # Create players and engine (need Basic Pokemon in deck)
    deck1 = [basic1] * 19 + [attacker]
    deck2 = [basic2] * 19 + [defender]
    player1 = Player("Player 1", deck1, [Energy.Type.GRASS])
    player2 = Player("Player 2", deck2, [Energy.Type.FIRE])
    
    engine = BattleEngine(player1, player2, debug=False)
    engine._setup_game()
    
    # Set up attacker and defender
    player1.active_pokemon = attacker
    player2.active_pokemon = defender
    
    # Attach energy to attacker
    attacker.equipped_energies[Energy.Type.GRASS] = 2
    attacker.equipped_energies[Energy.Type.NORMAL] = 2
    
    # Execute attack
    initial_damage = attacker.damage_taken
    engine._execute_attack(attacker, heal_attack, player1, player2)
    
    # Check that healing occurred
    assert attacker.damage_taken < initial_damage, f"Expected damage to decrease, got {attacker.damage_taken} (was {initial_damage})"
    assert attacker.damage_taken == max(0, initial_damage - 30), f"Expected damage {max(0, initial_damage - 30)}, got {attacker.damage_taken}"
    
    print("✓ Attack effects execution tests passed")
    return True

if __name__ == "__main__":
    success = test_attack_effects()
    exit(0 if success else 1)

