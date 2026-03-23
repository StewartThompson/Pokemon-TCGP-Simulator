"""Test Step 30: Implement Ability Activation"""
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.use_ability import UseAbilityAction
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.ability import Ability

def test_ability_activation():
    """Test ability activation"""
    # Create Pokemon with ability
    ability = Ability("Powder Heal", "Once during your turn, you may heal 20 damage from each of your Pokémon.",
                     Ability.Target.PLAYER_ALL, Card.Position.ACTIVE)
    
    # Create Basic Pokemon for deck
    basic = Pokemon("basic-001", "Caterpie", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 50, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    
    butterfree = Pokemon("a1-007", "Butterfree", Energy.Type.GRASS, Card.Type.POKEMON,
                        Card.Subtype.STAGE_2, 120, "Set", "Pack", "Rare", [], 1, Energy.Type.FIRE, "Metapod",
                        abilities=[ability])
    
    deck = [basic] * 19 + [butterfree]
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon):
            if card.name == "Butterfree":
                player.set_active_pokemon(card)
                player.cards_in_hand.remove(card)
                break
    
    # If Butterfree not in hand, add it manually
    if player.active_pokemon is None or player.active_pokemon.name != "Butterfree":
        player.set_active_pokemon(butterfree)
    
    # Damage Pokemon
    player.active_pokemon.damage_taken = 30
    initial_damage = player.active_pokemon.damage_taken
    
    # Test ability activation
    action = UseAbilityAction("active", 0)
    engine = BattleEngine(player, player, debug=False)
    
    is_valid, error = action.validate(player, engine)
    assert is_valid, error
    
    action.execute(player, engine)
    
    # Check ability was used
    assert player.active_pokemon.used_ability_this_turn == True, "Ability should be marked as used"
    
    # Try to use ability again (should fail)
    action2 = UseAbilityAction("active", 0)
    is_valid2, error2 = action2.validate(player, engine)
    assert not is_valid2, "Should not be able to use ability twice in same turn"
    
    print("✓ Ability activation tests passed")
    return True

if __name__ == "__main__":
    success = test_ability_activation()
    exit(0 if success else 1)

