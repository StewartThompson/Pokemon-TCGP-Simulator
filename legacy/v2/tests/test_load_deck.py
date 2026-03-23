#!/usr/bin/env python3
"""
Test suite for load_deck.py
"""

import os
import sys
import unittest

# Add the v2 directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from game.load_deck import DeckLoader

class TestLoadDeck(unittest.TestCase):
    """Test load_deck functionality"""
    
    def setUp(self):
        self.deck_loader = DeckLoader()
    
    def test_list_available_decks(self):
        """Test listing available decks"""
        decks = self.deck_loader.list_available_decks()
        self.assertIsInstance(decks, list)
        # Should find at least the basic decks
        self.assertTrue(len(decks) > 0)
        # Should contain basic_grass_deck
        self.assertIn('basic_grass_deck', decks)
    
    def test_load_valid_deck(self):
        """Test loading a valid deck"""
        deck = self.deck_loader.load_deck_by_name('basic_grass_deck')
        self.assertIsNotNone(deck)
        self.assertIsInstance(deck, list)
        self.assertEqual(len(deck), 20)  # Should have 20 cards
        
        # Verify cards have required attributes
        for card in deck:
            self.assertTrue(hasattr(card, 'name'))
            self.assertTrue(hasattr(card, 'id'))
    
    def test_load_invalid_deck(self):
        """Test loading a non-existent deck"""
        deck = self.deck_loader.load_deck_by_name('nonexistent_deck')
        self.assertIsNone(deck)
    
    def test_load_empty_deck_name(self):
        """Test loading with empty deck name"""
        deck = self.deck_loader.load_deck_by_name('')
        self.assertIsNone(deck)

if __name__ == "__main__":
    unittest.main() 