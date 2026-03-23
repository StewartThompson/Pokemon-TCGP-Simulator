from v3.models.agents.random_agent import RandomAgent

import random
from typing import Optional, List
from v3.models.agents.random_agent import RandomAgent as BotRandomAgent
from v3.models.agents.agent import Agent
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.match.energy_zone import EnergyZone

class Player:
    def __init__(self, name: str, deck: list[Card], chosen_energies: list[Energy.Type], agent: Agent = None):
        self.name: str = name # Name of the player
        self.deck: list[Card] = deck # Original deck that the player has
        
        # Validate that chosen_energies is provided and not empty
        if not chosen_energies or len(chosen_energies) == 0:
            raise ValueError("chosen_energies must be provided and contain at least one energy type")
        
        self.chosen_energies: list[Energy.Type] = chosen_energies # Chosen energies for the player
        self.agent: Agent = agent(self) if agent else BotRandomAgent(self) # Controls the player's actions

        # These values are game values for the player
        self.points: int = 0
        
        # Note: Colorless energy requirements can be fulfilled by ANY energy type
        # So we don't need to add Normal/Colorless to the energy zone
        # The energy zone should only contain the energy types specified by the deck
        self.energy_zone = EnergyZone(chosen_energies)

        # Tracking the player's cards
        self.cards_in_hand: list[Card] = []
        self.active_pokemon: Pokemon = None
        self.bench_pokemons: list[Pokemon] = [None, None, None]
        self.discard_pile: list[Card] = []
        
        # Additional game values to track statuses
        self.can_play_trainer = True
        self.played_supporter_this_turn: bool = False
        self.attached_energy_this_turn: bool = False  # Limit: 1 energy per turn
        self.played_pokemon_this_turn: bool = False  # Limit: 1 Pokemon per turn
        self.used_rare_candy_this_turn: bool = False  # Track Rare Candy usage
        self.can_attack_next_turn: bool = True  # Can be set to False by effects like Tail Whip

        # Methods to be called at the start of the game
        self._initialize_deck(deck)
        self._add_energies_to_energy_zone()

    # Draws inital hand and checks for basic pokemon
    def draw_inital_hand(self):
        while True:
            self._shuffle_deck()
            self.draw(5)
            if self._check_for_basic_pokemon(self.cards_in_hand) == True:
                return
            else:
                # If no basic pokemon is drawn, reset the deck and draw again
                self.put_cards_back_in_deck()

    def can_draw(self):
        """Check if player can draw (only requires deck to have cards)"""
        return len(self.deck) > 0

    def draw(self, n):
        for _ in range(int(n)):
            if not self.can_draw():
                raise ValueError("Check if can draw before drawing")
            
            card = self.deck.pop(0)
            card.card_position = Card.Position.HAND
            self.cards_in_hand.append(card)
    
    def put_cards_back_in_deck(self):
        for card in self.cards_in_hand:
            card.card_position = Card.Position.DECK
        self.deck = self.deck + self.cards_in_hand
        self.cards_in_hand = []
    
    def _get_turn_zero_actions(self) -> List[str]:
        """Get actions available during turn zero (only play Basic Pokemon)"""
        actions = []
        
        # Can only play Basic Pokemon
        for card in self.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                # Can play to active if empty
                if self.active_pokemon is None:
                    actions.append(f"play_pokemon_{card.id}_active")
                
                # Can play to bench if slots available (will auto-fill from 0, 1, 2)
                if any(bench_pokemon is None for bench_pokemon in self.bench_pokemons):
                    actions.append(f"play_pokemon_{card.id}_bench")
        
        # Can always end turn
        actions.append("end_turn")
        
        return actions
    
    def _get_actions(self, opponent_pokemon_locations: List[int] = None) -> List[str]:
        """Get all valid actions for current turn"""
        actions = []
        
        # Play Pokemon
        actions.extend(self._get_play_pokemon_actions())
        
        # Attach Energy
        actions.extend(self._get_attach_energy_actions())
        
        # Evolve
        actions.extend(self._get_evolve_actions())
        
        # Retreat
        actions.extend(self._get_retreat_actions())
        
        # Play Trainers
        actions.extend(self._get_play_item_actions())
        actions.extend(self._get_play_supporter_actions())
        actions.extend(self._get_attach_tool_actions())
        
        # Use Abilities
        actions.extend(self._get_use_ability_actions())
        
        # Attack
        actions.extend(self._get_attack_actions())
        
        # End Turn
        actions.append("end_turn")
        
        return actions
    
    def _get_play_pokemon_actions(self) -> List[str]:
        """Get actions to play Pokemon from hand"""
        actions = []
        for card in self.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                if self.active_pokemon is None:
                    actions.append(f"play_pokemon_{card.id}_active")
                # Check if there's any empty bench slot (will auto-fill from 0, 1, 2)
                if any(bench_pokemon is None for bench_pokemon in self.bench_pokemons):
                    actions.append(f"play_pokemon_{card.id}_bench")
        return actions
    
    def _get_attach_energy_actions(self) -> List[str]:
        """Get actions to attach energy"""
        actions = []
        if self.energy_zone.has_energy():
            if self.active_pokemon:
                actions.append("attach_energy_active")
            for i, bench_pokemon in enumerate(self.bench_pokemons):
                if bench_pokemon:
                    actions.append(f"attach_energy_bench_{i}")
        return actions
    
    def _get_attack_actions(self) -> List[str]:
        """Get actions to attack"""
        actions = []
        if self.active_pokemon:
            # Get all attacks and check which ones are possible
            for i, attack in enumerate(self.active_pokemon.attacks):
                if self.active_pokemon._can_afford_attack(attack):
                    actions.append(f"attack_{i}")
        return actions
    
    def _get_evolve_actions(self) -> List[str]:
        """Get actions to evolve Pokemon"""
        actions = []
        from v3.models.match.game_rules import GameRules
        
        for card in self.cards_in_hand:
            if isinstance(card, Pokemon):
                # Check if can evolve active
                if self.active_pokemon and GameRules.can_evolve(self.active_pokemon, card):
                    if self.active_pokemon.turns_in_play >= 1:
                        actions.append(f"evolve_{card.id}_active")
                
                # Check if can evolve bench Pokemon
                for i, bench_pokemon in enumerate(self.bench_pokemons):
                    if bench_pokemon and GameRules.can_evolve(bench_pokemon, card):
                        if bench_pokemon.turns_in_play >= 1:
                            actions.append(f"evolve_{card.id}_bench_{i}")
        return actions
    
    def _get_retreat_actions(self) -> List[str]:
        """Get actions to retreat active Pokemon"""
        actions = []
        if self.active_pokemon and self.active_pokemon.can_retreat():
            retreat_cost = self.active_pokemon.retreat_cost
            total_energy = sum(self.active_pokemon.equipped_energies.values())
            
            if total_energy >= retreat_cost:
                # Find empty bench slots
                for i, bench_pokemon in enumerate(self.bench_pokemons):
                    if bench_pokemon is None:
                        actions.append(f"retreat_{i}")
        return actions
    
    def _get_discard_actions(self) -> List[str]:
        """Get actions to discard cards (for voluntary discards from effects)"""
        actions = []
        # Return actions to discard each card (for effects that require discarding)
        for i, card in enumerate(self.cards_in_hand):
            actions.append(f"discard_{i}")
        return actions
    
    def _get_play_item_actions(self) -> List[str]:
        """Get actions to play Item cards"""
        actions = []
        from v3.models.cards.item import Item
        from v3.models.match.effects import EffectParser
        from v3.models.match.effects.heal_effect import HealEffect
        from v3.models.match.effects.heal_all_effect import HealAllEffect
        
        if self.can_play_trainer:
            for card in self.cards_in_hand:
                if isinstance(card, Item):
                    # Check if this is a healing item
                    if self._has_healing_effect(card):
                        # Only show if there are damaged Pokemon to heal
                        # Parse the effect to get type restrictions
                        effects = EffectParser.parse_multiple(card.ability.effect)
                        has_healable_pokemon = False
                        for effect in effects:
                            if isinstance(effect, (HealEffect, HealAllEffect)):
                                if self._has_damaged_pokemon_to_heal(effect):
                                    has_healable_pokemon = True
                                    break
                        if not has_healable_pokemon:
                            continue  # Skip this healing item
                    actions.append(f"play_item_{card.id}")
        return actions
    
    def _get_play_supporter_actions(self) -> List[str]:
        """Get actions to play Supporter cards"""
        actions = []
        from v3.models.cards.supporter import Supporter
        from v3.models.match.effects import EffectParser
        from v3.models.match.effects.heal_effect import HealEffect
        from v3.models.match.effects.heal_all_effect import HealAllEffect
        
        if self.can_play_trainer and not self.played_supporter_this_turn:
            for card in self.cards_in_hand:
                if isinstance(card, Supporter):
                    # Check if this is a healing supporter
                    if self._has_healing_effect(card):
                        # Only show if there are damaged Pokemon to heal
                        # Parse the effect to get type restrictions
                        effects = EffectParser.parse_multiple(card.ability.effect)
                        has_healable_pokemon = False
                        for effect in effects:
                            if isinstance(effect, (HealEffect, HealAllEffect)):
                                if self._has_damaged_pokemon_to_heal(effect):
                                    has_healable_pokemon = True
                                    break
                        if not has_healable_pokemon:
                            continue  # Skip this healing supporter
                    actions.append(f"play_supporter_{card.id}")
        return actions
    
    def _get_attach_tool_actions(self) -> List[str]:
        """Get actions to attach Tool cards"""
        actions = []
        from v3.models.cards.tool import Tool
        if self.can_play_trainer:
            for card in self.cards_in_hand:
                if isinstance(card, Tool):
                    # Can attach to active
                    if self.active_pokemon and self.active_pokemon.poketool is None:
                        actions.append(f"attach_tool_{card.id}_active")
                    # Can attach to bench Pokemon
                    for i, bench_pokemon in enumerate(self.bench_pokemons):
                        if bench_pokemon and bench_pokemon.poketool is None:
                            actions.append(f"attach_tool_{card.id}_bench_{i}")
        return actions
    
    def _get_use_ability_actions(self) -> List[str]:
        """Get actions to use Pokemon abilities"""
        actions = []
        from v3.models.match.effects import EffectParser
        from v3.models.match.effects.heal_effect import HealEffect
        from v3.models.match.effects.heal_all_effect import HealAllEffect
        
        # Check active Pokemon
        if self.active_pokemon and not self.active_pokemon.used_ability_this_turn:
            for i, ability in enumerate(self.active_pokemon.abilities):
                # Check if this ability has a healing effect
                if ability and ability.effect:
                    effects = EffectParser.parse_multiple(ability.effect)
                    is_healing_ability = any(isinstance(e, (HealEffect, HealAllEffect)) for e in effects)
                    if is_healing_ability:
                        # Only show if there are damaged Pokemon to heal
                        has_healable_pokemon = False
                        for effect in effects:
                            if isinstance(effect, (HealEffect, HealAllEffect)):
                                if self._has_damaged_pokemon_to_heal(effect):
                                    has_healable_pokemon = True
                                    break
                        if not has_healable_pokemon:
                            continue  # Skip this healing ability
                actions.append(f"use_ability_active_{i}")
        
        # Check bench Pokemon
        for bench_idx, bench_pokemon in enumerate(self.bench_pokemons):
            if bench_pokemon and not bench_pokemon.used_ability_this_turn:
                for i, ability in enumerate(bench_pokemon.abilities):
                    # Check if this ability has a healing effect
                    if ability and ability.effect:
                        effects = EffectParser.parse_multiple(ability.effect)
                        is_healing_ability = any(isinstance(e, (HealEffect, HealAllEffect)) for e in effects)
                        if is_healing_ability:
                            # Only show if there are damaged Pokemon to heal
                            has_healable_pokemon = False
                            for effect in effects:
                                if isinstance(effect, (HealEffect, HealAllEffect)):
                                    if self._has_damaged_pokemon_to_heal(effect):
                                        has_healable_pokemon = True
                                        break
                            if not has_healable_pokemon:
                                continue  # Skip this healing ability
                    actions.append(f"use_ability_bench_{bench_idx}_{i}")
        
        return actions

    def _has_healing_effect(self, card) -> bool:
        """Check if a card (Item/Supporter) has a healing effect"""
        from v3.models.match.effects import EffectParser
        from v3.models.match.effects.heal_effect import HealEffect
        from v3.models.match.effects.heal_all_effect import HealAllEffect
        
        if not card.ability or not card.ability.effect:
            return False
        
        # Parse the effect to see if it's a healing effect
        effects = EffectParser.parse_multiple(card.ability.effect)
        for effect in effects:
            if isinstance(effect, (HealEffect, HealAllEffect)):
                return True
        return False
    
    def _has_damaged_pokemon_to_heal(self, heal_effect=None) -> bool:
        """Check if there are any damaged Pokemon that can be healed
        
        Args:
            heal_effect: Optional HealEffect to check type restrictions
        Returns:
            True if there are damaged Pokemon that match the healing criteria
        """
        from v3.models.cards.energy import Energy
        
        # If no heal effect specified, check for any damaged Pokemon
        if heal_effect is None:
            # Check active Pokemon
            if self.active_pokemon and self.active_pokemon.damage_taken > 0:
                return True
            # Check bench Pokemon
            for bench_pokemon in self.bench_pokemons:
                if bench_pokemon and bench_pokemon.damage_taken > 0:
                    return True
            return False
        
        # Check with type restrictions from heal_effect
        pokemon_type = getattr(heal_effect, 'pokemon_type', None)
        target = getattr(heal_effect, 'target', 'one')
        
        # Check active Pokemon
        if self.active_pokemon and self.active_pokemon.damage_taken > 0:
            if not pokemon_type:
                return True  # No type restriction, can heal
            # Check type match
            type_map = {
                'grass': Energy.Type.GRASS,
                'fire': Energy.Type.FIRE,
                'water': Energy.Type.WATER,
                'electric': Energy.Type.ELECTRIC,
                'lightning': Energy.Type.ELECTRIC,
                'psychic': Energy.Type.PSYCHIC,
                'rock': Energy.Type.ROCK,
                'fighting': Energy.Type.ROCK,
                'dark': Energy.Type.DARK,
                'darkness': Energy.Type.DARK,
                'metal': Energy.Type.METAL,
            }
            expected_type = type_map.get(pokemon_type.lower())
            if expected_type and self.active_pokemon.element == expected_type:
                return True
        
        # Check bench Pokemon
        for bench_pokemon in self.bench_pokemons:
            if bench_pokemon and bench_pokemon.damage_taken > 0:
                if not pokemon_type:
                    return True  # No type restriction, can heal
                # Check type match
                expected_type = type_map.get(pokemon_type.lower())
                if expected_type and bench_pokemon.element == expected_type:
                    return True
        
        return False

    ########################################################
    #            PRIVATE METHODS STARTING HERE             #
    ########################################################

    # Initialize the deck
    # Initalize 
    def _initialize_deck(self, deck):
        # Filter out None values from the deck
        if None in deck:
            raise ValueError("Deck cannot contain None values")
        if self._check_for_basic_pokemon(deck) == False:
            raise ValueError("Deck must contain at least one basic pokemon")
        if len(deck) != 20:
            raise ValueError("Deck must contain 20 cards")
        # Check for duplicate cards (max 2 copies allowed)
        for card in deck:
            if deck.count(card.name) > 2:
                raise ValueError(f"Deck cannot contain more than 2 copies of {card.name}")
        
        # Set all cards in deck to DECK position
        for card in deck:
            card.card_position = Card.Position.DECK

    # Refill energy to be performed at the start of the players turn
    def _add_energies_to_energy_zone(self):
        """Refill energy zone at start of turn"""
        self.energy_zone.generate_energy()
    
    def _can_add_energy_to_pokemon(self):
        # Check if the pokemon can add energy to its energy zone
        return self.energy_zone.has_energy()
    
    def _add_energy_to_pokemon(self, pokemon: Pokemon):
        # Add energy to the pokemon
        if self._can_add_energy_to_pokemon():
            pokemon.energy_zone.append(self.energy_zone)
            self.energy_zone = None
        else:
            raise ValueError("Should have checked if energy zone is not None")

    def _check_for_basic_pokemon(self, deck):
        for card in deck:
            if type(card) is Pokemon and card.subtype == "Basic":
                return True
        return False

    def _shuffle_deck(self):
        # Ensure all cards in deck have DECK position
        random.shuffle(self.deck)




    ########################################################
    #           Still need to implement these              #
    ########################################################

    def set_active_pokemon(self, pokemon):
        """Set a Pokemon as the active Pokemon."""
        if pokemon:
            pokemon.card_position = Card.Position.ACTIVE
        self.active_pokemon = pokemon

    def add_to_bench(self, pokemon, position):
        """Add a Pokemon to the bench at a specific position."""
        if pokemon and 0 <= position < len(self.bench_pokemons):
            pokemon.card_position = Card.Position.BENCH
            self.bench_pokemons[position] = pokemon

    def discard_card(self, card):
        """Add a card to the discard pile."""
        if card:
            card.card_position = Card.Position.DISCARD
            self.discard_pile.append(card)
    
    @property
    def energy_zone_current_energy(self) -> Optional[Energy.Type]:
        return self.energy_zone.current_energy
    
    @property
    def energy_zone_next_energy(self) -> Optional[Energy.Type]:
        return self.energy_zone.next_energy

