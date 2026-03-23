# This is the item card class; for example Poké Ball, Potion, Red Card, etc.
from .card import Card

class Item(Card):
    def __init__(self, id, name, type, subtype, set, pack, rarity, abilities, action_ids):
        # Call the parent Card constructor
        super().__init__(id, name, type, subtype, set, pack, rarity, action_ids)
        
        # If abilities exist, set the first one as the main ability
        if abilities:
            self.ability = abilities[0]

    def __str__(self):
        return f"{self.name}"
    
    def _get_actions(self, player, opponent_pokemon_locations):
        """Get all possible actions for the Item"""

        available_actions = []

        return available_actions