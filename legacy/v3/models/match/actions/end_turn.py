from typing import Optional
from .action import Action, ActionType

class EndTurnAction(Action):
    """Action to end the current turn"""
    
    def __init__(self):
        super().__init__(ActionType.END_TURN)
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """End turn is always valid"""
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        """End turn - actual cleanup happens in battle engine"""
        battle_engine.log(f"{player.name} ends their turn")
    
    def to_string(self) -> str:
        return "end_turn"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'EndTurnAction':
        if action_str != "end_turn":
            raise ValueError(f"Invalid action string: {action_str}")
        return cls()

