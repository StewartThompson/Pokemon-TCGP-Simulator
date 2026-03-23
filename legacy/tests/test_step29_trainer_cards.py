"""Test Step 29: Implement Trainer Card Actions"""
import sys
sys.path.insert(0, '.')

from v3.models.match.actions.play_item import PlayItemAction
from v3.models.match.actions.play_supporter import PlaySupporterAction
from v3.models.match.actions.attach_tool import AttachToolAction
from v3.models.match.player import Player
from v3.models.match.battle_engine import BattleEngine
from v3.models.cards.item import Item
from v3.models.cards.supporter import Supporter
from v3.models.cards.tool import Tool
from v3.models.cards.card import Card
from v3.models.cards.ability import Ability
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.energy import Energy

def test_play_item():
    """Test playing Item cards"""
    # Create Item
    item_ability = Ability("Potion Effect", "Heal 30 damage from 1 of your Pokémon.", 
                          Ability.Target.PLAYER_ACTIVE, Card.Position.ACTIVE)
    item = Item("item-001", "Potion", Card.Type.TRAINER, Card.Subtype.ITEM, 
               "Set", "Pack", "Common", ability=item_ability)
    
    # Create deck with Basic Pokemon
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    deck = [basic] * 19 + [item]
    
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player.set_active_pokemon(card)
            player.cards_in_hand.remove(card)
            break
    
    # Add item to hand if not there
    if item not in player.cards_in_hand:
        player.cards_in_hand.append(item)
    
    # Damage Pokemon
    player.active_pokemon.damage_taken = 30
    
    # Test play item
    action = PlayItemAction(item.id)
    engine = BattleEngine(player, player, debug=False)
    
    is_valid, error = action.validate(player, engine)
    assert is_valid, error
    
    action.execute(player, engine)
    
    # Verify item was discarded
    assert item in player.discard_pile, "Item should be in discard pile"
    assert item not in player.cards_in_hand, "Item should not be in hand"
    
    print("✓ Play Item tests passed")
    return True

def test_play_supporter():
    """Test playing Supporter cards (one per turn limit)"""
    # Create Supporter
    supporter_ability = Ability("Professor's Research Effect", "Discard your hand, then draw 7 cards.", 
                               Ability.Target.PLAYER_ACTIVE, Card.Position.ACTIVE)
    supporter = Supporter("supporter-001", "Professor's Research", Card.Type.TRAINER, Card.Subtype.SUPPORTER,
                         "Set", "Pack", "Uncommon", ability=supporter_ability)
    
    # Create deck
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    deck = [basic] * 19 + [supporter]
    
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player.set_active_pokemon(card)
            player.cards_in_hand.remove(card)
            break
    
    # Add supporter to hand if not there
    if supporter not in player.cards_in_hand:
        player.cards_in_hand.append(supporter)
    
    # Test play supporter
    action = PlaySupporterAction(supporter.id)
    engine = BattleEngine(player, player, debug=False)
    
    is_valid, error = action.validate(player, engine)
    assert is_valid, error
    
    action.execute(player, engine)
    
    # Verify supporter was discarded and flag set
    assert supporter in player.discard_pile, "Supporter should be in discard pile"
    assert player.played_supporter_this_turn == True, "Supporter flag should be set"
    
    # Try to play another supporter (should fail)
    supporter2 = Supporter("supporter-002", "Another Supporter", Card.Type.TRAINER, Card.Subtype.SUPPORTER,
                          "Set", "Pack", "Uncommon", ability=supporter_ability)
    player.cards_in_hand.append(supporter2)
    action2 = PlaySupporterAction(supporter2.id)
    is_valid2, error2 = action2.validate(player, engine)
    assert not is_valid2, "Should not be able to play second supporter in same turn"
    
    print("✓ Play Supporter tests passed")
    return True

def test_attach_tool():
    """Test attaching Tool cards"""
    # Create Tool
    tool_ability = Ability("Cape Effect", "The Pokémon this card is attached to takes 20 less damage from attacks.", 
                         Ability.Target.PLAYER_ACTIVE, Card.Position.ACTIVE)
    tool = Tool("tool-001", "Cape", Card.Type.TRAINER, Card.Subtype.TOOL,
               "Set", "Pack", "Uncommon", ability=tool_ability)
    
    # Create deck
    basic = Pokemon("basic-001", "Bulbasaur", Energy.Type.GRASS, Card.Type.POKEMON,
                   Card.Subtype.BASIC, 70, "Set", "Pack", "Common", [], 1, Energy.Type.FIRE, None)
    deck = [basic] * 19 + [tool]
    
    player = Player("Test Player", deck, [Energy.Type.GRASS])
    player.draw_inital_hand()
    
    # Set active Pokemon
    for card in player.cards_in_hand:
        if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
            player.set_active_pokemon(card)
            player.cards_in_hand.remove(card)
            break
    
    # Add tool to hand if not there
    if tool not in player.cards_in_hand:
        player.cards_in_hand.append(tool)
    
    # Test attach tool
    action = AttachToolAction(tool.id, "active")
    engine = BattleEngine(player, player, debug=False)
    
    is_valid, error = action.validate(player, engine)
    assert is_valid, error
    
    action.execute(player, engine)
    
    # Verify tool was attached
    assert player.active_pokemon.poketool == tool, "Tool should be attached to Pokemon"
    assert tool not in player.cards_in_hand, "Tool should not be in hand"
    
    # Try to attach another tool (should fail)
    tool2 = Tool("tool-002", "Another Tool", Card.Type.TRAINER, Card.Subtype.TOOL,
                "Set", "Pack", "Uncommon", ability=tool_ability)
    player.cards_in_hand.append(tool2)
    action2 = AttachToolAction(tool2.id, "active")
    is_valid2, error2 = action2.validate(player, engine)
    assert not is_valid2, "Should not be able to attach second tool to same Pokemon"
    
    print("✓ Attach Tool tests passed")
    return True

def run_all_trainer_tests():
    """Run all trainer card tests"""
    tests = [test_play_item, test_play_supporter, test_attach_tool]
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
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTrainer Card Tests: {passed}/{total} passed")
    return all(results.values())

if __name__ == "__main__":
    success = run_all_trainer_tests()
    exit(0 if success else 1)

