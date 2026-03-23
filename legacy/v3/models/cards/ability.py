from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .card import Card

# These are the abilities that a pokemon can use
class Ability:
    class Target:
        PLAYER_ACTIVE = "pactive"
        PLAYER_BENCH = "pbench"
        PLAYER_ALL = "pall"
        OPPONENT_ACTIVE = "oactive"
        OPPONENT_BENCH = "obench"
        OPPONENT_ALL = "oall"
        OPPONENT_ALL = "oall"
        ALL = "all"
    
    # Position will be defined when Card is imported
    class Position:
        DECK = "DECK"
        HAND = "HAND" 
        BENCH = "BENCH"
        ACTIVE = "ACTIVE"
        DISCARD = "DISCARD"

    def __init__(self, name: str, effect: str, target : Target, position):
        self.name: str = name
        self.effect: str = effect
        self.target: Ability.Target = target
        self.position = position  # Will be Card.Position when used