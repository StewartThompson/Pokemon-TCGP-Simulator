from typing import Optional
from .action import Action, ActionType

class AttackAction(Action):
    """Action to attack with active Pokemon"""
    
    def __init__(self, attack_index: int):
        super().__init__(ActionType.ATTACK)
        self.attack_index = attack_index
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if attack can be executed"""
        if not player.active_pokemon:
            return False, "No active Pokemon"
        
        # Check if player can attack (may be prevented by effects like Tail Whip)
        if hasattr(player, 'can_attack_next_turn') and not player.can_attack_next_turn:
            return False, "Cannot attack this turn (prevented by opponent's effect)"
        
        if player.active_pokemon.attacked_this_turn:
            return False, "Pokemon has already attacked this turn"
        
        if self.attack_index >= len(player.active_pokemon.attacks):
            return False, f"Invalid attack index: {self.attack_index}"
        
        attack = player.active_pokemon.attacks[self.attack_index]
        if not player.active_pokemon._can_afford_attack(attack):
            return False, "Cannot afford attack energy cost"
        
        # Check if opponent has an active Pokemon to attack
        opponent = battle_engine._get_opponent(player)
        if not opponent.active_pokemon:
            return False, "No opponent Pokemon to attack"
        
        return True, None
    
    def execute(self, player, battle_engine) -> None:
        """Execute attack"""
        attacker = player.active_pokemon
        opponent = battle_engine._get_opponent(player)
        defender = opponent.active_pokemon
        
        if not defender:
            battle_engine.log("No opponent Pokemon to attack")
            return
        
        attack = attacker.attacks[self.attack_index]
        battle_engine._execute_attack(attacker, attack, player, opponent)
    
    def to_string(self) -> str:
        return f"attack_{self.attack_index}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'AttackAction':
        if not action_str.startswith("attack_"):
            raise ValueError(f"Invalid action string: {action_str}")
        try:
            attack_index = int(action_str.split("_")[1])
            return cls(attack_index)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid attack index in: {action_str}")

