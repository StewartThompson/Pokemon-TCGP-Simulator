#!/usr/bin/env python3

import argparse
import random
import sys
import os
from .battle_engine import BattleEngine
from .load_deck import DeckLoader
from .player import Player
from v2.agents.human_agent import HumanAgent
from v2.agents.random_agent import RandomAgent
from cards.pokemon import Pokemon

class Match:
    """Simple match class that takes two Player objects"""
    
    def __init__(self, player1: Player, player2: Player, debug: bool = False):
        self.player1 = player1
        self.player2 = player2
        self.debug = debug
    
    def start_battle(self):
        """Start battle and return winner"""
        battle_engine = BattleEngine(self.player1, self.player2, self.debug)
        winner_player = battle_engine.start_battle()
        
        # Return the winner's name for compatibility
        return winner_player.name if winner_player else "Draw"
    
    def get_possible_attacks(self, pokemon: Pokemon):
        """Get possible attacks for a pokemon"""
        return pokemon.get_possible_attacks()
    
    def get_player_state(self, player: Player):
        """Get the state of the match"""
        return self.player1.get_state()

def main():
    parser = argparse.ArgumentParser(description="Pokemon Match Simulator")
    parser.add_argument("--deck1", nargs=2, help="Player 1: agent deck_name")
    parser.add_argument("--deck2", nargs=2, help="Player 2: agent deck_name") 
    parser.add_argument("--simulations", type=int, default=1)
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    if not args.deck1 or not args.deck2:
        print("Need --deck1 and --deck2")
        return
    
    agent1_name, deck1_name = args.deck1
    agent2_name, deck2_name = args.deck2

    # Load decks
    deck_loader = DeckLoader()
    deck1, deck1_type = deck_loader.load_deck_by_name(deck1_name)
    deck2, deck2_type = deck_loader.load_deck_by_name(deck2_name)
    
    if not deck1:
        print(f"Deck '{deck1_name}' not found")
        return
    if not deck2:
        print(f"Deck '{deck2_name}' not found") 
        return

    # Create agents
    agent1_class = HumanAgent if agent1_name == "human" else RandomAgent
    agent2_class = HumanAgent if agent2_name == "human" else RandomAgent

    # Create players
    player1 = Player("Player 1", deck1, chosen_energies=deck1_type, agent=agent1_class)
    player2 = Player("Player 2", deck2, chosen_energies=deck2_type, agent=agent2_class)
    
    print(f"  {deck1_name} vs {deck2_name}")
    
    results = {"Player 1": 0, "Player 2": 0, "Draw": 0}
    for i in range(args.simulations):
        # Create a new match for each simulation
        match = Match(player1, player2, debug=args.debug)
        winner = match.start_battle()
        results[winner] += 1
    
    print(f"Results: Player 1: {results['Player 1']}, Player 2: {results['Player 2']}, Draws: {results['Draw']}")

if __name__ == "__main__":
    main()