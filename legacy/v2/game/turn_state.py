from typing import Tuple

class TurnState:
    """Manages state that persists during a single turn."""
    
    def __init__(self):
        self.has_attached_energy = False
        self.has_played_supporter = False
        self.has_attacked = False
        self.retreat_cost_reduction = 0
        self.bonus_damage_effect = (0, None)
        self.evolved_pokemon_this_turn = []  # Track Pokemon that evolved this turn
    
    def reset(self, is_first_turn=False):
        """Reset turn state for a new turn."""
        self.has_attached_energy = False
        self.has_played_supporter = False
        self.has_attacked = False
        self.retreat_cost_reduction = 0
        self.bonus_damage_effect = (0, None)
        self.evolved_pokemon_this_turn = []  # Clear evolved Pokemon tracking 