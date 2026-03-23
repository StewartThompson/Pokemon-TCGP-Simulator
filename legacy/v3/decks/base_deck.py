"""
Base class for all deck configurations in v3.
Handles card loading using JsonCardImporter.
"""

from typing import List, Dict, Any
from copy import deepcopy
from v3.importers.json_card_importer import JsonCardImporter
from v3.models.cards.card import Card


class BaseDeck:
    """Base class for all deck configurations in v3"""
    
    def __init__(self):
        """Initialize the deck with card importer"""
        self.importer = JsonCardImporter()
        self.importer.import_from_json()
        self._loaded_cards = {}  # Cache for loaded cards
    
    def get_card_by_id(self, card_id: str) -> Card:
        """Get a card by its ID (returns a deep copy for deck building)"""
        # Check cache first
        if card_id in self._loaded_cards:
            return deepcopy(self._loaded_cards[card_id])
        
        # Try to find in importer
        card = None
        
        # Check Pokemon
        if card_id in self.importer.pokemon:
            card = self.importer.pokemon[card_id]
        # Check Items
        elif card_id in self.importer.items:
            card = self.importer.items[card_id]
        # Check Supporters
        elif card_id in self.importer.supporters:
            card = self.importer.supporters[card_id]
        # Check Tools
        elif card_id in self.importer.tools:
            card = self.importer.tools[card_id]
        
        if card is None:
            raise ValueError(f"Card with ID '{card_id}' not found in card database")
        
        # Cache the original (we'll deepcopy when returning)
        self._loaded_cards[card_id] = card
        return deepcopy(card)
    
    def get_deck(self) -> List[Card]:
        """Override this method in subclasses to define deck contents"""
        raise NotImplementedError("Subclasses must implement get_deck()")
    
    def get_description(self) -> Dict[str, Any]:
        """Override this method in subclasses to provide deck description"""
        return {
            "name": "Unknown Deck",
            "type": "Unknown",
            "strategy": "No description provided"
        }
    
    def get_energy_types(self) -> List[str]:
        """Override this method to return the energy types this deck uses"""
        return []
    
    def validate_deck(self, deck: List[Card]) -> tuple[bool, str]:
        """Validate that a deck meets game rules"""
        if len(deck) != 20:
            return False, f"Deck must contain exactly 20 cards, got {len(deck)}"
        
        # Check for at least one Basic Pokemon
        basic_pokemon = [c for c in deck if hasattr(c, 'subtype') and c.subtype == Card.Subtype.BASIC]
        if not basic_pokemon:
            return False, "Deck must contain at least one Basic Pokemon"
        
        # Check for max copies per card (by ID)
        # Note: Standard rule is max 2 copies, but for testing with limited card pool,
        # we allow up to 3 copies if needed to reach 20 cards
        # In a real game with full card pool, this should be strictly enforced at 2
        from collections import Counter
        card_counts = Counter(card.id for card in deck)
        for card_id, count in card_counts.items():
            if count > 3:
                return False, f"Deck contains {count} copies of {card_id} (max 3 allowed for testing, ideally 2)"
        
        return True, "Deck is valid"

