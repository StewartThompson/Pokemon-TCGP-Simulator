from .base_deck import BaseDeck

class BasicLightningDeck(BaseDeck):
    """Basic Lightning Pokemon deck (20 cards)"""
    
    def get_deck(self):
        """Returns a basic lightning deck (20 cards)"""
        
        # Build deck with electric Pokemon
        deck = [
             # Erika x2
            self.get_card_by_id('a1-219'),
            self.get_card_by_id('a1-219'),

            # Bulbasaur x2
            self.get_card_by_id('a1-001'),
            self.get_card_by_id('a1-001'),
            
            # Ivysaur x2
            self.get_card_by_id('a1-002'),
            self.get_card_by_id('a1-002'),

            # Venusaur ex x1
            self.get_card_by_id('a1-004'),
            self.get_card_by_id('a1-004'),
            
            # Weedle x2
            self.get_card_by_id('a1-008'),
            self.get_card_by_id('a1-008'),
            
            # Kakuna x2
            self.get_card_by_id('a1-009'),
            self.get_card_by_id('a1-009'),
            
            # Giovanni x2
            self.get_card_by_id('a1-223'),
            self.get_card_by_id('a1-223'),
            
            # Sabrina x2
            self.get_card_by_id('a1-225'),
            self.get_card_by_id('a1-225'),
            
            # Paras x2
            self.get_card_by_id('a1-014'),
            self.get_card_by_id('a1-014'),
            
            # Parasect x2
            self.get_card_by_id('a1-015'),
            self.get_card_by_id('a1-015'),
        ]
        
        # Remove any None values (in case some cards weren't found)
        deck = [card for card in deck if card is not None]
        
        return deck

    def get_description(self):
        """Returns a description of the deck"""
        return {
            "name": "Basic Lightning Deck",
            "type": "Electric",
            "strategy": "Fast electric deck with lightning Pokemon"
        } 
    def get_type(self):
        """Returns the type of the deck"""
        return ["Lightning"]