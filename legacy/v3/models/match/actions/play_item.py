"""Play Item action - play an Item trainer card"""
from typing import Optional
from .action import Action, ActionType
from v3.models.cards.item import Item
from v3.models.match.effects import EffectParser

class PlayItemAction(Action):
    """Action to play an Item card"""
    
    def __init__(self, item_id: str):
        super().__init__(ActionType.PLAY_ITEM)
        self.item_id = item_id
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if item can be played"""
        item = next((c for c in player.cards_in_hand if c.id == self.item_id), None)
        if not item:
            return False, f"Item {self.item_id} not in hand"
        
        if not isinstance(item, Item):
            return False, f"Card {self.item_id} is not an Item"
        
        if not player.can_play_trainer:
            return False, "Cannot play trainer cards this turn"
        
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        """Execute playing item"""
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: PlayItemAction.execute() called for item_id: {self.item_id}")
        
        item = next((c for c in player.cards_in_hand if c.id == self.item_id), None)
        if not item or not isinstance(item, Item):
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: Item {self.item_id} not found in hand. Hand has {len(player.cards_in_hand)} cards")
            raise ValueError(f"Item {self.item_id} not found")
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Found item: {item.name} (id: {item.id})")
            battle_engine.log(f"DEBUG: Item has ability: {item.ability is not None}")
            if item.ability:
                battle_engine.log(f"DEBUG: Ability name: {item.ability.name if hasattr(item.ability, 'name') else 'N/A'}")
                battle_engine.log(f"DEBUG: Ability effect: {item.ability.effect if hasattr(item.ability, 'effect') else 'N/A'}")
        
        # Remove from hand
        player.cards_in_hand.remove(item)
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Removed {item.name} from hand. Hand size now: {len(player.cards_in_hand)}")
        
        # Execute item effect
        if item.ability and item.ability.effect:
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: Parsing item effect: '{item.ability.effect}'")
            effects = EffectParser.parse_multiple(item.ability.effect)
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: Parsed {len(effects)} effect(s) from item")
                for i, effect in enumerate(effects):
                    battle_engine.log(f"DEBUG: Effect {i+1}: {type(effect).__name__} - {effect}")
            
            for i, effect in enumerate(effects):
                try:
                    if battle_engine.debug:
                        battle_engine.log(f"DEBUG: Executing effect {i+1}/{len(effects)}: {type(effect).__name__}")
                        if hasattr(effect, 'card_type'):
                            battle_engine.log(f"DEBUG: SearchEffect card_type: {effect.card_type}, amount: {effect.amount}")
                    effect.execute(player, battle_engine)
                    if battle_engine.debug:
                        battle_engine.log(f"DEBUG: Effect {i+1} executed successfully")
                except Exception as e:
                    battle_engine.log(f"Error executing item effect: {e}")
                    import traceback
                    if battle_engine.debug:
                        traceback.print_exc()
        else:
            if battle_engine.debug:
                battle_engine.log(f"DEBUG: Item {item.name} has no ability or effect")
                if not item.ability:
                    battle_engine.log(f"DEBUG: Item.ability is None")
                elif not item.ability.effect:
                    battle_engine.log(f"DEBUG: Item.ability.effect is None or empty")
        
        # Discard item
        player.discard_card(item)
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: Discarded {item.name}. Discard pile size: {len(player.discard_pile)}")
        
        battle_engine.log(f"{player.name} played {item.name}")
        
        if battle_engine.debug:
            battle_engine.log(f"DEBUG: PlayItemAction.execute() completed. Hand size: {len(player.cards_in_hand)}")
    
    def to_string(self) -> str:
        return f"play_item_{self.item_id}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'PlayItemAction':
        if not action_str.startswith("play_item_"):
            raise ValueError(f"Invalid action string: {action_str}")
        item_id = action_str.replace("play_item_", "")
        return cls(item_id)

