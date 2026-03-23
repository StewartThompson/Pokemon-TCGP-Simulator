"""
Basic Grass Pokemon deck for v3
Uses only cards available in the current card database
"""

from typing import List, Dict, Any
from copy import deepcopy
from .base_deck import BaseDeck
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy


class BasicGrassDeck(BaseDeck):
    """Basic Grass Pokemon deck (20 cards)"""
    
    def get_deck(self) -> List[Card]:
        """Returns a Grass Pokemon deck (20 cards) using available cards"""
        
        deck = []
        
        # Build deck with available Grass Pokemon
        # Using only cards that exist in the current database
        
        # Bulbasaur x2 (Basic)
        deck.append(self.get_card_by_id('a1-001'))
        deck.append(self.get_card_by_id('a1-001'))
        
        # Ivysaur x2 (Stage 1 - evolves from Bulbasaur)
        deck.append(self.get_card_by_id('a1-002'))
        deck.append(self.get_card_by_id('a1-002'))
        
        # Venusaur ex x2 (Stage 2 - evolves from Ivysaur)
        deck.append(self.get_card_by_id('a1-004'))
        deck.append(self.get_card_by_id('a1-004'))

        # Petilil x2 (Basic)
        deck.append(self.get_card_by_id('a1-029'))
        deck.append(self.get_card_by_id('a1-029'))

        # Lilligant x2 (Stage 1 - evolves from Petilil)
        deck.append(self.get_card_by_id('a1-030'))
        deck.append(self.get_card_by_id('a1-030'))
        
        # Pokeball to draw basic pokemon
        deck.append(self.get_card_by_id('pa-005')) 
        deck.append(self.get_card_by_id('pa-005')) 

        # Health Potion to heal 20 damage from a pokemon
        deck.append(self.get_card_by_id('pa-001'))
        deck.append(self.get_card_by_id('pa-001'))

        # Professor's Research to draw 2 cards
        deck.append(self.get_card_by_id('pa-007'))
        deck.append(self.get_card_by_id('pa-007'))

        # Giant Cape to reduce damage taken by 20
        deck.append(self.get_card_by_id('a2-147'))
        deck.append(self.get_card_by_id('a2-147'))

        # Erika to heal 50 damage to grass pokemon
        deck.append(self.get_card_by_id('a1-219'))
        deck.append(self.get_card_by_id('a1-219'))
        
        # Validate deck
        is_valid, error = self.validate_deck(deck)
        if not is_valid:
            raise ValueError(f"Invalid deck: {error}")
        
        return deck
    
    def get_description(self) -> Dict[str, Any]:
        """Returns a description of the deck"""
        return {
            "name": "Basic Grass Deck",
            "type": "Grass",
            "strategy": "Grass Pokemon focused deck with evolution chains. Features Bulbasaur, Caterpie, and Weedle evolution lines.",
            "cards": 20,
            "basic_pokemon": 6,
            "stage1_pokemon": 6,
            "stage2_pokemon": 6
        }
    
    def get_energy_types(self) -> List[str]:
        """Returns the energy types this deck uses"""
        return ["Grass"]  # Normal for Colorless costs

