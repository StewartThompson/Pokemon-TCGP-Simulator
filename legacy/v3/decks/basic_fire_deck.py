"""
Basic Fire Pokemon deck for v3
Uses only cards available in the current card database
"""

from typing import List, Dict, Any
from copy import deepcopy
from .base_deck import BaseDeck
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy


class BasicFireDeck(BaseDeck):
    """Basic Fire Pokemon deck (20 cards)"""
    
    def get_deck(self) -> List[Card]:
        """Returns a basic deck (20 cards)"""
        
        deck = []
        
        # Vulpix x2 (Basic)
        deck.append(self.get_card_by_id('a1-037'))
        deck.append(self.get_card_by_id('a1-037'))
        
        # Ninetales x2 (Stage 1)
        deck.append(self.get_card_by_id('a1-038'))
        deck.append(self.get_card_by_id('a1-038'))
        
        # Charmander x2 (Basic)
        deck.append(self.get_card_by_id('a1-230'))
        deck.append(self.get_card_by_id('a1-230'))
        
        # Charizard ex x2 (Stage 2)
        deck.append(self.get_card_by_id('a2b-010'))
        deck.append(self.get_card_by_id('a2b-010'))
        
        # Rare Candy to evolve a pokemon
        deck.append(self.get_card_by_id('a3-144'))
        deck.append(self.get_card_by_id('a3-144'))
        
        # Sabrina to switch out an opponent's active pokemon to the bench
        deck.append(self.get_card_by_id('a1-272'))
        deck.append(self.get_card_by_id('a1-272'))
        
        # Health Potion to heal 20 damage from a pokemon
        deck.append(self.get_card_by_id('pa-001'))
        deck.append(self.get_card_by_id('pa-001'))

        # Professor's Research to draw 2 cards
        deck.append(self.get_card_by_id('pa-007'))
        deck.append(self.get_card_by_id('pa-007'))

        # Giant Cape to reduce damage taken by 20
        deck.append(self.get_card_by_id('a2-147'))
        deck.append(self.get_card_by_id('a2-147'))
        
        # Add 2 more cards to reach 20 (Poké Ball)
        deck.append(self.get_card_by_id('pa-005'))
        deck.append(self.get_card_by_id('pa-005'))

        # Validate deck
        is_valid, error = self.validate_deck(deck)
        if not is_valid:
            raise ValueError(f"Invalid deck: {error}")
        
        return deck
    
    def get_description(self) -> Dict[str, Any]:
        """Returns a description of the deck"""
        return {
            "name": "Basic Fire Deck",
            "type": "Fire",
            "strategy": "Fire Pokemon focused deck with evolution chains. Features Vulpix, Ninetales, Charmander, and Charizard ex.",
            "cards": 20
        }
    
    def get_energy_types(self) -> List[str]:
        """Returns the energy types this deck uses"""
        return ["Fire"]
