"""Discard action - discard a card from hand"""
from typing import Optional
from .action import Action, ActionType

class DiscardAction(Action):
    """Action to discard a card from hand"""
    
    def __init__(self, card_index: int):
        super().__init__(ActionType.END_TURN)  # Reuse END_TURN type for now
        self.card_index = card_index
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if discard can be performed"""
        if self.card_index < 0 or self.card_index >= len(player.cards_in_hand):
            return False, f"Invalid card index: {self.card_index}"
        
        # Discard is always valid (no hand size limit - used for effects that require discarding)
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        if self.card_index < len(player.cards_in_hand):
            card = player.cards_in_hand.pop(self.card_index)
            player.discard_card(card)
            battle_engine.log(f"{player.name} discarded {card.name}")
    
    def to_string(self) -> str:
        return f"discard_{self.card_index}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'DiscardAction':
        if not action_str.startswith("discard_"):
            raise ValueError(f"Invalid action string: {action_str}")
        try:
            card_index = int(action_str.split("_")[1])
            return cls(card_index)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid discard action format: {action_str}")

