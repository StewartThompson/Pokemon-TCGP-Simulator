from v2.agents.random_agent import RandomAgent

import random
from v2.agents import bot_agent
from cards.pokemon import Pokemon
from game.ids.actions import *
from cards.card import Card

class Player:
    def __init__(self, name, deck, chosen_energies=None, agent=None):
        self.name = name
        self.deck = deck
        self.chosen_energies = chosen_energies
        self.agent = agent(self) if agent else bot_agent.RandomAgent(self)

        # These values are game values for the player
        self.points = 0
        self.cards_in_hand = []
        self.active_pokemon: Pokemon = None
        self.bench_pokemons: list[Pokemon] = [None, None, None]
        self.discard_pile = []
        self.prize_points = 0
        self.can_play_trainer = True
        self.energy_points = 10

        self.energy_pile = []  # This is the next two energies to be used
        self.energy_zone = []  # Energy Zone for PTCGP mechanics

        # These values are used to help the bot know the composition of the deck for strategy
        self._original_deck = deck 

        # Methods to be called at the start of the game
        self._initialize_deck(deck)
        self._add_energies_to_energy_pile()
        
    
    # Refill energy to be performed at the start of the players turn
    def _add_energies_to_energy_pile(self):
        # Keep adding energies until we have 2 in the pile
        while len(self.energy_pile) < 2:
            # Ensure we have at least one energy type to choose from
            if self.chosen_energies:
                self.energy_pile.append(random.choice(self.chosen_energies))

    def pokemon_field(self):
        """Return a list of all active and bench Pokémon belonging to this player."""
        pokemons = []
        if self.active_pokemon:
            pokemons.append(self.active_pokemon)
        if self.bench_pokemons:
            pokemons.extend(self.bench_pokemons)
        return pokemons

    # If player has no pokemon left, they lose the game
    def has_pokemon_left(self):
        """Check if player has any Pokémon left."""
        return self.active_pokemon is not None and len(self.bench_pokemons) > 0

    # Draws inital hand and checks for basic pokemon
    def draw_inital_hand(self):
        while True:
            self.shuffle_deck()
            self.draw(5)
            if self._check_for_basic_pokemon(self.cards_in_hand) == True:
                return
            else:
                # If no basic pokemon is drawn, reset the deck and draw again
                self.deck = self._original_deck
                self.cards_in_hand = []

    def get_basic_pokemon(self):
        return [card for card in self.cards_in_hand if card.subtype == "Basic"]

    def shuffle_deck(self):
        # Ensure all cards in deck have DECK position
        for card in self.deck:
            card.card_position = Card.Position.DECK
        random.shuffle(self.deck)

    def draw(self, n):
        for i in range(int(n)):
            if len(self.deck) == 0 or len(self.cards_in_hand) > 10:
                return False

            card = self.deck[0]
            card.card_position = Card.Position.HAND
            self.cards_in_hand.append(card)
            self.deck.pop(0)
        return True

    def __str__(self):
        return f"Player {self.name} - Points: {self.points}, Hand: {len(self.cards_in_hand)}, Active Pokemon: {self.active_pokemon}, Bench: {self.bench_pokemons}, \nDeck: {len(self.deck)}"

    # PRIVATE METHODS STARTING HERE

    # Initalize 
    def _initialize_deck(self, deck):
        # Filter out None values from the deck
        valid_deck = [card for card in deck if card is not None]
        
        if len(valid_deck) != 20:
            raise ValueError("Deck must contain 20 cards")
        
        if self._check_for_basic_pokemon(valid_deck) == False:
            raise ValueError("Deck must contain at least one basic pokemon")
        if len(valid_deck) != 20:
            raise ValueError("Deck must contain 20 cards")
        
        # Set all cards in deck to DECK position
        for card in valid_deck:
            card.card_position = Card.Position.DECK
            
        self.deck = valid_deck
        self._original_deck = valid_deck[:]

    def _check_for_basic_pokemon(self, deck):
        for card in deck:
            if type(card) is Pokemon and card.subtype == "Basic":
                return True
        return False

    def _set_energy_pile(self):
        # Set the energy pile to two random energies from self._original_deck_energy_types
        self.energy_pile = random.sample(self.chosen_energies, 2)

    def _get_turn_zero_actions(self):
        actions = []

        if self.active_pokemon is not None:
            actions.extend(["end_turn"])

        for card in self.cards_in_hand:
            if card.subtype == "Basic" and self.active_pokemon is None:
                actions.extend([action for action in card._get_actions(self, None) if '_pactive_' in action])
            elif card.subtype == "Basic" and self.active_pokemon is not None:
                actions.extend(card._get_actions(self, None))
        return actions

    def _get_actions(self, opponent_pokemon_locations):
        """Get all possible actions for the player"""

        actions = ["end_turn"]

        if self.energy_pile[0] is not None:
            actions.extend(["pactive_attach_energy", "pbench1_attach_energy", 
                            "pbench2_attach_energy", "pbench3_attach_energy"])

        # Get the actions from the player
        if self.active_pokemon is not None:
            actions.extend(self.active_pokemon._get_actions(self, opponent_pokemon_locations))

        for pokemon in self.bench_pokemons:
            if pokemon is not None:
                actions.extend(pokemon._get_actions(self, opponent_pokemon_locations))
        
        # Get the actions from hand
        for card in self.cards_in_hand:
            actions.extend(card._get_actions(self, opponent_pokemon_locations))
        
        return actions

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

