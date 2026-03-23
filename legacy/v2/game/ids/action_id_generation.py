from typing import Dict, List
import re


# Documentation for the labeling:
# Position: where the card needs to be to use the action (pHand, pActive, pBench1, pBench2, pBench3) 
#           Supporter cards can only be played from your hand so they would be pHand
#           Default is pActive (active pokemon's attacks can only be from active spot)
# Target: where the action is targeting (pActive, pBench1, pBench2, pBench3, pDiscard, oActive, oBench1, oBench2, oBench3, oDiscard)
#           If the action doesn't target anything, it's pActive (active pokemon attacks active pokmeon)

class ActionIdGenerator:
    @staticmethod
    def _to_camel_case(text: str) -> str:
        """Convert text to camelCase, removing all special characters."""
        # Remove all special characters and replace with spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        # Split into words and convert to camelCase
        words = text.split()
        if not words:
            return ""
        # First word lowercase
        result = words[0].lower()
        # Subsequent words capitalized
        for word in words[1:]:
            result += word[0].upper() + word[1:].lower()
        return result

    @staticmethod
    def get_attack_id(card: dict, attack: dict) -> str:
        """Generate a unique ID for an attack action.
        Format: {cardId}_attack_{pokemonName}_{attackName}_{position}_{target}
        """
        position = attack.get("position", "pActive")
        target = attack.get("target", "oActive")
        return f"{card['id']}_attack_{ActionIdGenerator._to_camel_case(card['name'])}_{ActionIdGenerator._to_camel_case(attack['name'])}_{position}_{target}"

    @staticmethod
    def get_ability_id(card: dict, ability: dict) -> str:
        """Generate a unique ID for an ability action.
        Format: {cardId}_ability_{pokemonName}_{abilityName}_{position}_{target}
        """
        position = ability.get("position", "pActive") 
        target = ability.get("target", "oActive")
        return f"{card['id']}_ability_{ActionIdGenerator._to_camel_case(card['name'])}_{ActionIdGenerator._to_camel_case(ability['name'])}_{position}_{target}"

    @staticmethod
    def evolution_ids(card: dict) -> List[str]:
        """Generate the 4 evolution action IDs for a card that can be evolved into.
        Format: {cardId}_evolve_{spot}_{basePokemon}_{evolvedPokemon}
        Returns empty list if card is not evolvable into.
        """
        if not card.get("evolvesFrom"):
            return []
        spots = ["pactive", "pbench1", "pbench2", "pbench3"]
        return [
            f"{card['id']}_evolve_{spot}_{ActionIdGenerator._to_camel_case(card['evolvesFrom'])}_{ActionIdGenerator._to_camel_case(card['name'])}"
            for spot in spots
        ]

    @staticmethod
    def retreat_id(card: dict) -> List[str]:
        """Generate a unique ID for a retreat action.
        Format: {cardId}_retreat_{spot}_{pokemonName}
        """
        spots = ["pbench1", "pbench2", "pbench3"]
        return [
            f"{card['id']}_retreat_{spot}_{ActionIdGenerator._to_camel_case(card['name'])}"
            for spot in spots
        ]

    @staticmethod
    def play_basic_pokemon_ids(card: dict) -> List[str]:
        """Generate the 4 'play basic pokemon' action IDs for a basic pokemon card.
        Format: {cardId}_play_{spot}_{pokemonName}
        Returns empty list if card is not a basic pokemon.
        """
        # Handle both Basic Pokemon and Fossil cards that act as Basic Pokemon
        if card.get("subtype") == "Basic":
            spots = ["pactive", "pbench1", "pbench2", "pbench3"]
        elif card.get("subtype") == "Fossil":
            spots = ["pbench1", "pbench2", "pbench3"]
        else:
            return []
        
        return [
            f"{card['id']}_play_{spot}_{ActionIdGenerator._to_camel_case(card['name'])}"
            for spot in spots
        ]
    
    @staticmethod
    def get_all_action_ids_for_card(card: dict) -> List[str]:
        """Generate all action IDs for a card."""
        ids = []

        # Add play basic pokemon IDs
        # Add evolution trigger IDs 
        if (card.get('type') == 'Pokemon'):
            ids.extend(ActionIdGenerator.play_basic_pokemon_ids(card))
            ids.extend(ActionIdGenerator.evolution_ids(card))

        # Add ability IDs
        for ability in card.get("abilities", []):
            ids.append(ActionIdGenerator.get_ability_id(card, ability))

        # Add attack IDs
        for attack in card.get("attacks", []):
            ids.append(ActionIdGenerator.get_attack_id(card, attack))

        if (card.get('type') == 'Pokemon' and card.get("subtype") != "Fossil"):
            ids.extend(ActionIdGenerator.retreat_id(card))

        return ids
    
    @staticmethod
    def get_default_action_ids() -> List[str]:
        """Generate all action IDs for a player."""
        return [
            "end_turn",
            "pactive_attach_energy",
            "pbench1_attach_energy",
            "pbench2_attach_energy",
            "pbench3_attach_energy"
        ]

        
