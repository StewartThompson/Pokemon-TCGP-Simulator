"""Play Supporter action - play a Supporter trainer card"""
from typing import Optional
from .action import Action, ActionType
from v3.models.cards.supporter import Supporter
from v3.models.match.effects import EffectParser

class PlaySupporterAction(Action):
    """Action to play a Supporter card"""
    
    def __init__(self, supporter_id: str):
        super().__init__(ActionType.PLAY_SUPPORTER)
        self.supporter_id = supporter_id
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if supporter can be played"""
        supporter = next((c for c in player.cards_in_hand if c.id == self.supporter_id), None)
        if not supporter:
            return False, f"Supporter {self.supporter_id} not in hand"
        
        if not isinstance(supporter, Supporter):
            return False, f"Card {self.supporter_id} is not a Supporter"
        
        if hasattr(player, 'played_supporter_this_turn') and player.played_supporter_this_turn:
            return False, "Already played a Supporter this turn"
        
        if not player.can_play_trainer:
            return False, "Cannot play trainer cards this turn"
        
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        """Execute playing supporter"""
        supporter = next((c for c in player.cards_in_hand if c.id == self.supporter_id), None)
        if not supporter or not isinstance(supporter, Supporter):
            raise ValueError(f"Supporter {self.supporter_id} not found")
        
        # Remove from hand
        player.cards_in_hand.remove(supporter)
        
        # Mark supporter as played
        if not hasattr(player, 'played_supporter_this_turn'):
            player.played_supporter_this_turn = False
        player.played_supporter_this_turn = True
        
        # Execute supporter effect
        if supporter.ability and supporter.ability.effect:
            effects = EffectParser.parse_multiple(supporter.ability.effect)
            for effect in effects:
                try:
                    effect.execute(player, battle_engine)
                except Exception as e:
                    battle_engine.log(f"Error executing supporter effect: {e}")
                    import traceback
                    if battle_engine.debug:
                        traceback.print_exc()
        
        # Discard supporter
        player.discard_card(supporter)
        
        battle_engine.log(f"{player.name} played {supporter.name}")
    
    def to_string(self) -> str:
        return f"play_supporter_{self.supporter_id}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'PlaySupporterAction':
        if not action_str.startswith("play_supporter_"):
            raise ValueError(f"Invalid action string: {action_str}")
        supporter_id = action_str.replace("play_supporter_", "")
        return cls(supporter_id)

