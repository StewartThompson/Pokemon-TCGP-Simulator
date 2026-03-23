"""
Deck loader for Pokemon TCG Pocket Battle Simulator.
Dynamically loads deck configurations by name from the decks directory.
"""

import os
import sys
import importlib
from typing import List, Optional

class DeckLoader:
    """Class to load deck configurations by name"""
    
    def __init__(self):
        # Add the parent directory to Python path if not already there
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
    
    def load_deck_by_name(self, deck_name: str) -> Optional[List]:
        """Load a deck by its module name from the decks directory"""
        try:
            # Clear any existing deck module to force reload
            module_name = f"decks.{deck_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Import the deck module
            module = importlib.import_module(module_name)
            
            # Find the deck class in the module
            deck_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    hasattr(obj, 'get_deck') and 
                    hasattr(obj, 'get_description') and
                    name != 'BaseDeck'):
                    deck_class = obj
                    break
            
            if deck_class is None:
                return None
                
            # Create instance and get the deck
            deck_instance = deck_class()
            return deck_instance.get_deck(), deck_instance.get_type()
            
        except Exception as e:
            print(f"Error loading deck {deck_name}: {e}")
            return None

    def list_available_decks(self) -> List[str]:
        """List all available deck files in the decks directory"""
        try:
            # Get the decks directory path
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            decks_dir = os.path.join(parent_dir, "decks")
            
            if not os.path.exists(decks_dir):
                return []
            
            # Find all Python files (excluding __init__.py and base_deck.py)
            deck_files = []
            for filename in os.listdir(decks_dir):
                if filename.endswith(".py") and filename not in ["__init__.py", "base_deck.py"]:
                    deck_name = filename[:-3]  # Remove .py extension
                    deck_files.append(deck_name)
                    
            return sorted(deck_files)
            
        except Exception:
            return []
