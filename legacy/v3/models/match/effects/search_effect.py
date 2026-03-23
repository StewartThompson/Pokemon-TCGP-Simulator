"""Search effect - searches deck for cards"""
import re
import random
from typing import Optional, TYPE_CHECKING
from .effect import Effect
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.energy import Energy
from v3.models.cards.card import Card

if TYPE_CHECKING:
    from v3.models.match.player import Player
    from v3.models.match.battle_engine import BattleEngine

class SearchEffect(Effect):
    """Search deck for cards"""
    
    def __init__(self, card_type: str, element: Optional[Energy.Type] = None, amount: int = 1):
        self.card_type = card_type  # "Pokemon", "Energy", etc.
        self.element = element
        self.amount = amount
    
    def execute(self, player, battle_engine, source=None):
        found = []
        battle_engine.log(f"Searching deck for {self.amount} {self.card_type}...")
        battle_engine.log(f"Deck size: {len(player.deck)}")
        
        for card in player.deck:
            if self.card_type == "BasicPokemon" and isinstance(card, Pokemon):
                # Only Basic Pokemon
                if hasattr(card, 'subtype') and card.subtype == Card.Subtype.BASIC:
                    if self.element is None or card.element == self.element:
                        found.append(card)
                        if battle_engine.debug:
                            battle_engine.log(f"  Found Basic Pokemon: {card.name} (subtype: {card.subtype})")
            elif self.card_type == "Pokemon" and isinstance(card, Pokemon):
                # Any Pokemon (can filter by element)
                if self.element is None or card.element == self.element:
                    found.append(card)
                    if battle_engine.debug:
                        battle_engine.log(f"  Found Pokemon: {card.name}")
        
        battle_engine.log(f"Found {len(found)} matching cards in deck")
        
        # Take random cards up to amount
        if found:
            to_take = min(self.amount, len(found))
            selected = random.sample(found, to_take)
            for card in selected:
                player.deck.remove(card)
                player.cards_in_hand.append(card)
                card.card_position = Card.Position.HAND
                battle_engine.log(f"Added {card.name} to {player.name}'s hand")
            battle_engine.log(f"Put {len(selected)} {self.card_type} into hand (hand size: {len(player.cards_in_hand)})")
            # No hand size limit - players can have any number of cards in hand
        else:
            battle_engine.log(f"No matching {self.card_type} found in deck")
    
    @classmethod
    def from_text(cls, effect_text: str) -> Optional['SearchEffect']:
        """Parse search effect from text"""
        text_lower = effect_text.lower()
        
        # Pattern for "Draw 1 basic Pokémon card." or "Draw 1 basic Pokemon card."
        basic_pattern = r'draw\s+(\d+)\s+basic\s+pok[ée]mon\s+card'
        match = re.search(basic_pattern, text_lower)
        if match:
            amount = int(match.group(1))
            # Return SearchEffect that only searches for Basic Pokemon
            effect = cls("BasicPokemon", None, amount)
            # Debug logging will be done in execute() method
            return effect
        
        # Pattern: "Put 1 random Grass Pokémon from your deck into your hand."
        # Also handle: "Put 1 random Grass Pokemon from your deck into your hand."
        pattern = r'put\s+(\d+)\s+(?:random\s+)?(\w+)\s+pok[ée]mon\s+from\s+your\s+deck\s+into\s+your\s+hand'
        match = re.search(pattern, text_lower)
        if match:
            amount = int(match.group(1))
            element_str = match.group(2)
            
            # Map string to Energy.Type (same as Energy.from_string_list)
            energy_map = {
                'FIRE': Energy.Type.FIRE,
                'WATER': Energy.Type.WATER,
                'ROCK': Energy.Type.ROCK,
                'GRASS': Energy.Type.GRASS,
                'NORMAL': Energy.Type.NORMAL,
                'COLORLESS': Energy.Type.NORMAL,
                'ELECTRIC': Energy.Type.ELECTRIC,
                'PSYCHIC': Energy.Type.PSYCHIC,
                'DARK': Energy.Type.DARK,
                'DARKNESS': Energy.Type.DARK,
                'METAL': Energy.Type.METAL,
            }
            
            element = energy_map.get(element_str.upper())
            return cls("Pokemon", element, amount)
        return None

