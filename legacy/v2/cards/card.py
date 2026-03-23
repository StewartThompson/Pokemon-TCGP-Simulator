# This is the superclass for all cards

class Card:
    class Position:
        DECK = "DECK"
        HAND = "HAND" 
        BENCH = "BENCH"
        ACTIVE = "ACTIVE"
        DISCARD = "DISCARD"

    def __init__(self, id, name, type, subtype, set, pack, rarity, action_ids):
        self.id = id
        self.name = name
        self.type = type
        self.subtype = subtype
        self.set = set
        self.pack = pack
        self.rarity = rarity
        self.action_ids = action_ids if action_ids is not None else []
    
        # Lets say we add position to the card
        self.card_position = Card.Position.DECK  # Can be: DECK, HAND, BENCH, ACTIVE, DISCARD