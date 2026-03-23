"""
Base class for all deck configurations.
Handles card loading so individual deck files stay clean.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from import_files.card_loader import CardLoader

class BaseDeck:
    """Base class for all deck configurations"""
    
    def __init__(self):
        self.card_loader = CardLoader()
    
    def get_card_by_id(self, card_id: str):
        """Get a card by its ID"""
        return self.card_loader.get_card_by_id(card_id)
    
    def get_deck(self):
        """Override this method in subclasses to define deck contents"""
        raise NotImplementedError("Subclasses must implement get_deck()")
    
    def get_description(self):
        """Override this method in subclasses to provide deck description"""
        return {"name": "Unknown Deck", "type": "Unknown", "strategy": "No description provided"} 