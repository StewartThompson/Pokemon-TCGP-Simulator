from .json_card_importer import JsonCardImporter
from typing import Optional, Any
import copy

class CardLoader:
    """Loads and manages all cards from the JSON import system for easy deck building."""
    
    def __init__(self):
        self.importer = JsonCardImporter()
        self.importer.import_from_json()
  
    def get_card_by_id(self, card_id: str) -> Optional[Any]:
        """Get any card by its ID, regardless of type."""
        
        if card_id in self.importer.items:
            return copy.deepcopy(self.importer.items[card_id])
        elif card_id in self.importer.pokemon:
            return copy.deepcopy(self.importer.pokemon[card_id])
        elif card_id in self.importer.supporters:
            return copy.deepcopy(self.importer.supporters[card_id])
        elif card_id in self.importer.tools:
            return copy.deepcopy(self.importer.tools[card_id])
        elif card_id in self.importer.fossils:
            return copy.deepcopy(self.importer.fossils[card_id])
        
        return None
    