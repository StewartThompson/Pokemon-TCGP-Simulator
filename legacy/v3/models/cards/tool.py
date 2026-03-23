# This is the tool card class; for example, the Cape, Poison Barb, etc.
from .card import Card
from .ability import Ability

class Tool(Card):
    def __init__(self, id: str, name: str, type: Card.Type, subtype: Card.Subtype, set: str, pack: str, rarity: str, image_url: str = None, ability: Ability = None):
        # Call the parent Card constructor
        super().__init__(id, name, type, subtype, set, pack, rarity, image_url, ability)
    
    def to_display_string(self) -> str:
        """Generate a string representation of the Tool for display."""
        display = f"{self.name} (Tool)"
        if self.ability:
            display += f"\nEffect: {self.ability.effect}"
        return display
        