# This is the superclass for all cards
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from .ability import Ability

class Card:

    class Type:
        POKEMON = "Pokemon"
        TRAINER = "Trainer"
    
    class Subtype:
        BASIC = "Basic"
        STAGE_1 = "Stage 1"
        STAGE_2 = "Stage 2"
        STAGE_3 = "Stage 3"
        SUPPORTER = "Supporter"
        TOOL = "Tool"
        ITEM = "Item"

    class Position:
        DECK = "DECK"
        HAND = "HAND" 
        BENCH = "BENCH"
        ACTIVE = "ACTIVE"
        DISCARD = "DISCARD"

    def __init__(self, id: str, name: str, type: Type, subtype: Subtype, set: str, pack: str, rarity: str, image_url: str = None, ability: Optional['Ability'] = None):
        self.id: str = id
        self.name: str = name
        self.type: Card.Type = type
        self.subtype: Card.Subtype = subtype
        self.set: str = set
        self.pack: str = pack
        self.rarity: str = rarity
        self.image_url: str = image_url
        self.ability: Ability = ability
    
        # Lets say we add position to the card
        self.card_position: Card.Position = Card.Position.DECK  # Can be: DECK, HAND, BENCH, ACTIVE, DISCARD
    
    def to_display_string(self) -> str:
        """Base card display representation. Subclasses should override this."""
        return f"{self.name} ({self.subtype})"