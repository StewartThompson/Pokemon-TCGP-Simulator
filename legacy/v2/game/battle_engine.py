import random
import sys
import os
from typing import List, Dict, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum

# Add v2 directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from game.game_rules import GameRules
from import_files.card_loader import CardLoader
from game.player import Player
from cards.pokemon import Pokemon
from cards.card import Card
from v2.agents.random_agent import RandomAgent
from v2.game.ids.state import *  # Import all state constants
from v2.game.ids.energy import ENERGY_TYPES
from v2.game.ids.stages import STAGES


class CardType(Enum):
    POKEMON = "pokemon"
    TRAINER = "trainer"
    ITEM = "item"
    TOOL = "tool"

class GamePhase(Enum):
    SETUP = "setup"
    TURN_ZERO = "turn_zero"
    MAIN = "main"
    END = "end"



class BattleEngine:
    """Core battle engine - simplified and modular"""
    
    def __init__(self, player1: Player, player2: Player, debug: bool = False):
        self.players = [player1, player2]
        self.debug = debug

        self.current_player_index = 0
        self.turn = 0
        self.phase = GamePhase.SETUP
        self.winner = None
        self.state = [0] * STATE_SIZE
    
    def log(self, message: str):
        if self.debug:
            print(f"[Turn {self.turn}] {message}")
    
    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]
    
    @property
    def opponent(self) -> Player:
        return self.players[1 - self.current_player_index]
    
    def start_battle(self) -> Optional[Player]:
        """Main battle execution"""
        try:
            self._setup_game()
            self._turn_zero(self.players[0], self.players[1])
            self._turn_zero(self.players[1], self.players[0])
            
            while not self._is_game_over():
                self._execute_turn()
            return self._determine_winner()
        except Exception as e:
            self.log(f"Battle error: {e}")
            return None
        
    
    #### PRIVATE METHODS ####

    def _setup_game(self):
        """Initialize game state"""
        self.log("Setting up battle...")
        
        # Determine first player
        self.current_player_index = random.randint(0, 1)
        self.log(f"{self.current_player.name} goes first!")
        
        # Setup both players
        for player in self.players:
            self._setup_player(player)
        
        self.phase = GamePhase.TURN_ZERO
    
    def _setup_player(self, player: Player):
        """Setup individual player with mulligan handling"""
        # Draw initial hand
        player.draw_inital_hand()
    
    def _execute_turn(self):
        """Execute a complete turn"""
        self.turn += 1
        current = self.current_player
        
        self.log(f"Turn {self.turn} - {current.name}")
        
        # Turn start procedures
        self._start_turn_effects(current)
        self._draw_phase(current)
        self._main_phase(current)
        self._end_turn()

    def _turn_zero(self, player: Player, opponent: Player):
        # Get State
        state = self._get_state(player, opponent)
        # Get Actions
        actions = player._get_turn_zero_actions()

        # Play Action
        player.agent.play_action(actions)

    
    def _create_empty_state(self) -> List[float]:
        """Create an empty state array initialized with zeros"""
        return [0.0] * STATE_SIZE
    
    # This is a function that gets the state for the human player or for the AI
    def _get_state(self, player: Player, opponent: Player) -> Dict[str, Any]:
        # If the player is human, get the state from the human player
        if player.agent.is_human:
            #return player._get_human_state()
            return []
        # If the player is AI, get the state from the AI
        else:
            return self.get_ai_state(player, opponent)
        
    def _get_actions(self, player: Player) -> List[str]:
        """Get all possible actions for the player"""

        # Get the actions from the player
        opponent_pokemon_locations = self._get_opponent_pokemon_locations(player, self.opponent)
        return player._get_actions(opponent_pokemon_locations)

    def _start_turn_effects(self, player: Player):
        """Handle start-of-turn effects"""
        return
    
    def _draw_phase(self, player: Player):
        """Draw phase"""
        return
    
    def _main_phase(self, player: Player):
        """Main phase with player actions"""
        return
    
    def _get_player_action(self, player: Player, has_attacked: bool) -> Optional[str]:
        """Get and execute player action"""
        return
    
    def _default_ai_action(self, player: Player, has_attacked: bool) -> str:
        """Simple default AI logic"""
        # Try to attack
        return
    
    def _get_playable_cards(self, player: Player) -> List[Card]:
        """Get cards that can be played this turn"""
        return
    
    def _can_evolve_any(self, evolution: Pokemon, player: Player) -> bool:
        """Check if evolution can be played on any Pokemon"""
        return
    
    def _play_card(self, card: Card, player: Player):
        """Play a card from hand"""
        return
    
    def _evolve_pokemon(self, evolution: Pokemon, player: Player):
        """Handle Pokemon evolution"""
        return
    
    def _execute_attack(self, attacker: Pokemon, attack_index: int):
        """Execute an attack"""
        return
    
    def _calculate_damage(self, attacker: Pokemon, defender: Pokemon, base_damage: int) -> int:
        """Calculate final damage (can be extended for type effectiveness, etc.)"""
        return
    
    def _handle_knockout(self, knocked_out: Pokemon):
        """Handle Pokemon knockout"""
        return
    
    def _force_active_replacement(self):
        """Force opponent to replace active Pokemon"""
        return
    
    def _process_status_effects(self, player: Player):
        """Handle status effects at turn start"""
        return
    
    def _end_turn(self):
        """End current turn and switch players"""
        return
    
    def _is_game_over(self) -> bool:
        """Check if game should end"""
        return
    
    def _determine_winner(self) -> Optional[Player]:
        """Determine final winner"""
        return
    
    def _get_human_state(self, player: Player, opponent: Player) -> List[float]:
        """Get the state for the human player"""
        # This will be the GUI state that the human player sees
        return
    
    def _get_opponent_pokemon_locations(self, player: Player, opponent: Player) -> int:
        """Get the location of the opponent's active pokemon"""
        pokemon_locations = [0] * 3
        if opponent.active_pokemon:
            pokemon_locations[0] = 1
        if opponent.bench_pokemons[0]:
            pokemon_locations[1] = 1
        if opponent.bench_pokemons[1]:
            pokemon_locations[2] = 1
        if opponent.bench_pokemons[2]:
            pokemon_locations[3] = 1
        return pokemon_locations


    def get_ai_state(self, player: Player, opponent: Player) -> List[float]:
        """Get the state for the player"""
        self.state[pa_pokemon_id] = player.active_pokemon.id if player.active_pokemon else 0
        self.state[pa_pokemon_element] = ENERGY_TYPES[player.active_pokemon.element] if player.active_pokemon else 0
        self.state[pa_pokemon_stage] = STAGES[player.active_pokemon.stage] if player.active_pokemon else 0
        self.state[pa_pokemon_max_hp] = player.active_pokemon.max_hp if player.active_pokemon else 0
        self.state[pa_pokemon_attack_1] = player.active_pokemon.attacks[0].id if player.active_pokemon else 0
        self.state[pa_pokemon_attack_2] = player.active_pokemon.attacks[1].id if player.active_pokemon else 0
        self.state[pa_pokemon_retreat_cost] = player.active_pokemon.retreat_cost if player.active_pokemon else 0
        self.state[pa_pokemon_weakness] = ENERGY_TYPES[player.active_pokemon.weakness] if player.active_pokemon else 0
        self.state[pa_pokemon_ability] = player.active_pokemon.abilities[0].id if player.active_pokemon else 0
        self.state[pa_pokemon_evolves_from] = player.active_pokemon.evolves_from.id if player.active_pokemon else 0
        self.state[pa_pokemon_is_ex] = 1 if (player.active_pokemon and player.active_pokemon.is_ex) else 0
        self.state[pa_pokemon_poketool_id] = player.active_pokemon.poketool.id if player.active_pokemon else 0
        self.state[pa_pokemon_can_retreat] = 1 if (player.active_pokemon and player.active_pokemon.can_retreat) else 0
        self.state[pa_pokemon_damage_nerf] = player.active_pokemon.damage_nerf if player.active_pokemon else 0
        self.state[pa_pokemon_damage_taken] = player.active_pokemon.damage_taken if player.active_pokemon else 0
        self.state[pa_pokemon_placed_or_evolved_this_turn] = 1 if (player.active_pokemon and player.active_pokemon.placed_or_evolved_this_turn) else 0
        self.state[pa_pokemon_used_ability_this_turn] = 1 if (player.active_pokemon and player.active_pokemon.used_ability_this_turn) else 0
        
        # Status Effects
        self.state[pa_pokemon_status_poisoned] = 1 if (player.active_pokemon and player.active_pokemon.status_poisoned) else 0
        self.state[pa_pokemon_status_burned] = 1 if (player.active_pokemon and player.active_pokemon.status_burned) else 0
        self.state[pa_pokemon_status_paralyzed] = 1 if (player.active_pokemon and player.active_pokemon.status_paralyzed) else 0
        self.state[pa_pokemon_status_asleep] = 1 if (player.active_pokemon and player.active_pokemon.status_asleep) else 0
        self.state[pa_pokemon_status_confused] = 1 if (player.active_pokemon and player.active_pokemon.status_confused) else 0
        self.state[pa_pokemon_status_frozen] = 1 if (player.active_pokemon and player.active_pokemon.status_frozen) else 0
        
        # Energy on Active Pokémon
        self.state[pa_pokemon_energy_grass] = player.active_pokemon.equipped_energies['grass'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_fire] = player.active_pokemon.equipped_energies['fire'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_water] = player.active_pokemon.equipped_energies['water'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_lightning] = player.active_pokemon.equipped_energies['lightning'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_psychic] = player.active_pokemon.equipped_energies['psychic'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_fighting] = player.active_pokemon.equipped_energies['fighting'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_darkness] = player.active_pokemon.equipped_energies['darkness'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_metal] = player.active_pokemon.equipped_energies['metal'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_fairy] = player.active_pokemon.equipped_energies['fairy'] if player.active_pokemon else 0
        self.state[pa_pokemon_energy_normal] = player.active_pokemon.equipped_energies['normal'] if player.active_pokemon else 0

        # Bench Pokémon 1
        self.state[pb1_pokemon_id] = player.bench_pokemons[0].id if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_element] = ENERGY_TYPES[player.bench_pokemons[0].element] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_stage] = STAGES[player.bench_pokemons[0].stage] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_max_hp] = player.bench_pokemons[0].max_hp if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_attack_1] = player.bench_pokemons[0].attacks[0].id if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_attack_2] = player.bench_pokemons[0].attacks[1].id if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_retreat_cost] = player.bench_pokemons[0].retreat_cost if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_weakness] = ENERGY_TYPES[player.bench_pokemons[0].weakness] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_ability] = player.bench_pokemons[0].abilities[0].id if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_evolves_from] = player.bench_pokemons[0].evolves_from.id if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_is_ex] = 1 if (player.bench_pokemons and player.bench_pokemons[0] and player.bench_pokemons[0].is_ex) else 0
        self.state[pb1_pokemon_poketool_id] = player.bench_pokemons[0].poketool.id if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_can_retreat] = 1 if (player.bench_pokemons and player.bench_pokemons[0] and player.bench_pokemons[0].can_retreat) else 0
        self.state[pb1_pokemon_damage_nerf] = player.bench_pokemons[0].damage_nerf if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_damage_taken] = player.bench_pokemons[0].damage_taken if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_placed_or_evolved_this_turn] = 1 if (player.bench_pokemons and player.bench_pokemons[0] and player.bench_pokemons[0].placed_or_evolved_this_turn) else 0
        self.state[pb1_pokemon_used_ability_this_turn] = 1 if (player.bench_pokemons and player.bench_pokemons[0] and player.bench_pokemons[0].used_ability_this_turn) else 0
        
        # Energy on Bench Pokémon 1
        self.state[pb1_pokemon_energy_grass] = player.bench_pokemons[0].equipped_energies['grass'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_fire] = player.bench_pokemons[0].equipped_energies['fire'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_water] = player.bench_pokemons[0].equipped_energies['water'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_lightning] = player.bench_pokemons[0].equipped_energies['lightning'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_psychic] = player.bench_pokemons[0].equipped_energies['psychic'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_fighting] = player.bench_pokemons[0].equipped_energies['fighting'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_darkness] = player.bench_pokemons[0].equipped_energies['darkness'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_metal] = player.bench_pokemons[0].equipped_energies['metal'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_fairy] = player.bench_pokemons[0].equipped_energies['fairy'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        self.state[pb1_pokemon_energy_normal] = player.bench_pokemons[0].equipped_energies['normal'] if player.bench_pokemons and player.bench_pokemons[0] else 0
        
        # Bench Pokémon 2
        self.state[pb2_pokemon_id] = player.bench_pokemons[1].id if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_element] = ENERGY_TYPES[player.bench_pokemons[1].element] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_stage] = STAGES[player.bench_pokemons[1].stage] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_max_hp] = player.bench_pokemons[1].max_hp if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_attack_1] = player.bench_pokemons[1].attacks[0].id if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_attack_2] = player.bench_pokemons[1].attacks[1].id if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_retreat_cost] = player.bench_pokemons[1].retreat_cost if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_weakness] = ENERGY_TYPES[player.bench_pokemons[1].weakness] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_ability] = player.bench_pokemons[1].abilities[0].id if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_evolves_from] = player.bench_pokemons[1].evolves_from.id if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_is_ex] = 1 if (player.bench_pokemons and player.bench_pokemons[1] and player.bench_pokemons[1].is_ex) else 0
        self.state[pb2_pokemon_poketool_id] = player.bench_pokemons[1].poketool.id if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_can_retreat] = 1 if (player.bench_pokemons and player.bench_pokemons[1] and player.bench_pokemons[1].can_retreat) else 0
        self.state[pb2_pokemon_damage_nerf] = player.bench_pokemons[1].damage_nerf if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_damage_taken] = player.bench_pokemons[1].damage_taken if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_placed_or_evolved_this_turn] = 1 if (player.bench_pokemons and player.bench_pokemons[1] and player.bench_pokemons[1].placed_or_evolved_this_turn) else 0
        self.state[pb2_pokemon_used_ability_this_turn] = 1 if (player.bench_pokemons and player.bench_pokemons[1] and player.bench_pokemons[1].used_ability_this_turn) else 0
        
        # Energy on Bench Pokémon 2
        self.state[pb2_pokemon_energy_grass] = player.bench_pokemons[1].equipped_energies['grass'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_fire] = player.bench_pokemons[1].equipped_energies['fire'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_water] = player.bench_pokemons[1].equipped_energies['water'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_lightning] = player.bench_pokemons[1].equipped_energies['lightning'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_psychic] = player.bench_pokemons[1].equipped_energies['psychic'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_fighting] = player.bench_pokemons[1].equipped_energies['fighting'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_darkness] = player.bench_pokemons[1].equipped_energies['darkness'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_metal] = player.bench_pokemons[1].equipped_energies['metal'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_fairy] = player.bench_pokemons[1].equipped_energies['fairy'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        self.state[pb2_pokemon_energy_normal] = player.bench_pokemons[1].equipped_energies['normal'] if player.bench_pokemons and player.bench_pokemons[1] else 0
        
        # Bench Pokémon 3
        self.state[pb3_pokemon_id] = player.bench_pokemons[2].id if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_element] = ENERGY_TYPES[player.bench_pokemons[2].element] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_stage] = STAGES[player.bench_pokemons[2].stage] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_max_hp] = player.bench_pokemons[2].max_hp if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_attack_1] = player.bench_pokemons[2].attacks[0].id if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_attack_2] = player.bench_pokemons[2].attacks[1].id if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_retreat_cost] = player.bench_pokemons[2].retreat_cost if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_weakness] = ENERGY_TYPES[player.bench_pokemons[2].weakness] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_ability] = player.bench_pokemons[2].abilities[0].id if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_evolves_from] = player.bench_pokemons[2].evolves_from.id if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_is_ex] = 1 if (player.bench_pokemons and player.bench_pokemons[2] and player.bench_pokemons[2].is_ex) else 0
        self.state[pb3_pokemon_poketool_id] = player.bench_pokemons[2].poketool.id if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_can_retreat] = 1 if (player.bench_pokemons and player.bench_pokemons[2] and player.bench_pokemons[2].can_retreat) else 0
        self.state[pb3_pokemon_damage_nerf] = player.bench_pokemons[2].damage_nerf if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_damage_taken] = player.bench_pokemons[2].damage_taken if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_placed_or_evolved_this_turn] = 1 if (player.bench_pokemons and player.bench_pokemons[2] and player.bench_pokemons[2].placed_or_evolved_this_turn) else 0
        self.state[pb3_pokemon_used_ability_this_turn] = 1 if (player.bench_pokemons and player.bench_pokemons[2] and player.bench_pokemons[2].used_ability_this_turn) else 0
        
        # Energy on Bench Pokémon 3
        self.state[pb3_pokemon_energy_grass] = player.bench_pokemons[2].equipped_energies['grass'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_fire] = player.bench_pokemons[2].equipped_energies['fire'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_water] = player.bench_pokemons[2].equipped_energies['water'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_lightning] = player.bench_pokemons[2].equipped_energies['lightning'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_psychic] = player.bench_pokemons[2].equipped_energies['psychic'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_fighting] = player.bench_pokemons[2].equipped_energies['fighting'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_darkness] = player.bench_pokemons[2].equipped_energies['darkness'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_metal] = player.bench_pokemons[2].equipped_energies['metal'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_fairy] = player.bench_pokemons[2].equipped_energies['fairy'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        self.state[pb3_pokemon_energy_normal] = player.bench_pokemons[2].equipped_energies['normal'] if player.bench_pokemons and player.bench_pokemons[2] else 0
        
        # Card Count
        self.state[p_card_count] = len(player.cards_in_hand)

        self.state[p_hand_card_id_0] = player.cards_in_hand[0].id if len(player.cards_in_hand) > 0 else 0
        self.state[p_hand_card_id_1] = player.cards_in_hand[1].id if len(player.cards_in_hand) > 1 else 0
        self.state[p_hand_card_id_2] = player.cards_in_hand[2].id if len(player.cards_in_hand) > 2 else 0
        self.state[p_hand_card_id_3] = player.cards_in_hand[3].id if len(player.cards_in_hand) > 3 else 0
        self.state[p_hand_card_id_4] = player.cards_in_hand[4].id if len(player.cards_in_hand) > 4 else 0
        self.state[p_hand_card_id_5] = player.cards_in_hand[5].id if len(player.cards_in_hand) > 5 else 0
        self.state[p_hand_card_id_6] = player.cards_in_hand[6].id if len(player.cards_in_hand) > 6 else 0
        self.state[p_hand_card_id_7] = player.cards_in_hand[7].id if len(player.cards_in_hand) > 7 else 0
        self.state[p_hand_card_id_8] = player.cards_in_hand[8].id if len(player.cards_in_hand) > 8 else 0
        self.state[p_hand_card_id_9] = player.cards_in_hand[9].id if len(player.cards_in_hand) > 9 else 0

        # Take cards in deck and determine a probability for each one to be drawn next
        self.state[p_deck_card_id_0] = player.deck[0].id if len(player.deck) > 0 else 0
        self.state[p_deck_card_id_1] = player.deck[1].id if len(player.deck) > 1 else 0
        self.state[p_deck_card_id_2] = player.deck[2].id if len(player.deck) > 2 else 0
        self.state[p_deck_card_id_3] = player.deck[3].id if len(player.deck) > 3 else 0
        self.state[p_deck_card_id_4] = player.deck[4].id if len(player.deck) > 4 else 0
        self.state[p_deck_card_id_5] = player.deck[5].id if len(player.deck) > 5 else 0
        self.state[p_deck_card_id_6] = player.deck[6].id if len(player.deck) > 6 else 0
        self.state[p_deck_card_id_7] = player.deck[7].id if len(player.deck) > 7 else 0
        self.state[p_deck_card_id_8] = player.deck[8].id if len(player.deck) > 8 else 0
        self.state[p_deck_card_id_9] = player.deck[9].id if len(player.deck) > 9 else 0
        self.state[p_deck_card_id_10] = player.deck[10].id if len(player.deck) > 10 else 0
        self.state[p_deck_card_id_11] = player.deck[11].id if len(player.deck) > 11 else 0
        self.state[p_deck_card_id_12] = player.deck[12].id if len(player.deck) > 12 else 0
        self.state[p_deck_card_id_13] = player.deck[13].id if len(player.deck) > 13 else 0
        self.state[p_deck_card_id_14] = player.deck[14].id if len(player.deck) > 14 else 0
        self.state[p_deck_card_id_15] = player.deck[15].id if len(player.deck) > 15 else 0
        self.state[p_deck_card_id_16] = player.deck[16].id if len(player.deck) > 16 else 0
        self.state[p_deck_card_id_17] = player.deck[17].id if len(player.deck) > 17 else 0
        self.state[probability_of_drawing_card] = round((1 / len(player.deck)) * 100) if len(player.deck) > 0 else 0

        # Opponent Active Pokemon
        self.state[oa_pokemon_id] = opponent.active_pokemon.id if opponent.active_pokemon else 0
        self.state[oa_pokemon_element] = ENERGY_TYPES[opponent.active_pokemon.element] if opponent.active_pokemon else 0
        self.state[oa_pokemon_stage] = STAGES[opponent.active_pokemon.stage] if opponent.active_pokemon else 0
        self.state[oa_pokemon_max_hp] = opponent.active_pokemon.max_hp if opponent.active_pokemon else 0
        self.state[oa_pokemon_attack_1] = opponent.active_pokemon.attacks[0].id if opponent.active_pokemon else 0
        self.state[oa_pokemon_attack_2] = opponent.active_pokemon.attacks[1].id if opponent.active_pokemon else 0
        self.state[oa_pokemon_retreat_cost] = opponent.active_pokemon.retreat_cost if opponent.active_pokemon else 0
        self.state[oa_pokemon_weakness] = ENERGY_TYPES[opponent.active_pokemon.weakness] if opponent.active_pokemon else 0
        self.state[oa_pokemon_ability] = opponent.active_pokemon.abilities[0].id if opponent.active_pokemon else 0
        self.state[oa_pokemon_evolves_from] = opponent.active_pokemon.evolves_from.id if opponent.active_pokemon else 0
        self.state[oa_pokemon_is_ex] = 1 if (opponent.active_pokemon and opponent.active_pokemon.is_ex) else 0
        self.state[oa_pokemon_poketool_id] = opponent.active_pokemon.poketool.id if opponent.active_pokemon else 0
        self.state[oa_pokemon_can_retreat] = 1 if (opponent.active_pokemon and opponent.active_pokemon.can_retreat) else 0
        self.state[oa_pokemon_damage_nerf] = opponent.active_pokemon.damage_nerf if opponent.active_pokemon else 0
        self.state[oa_pokemon_damage_taken] = opponent.active_pokemon.damage_taken if opponent.active_pokemon else 0

        # Status Effects
        self.state[oa_pokemon_status_poisoned] = 1 if (opponent.active_pokemon and opponent.active_pokemon.status_poisoned) else 0
        self.state[oa_pokemon_status_burned] = 1 if (opponent.active_pokemon and opponent.active_pokemon.status_burned) else 0
        self.state[oa_pokemon_status_paralyzed] = 1 if (opponent.active_pokemon and opponent.active_pokemon.status_paralyzed) else 0
        self.state[oa_pokemon_status_asleep] = 1 if (opponent.active_pokemon and opponent.active_pokemon.status_asleep) else 0
        self.state[oa_pokemon_status_confused] = 1 if (opponent.active_pokemon and opponent.active_pokemon.status_confused) else 0
        self.state[oa_pokemon_status_frozen] = 1 if (opponent.active_pokemon and opponent.active_pokemon.status_frozen) else 0
        
        # Energy on Active Pokémon
        self.state[oa_pokemon_energy_grass] = opponent.active_pokemon.equipped_energies['grass'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_fire] = opponent.active_pokemon.equipped_energies['fire'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_water] = opponent.active_pokemon.equipped_energies['water'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_lightning] = opponent.active_pokemon.equipped_energies['lightning'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_psychic] = opponent.active_pokemon.equipped_energies['psychic'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_fighting] = opponent.active_pokemon.equipped_energies['fighting'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_darkness] = opponent.active_pokemon.equipped_energies['darkness'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_metal] = opponent.active_pokemon.equipped_energies['metal'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_fairy] = opponent.active_pokemon.equipped_energies['fairy'] if opponent.active_pokemon else 0
        self.state[oa_pokemon_energy_normal] = opponent.active_pokemon.equipped_energies['normal'] if opponent.active_pokemon else 0

        # Bench Pokémon 1
        self.state[ob1_pokemon_id] = opponent.bench_pokemons[0].id if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_element] = ENERGY_TYPES[opponent.bench_pokemons[0].element] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_stage] = STAGES[opponent.bench_pokemons[0].stage] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_max_hp] = opponent.bench_pokemons[0].max_hp if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_attack_1] = opponent.bench_pokemons[0].attacks[0].id if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_attack_2] = opponent.bench_pokemons[0].attacks[1].id if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_retreat_cost] = opponent.bench_pokemons[0].retreat_cost if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_weakness] = ENERGY_TYPES[opponent.bench_pokemons[0].weakness] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_ability] = opponent.bench_pokemons[0].abilities[0].id if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_evolves_from] = opponent.bench_pokemons[0].evolves_from.id if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_is_ex] = 1 if (opponent.bench_pokemons and opponent.bench_pokemons[0] and opponent.bench_pokemons[0].is_ex) else 0
        self.state[ob1_pokemon_poketool_id] = opponent.bench_pokemons[0].poketool.id if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_can_retreat] = 1 if (opponent.bench_pokemons and opponent.bench_pokemons[0] and opponent.bench_pokemons[0].can_retreat) else 0
        self.state[ob1_pokemon_damage_nerf] = opponent.bench_pokemons[0].damage_nerf if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_damage_taken] = opponent.bench_pokemons[0].damage_taken if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0

        # Energy on Bench Pokémon 1
        self.state[ob1_pokemon_energy_grass] = opponent.bench_pokemons[0].equipped_energies['grass'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_fire] = opponent.bench_pokemons[0].equipped_energies['fire'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_water] = opponent.bench_pokemons[0].equipped_energies['water'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_lightning] = opponent.bench_pokemons[0].equipped_energies['lightning'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_psychic] = opponent.bench_pokemons[0].equipped_energies['psychic'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_fighting] = opponent.bench_pokemons[0].equipped_energies['fighting'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_darkness] = opponent.bench_pokemons[0].equipped_energies['darkness'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_metal] = opponent.bench_pokemons[0].equipped_energies['metal'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_fairy] = opponent.bench_pokemons[0].equipped_energies['fairy'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        self.state[ob1_pokemon_energy_normal] = opponent.bench_pokemons[0].equipped_energies['normal'] if opponent.bench_pokemons and opponent.bench_pokemons[0] else 0
        
        # Bench Pokémon 2
        self.state[ob2_pokemon_id] = opponent.bench_pokemons[1].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_element] = ENERGY_TYPES[opponent.bench_pokemons[1].element] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_stage] = STAGES[opponent.bench_pokemons[1].stage] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_max_hp] = opponent.bench_pokemons[1].max_hp if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_attack_1] = opponent.bench_pokemons[1].attacks[0].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_attack_2] = opponent.bench_pokemons[1].attacks[1].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_retreat_cost] = opponent.bench_pokemons[1].retreat_cost if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_weakness] = ENERGY_TYPES[opponent.bench_pokemons[1].weakness] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_ability] = opponent.bench_pokemons[1].abilities[0].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_evolves_from] = opponent.bench_pokemons[1].evolves_from.id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_is_ex] = 1 if (opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] and opponent.bench_pokemons[1].is_ex) else 0
        self.state[ob2_pokemon_poketool_id] = opponent.bench_pokemons[1].poketool.id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_can_retreat] = 1 if (opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] and opponent.bench_pokemons[1].can_retreat) else 0
        self.state[ob2_pokemon_damage_nerf] = opponent.bench_pokemons[1].damage_nerf if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_damage_taken] = opponent.bench_pokemons[1].damage_taken if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0

        # Energy on Bench Pokémon 2
        self.state[ob2_pokemon_energy_grass] = opponent.bench_pokemons[1].equipped_energies['grass'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_fire] = opponent.bench_pokemons[1].equipped_energies['fire'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_water] = opponent.bench_pokemons[1].equipped_energies['water'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_lightning] = opponent.bench_pokemons[1].equipped_energies['lightning'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_psychic] = opponent.bench_pokemons[1].equipped_energies['psychic'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_fighting] = opponent.bench_pokemons[1].equipped_energies['fighting'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_darkness] = opponent.bench_pokemons[1].equipped_energies['darkness'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_metal] = opponent.bench_pokemons[1].equipped_energies['metal'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_fairy] = opponent.bench_pokemons[1].equipped_energies['fairy'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0
        self.state[ob2_pokemon_energy_normal] = opponent.bench_pokemons[1].equipped_energies['normal'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 1 and opponent.bench_pokemons[1] else 0

        # Bench Pokémon 3
        self.state[ob3_pokemon_id] = opponent.bench_pokemons[2].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_element] = ENERGY_TYPES[opponent.bench_pokemons[2].element] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_stage] = STAGES[opponent.bench_pokemons[2].stage] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_max_hp] = opponent.bench_pokemons[2].max_hp if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_attack_1] = opponent.bench_pokemons[2].attacks[0].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_attack_2] = opponent.bench_pokemons[2].attacks[1].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_retreat_cost] = opponent.bench_pokemons[2].retreat_cost if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_weakness] = ENERGY_TYPES[opponent.bench_pokemons[2].weakness] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_ability] = opponent.bench_pokemons[2].abilities[0].id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_evolves_from] = opponent.bench_pokemons[2].evolves_from.id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_is_ex] = 1 if (opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] and opponent.bench_pokemons[2].is_ex) else 0
        self.state[ob3_pokemon_poketool_id] = opponent.bench_pokemons[2].poketool.id if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_can_retreat] = 1 if (opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] and opponent.bench_pokemons[2].can_retreat) else 0
        self.state[ob3_pokemon_damage_nerf] = opponent.bench_pokemons[2].damage_nerf if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_damage_taken] = opponent.bench_pokemons[2].damage_taken if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0

        # Energy on Bench Pokémon 3
        self.state[ob3_pokemon_energy_grass] = opponent.bench_pokemons[2].equipped_energies['grass'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_fire] = opponent.bench_pokemons[2].equipped_energies['fire'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_water] = opponent.bench_pokemons[2].equipped_energies['water'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_lightning] = opponent.bench_pokemons[2].equipped_energies['lightning'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_psychic] = opponent.bench_pokemons[2].equipped_energies['psychic'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_fighting] = opponent.bench_pokemons[2].equipped_energies['fighting'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_darkness] = opponent.bench_pokemons[2].equipped_energies['darkness'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_metal] = opponent.bench_pokemons[2].equipped_energies['metal'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_fairy] = opponent.bench_pokemons[2].equipped_energies['fairy'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        self.state[ob3_pokemon_energy_normal] = opponent.bench_pokemons[2].equipped_energies['normal'] if opponent.bench_pokemons and len(opponent.bench_pokemons) > 2 and opponent.bench_pokemons[2] else 0
        
        # Opponent Original Cards
        self.state[o_original_card_id_0] = opponent._original_deck[0].id
        self.state[o_original_card_id_1] = opponent._original_deck[1].id
        self.state[o_original_card_id_2] = opponent._original_deck[2].id
        self.state[o_original_card_id_3] = opponent._original_deck[3].id
        self.state[o_original_card_id_4] = opponent._original_deck[4].id
        self.state[o_original_card_id_5] = opponent._original_deck[5].id
        self.state[o_original_card_id_6] = opponent._original_deck[6].id
        self.state[o_original_card_id_7] = opponent._original_deck[7].id
        self.state[o_original_card_id_8] = opponent._original_deck[8].id
        self.state[o_original_card_id_9] = opponent._original_deck[9].id
        self.state[o_original_card_id_10] = opponent._original_deck[10].id
        self.state[o_original_card_id_11] = opponent._original_deck[11].id
        self.state[o_original_card_id_12] = opponent._original_deck[12].id
        self.state[o_original_card_id_13] = opponent._original_deck[13].id
        self.state[o_original_card_id_14] = opponent._original_deck[14].id
        self.state[o_original_card_id_15] = opponent._original_deck[15].id
        self.state[o_original_card_id_16] = opponent._original_deck[16].id
        self.state[o_original_card_id_17] = opponent._original_deck[17].id
        self.state[o_original_card_id_18] = opponent._original_deck[18].id
        self.state[o_original_card_id_19] = opponent._original_deck[19].id

        self.state[o_discard_pile_card_id_0] = opponent.discard_pile[0].id if opponent.discard_pile and len(opponent.discard_pile) > 0 else 0
        self.state[o_discard_pile_card_id_1] = opponent.discard_pile[1].id if opponent.discard_pile and len(opponent.discard_pile) > 1 else 0
        self.state[o_discard_pile_card_id_2] = opponent.discard_pile[2].id if opponent.discard_pile and len(opponent.discard_pile) > 2 else 0
        self.state[o_discard_pile_card_id_3] = opponent.discard_pile[3].id if opponent.discard_pile and len(opponent.discard_pile) > 3 else 0
        self.state[o_discard_pile_card_id_4] = opponent.discard_pile[4].id if opponent.discard_pile and len(opponent.discard_pile) > 4 else 0
        self.state[o_discard_pile_card_id_5] = opponent.discard_pile[5].id if opponent.discard_pile and len(opponent.discard_pile) > 5 else 0
        self.state[o_discard_pile_card_id_6] = opponent.discard_pile[6].id if opponent.discard_pile and len(opponent.discard_pile) > 6 else 0
        self.state[o_discard_pile_card_id_7] = opponent.discard_pile[7].id if opponent.discard_pile and len(opponent.discard_pile) > 7 else 0
        self.state[o_discard_pile_card_id_8] = opponent.discard_pile[8].id if opponent.discard_pile and len(opponent.discard_pile) > 8 else 0
        self.state[o_discard_pile_card_id_9] = opponent.discard_pile[9].id if opponent.discard_pile and len(opponent.discard_pile) > 9 else 0
        self.state[o_discard_pile_card_id_10] = opponent.discard_pile[10].id if opponent.discard_pile and len(opponent.discard_pile) > 10 else 0
        self.state[o_discard_pile_card_id_11] = opponent.discard_pile[11].id if opponent.discard_pile and len(opponent.discard_pile) > 11 else 0
        self.state[o_discard_pile_card_id_12] = opponent.discard_pile[12].id if opponent.discard_pile and len(opponent.discard_pile) > 12 else 0
        self.state[o_discard_pile_card_id_13] = opponent.discard_pile[13].id if opponent.discard_pile and len(opponent.discard_pile) > 13 else 0
        self.state[o_discard_pile_card_id_14] = opponent.discard_pile[14].id if opponent.discard_pile and len(opponent.discard_pile) > 14 else 0
        self.state[o_discard_pile_card_id_15] = opponent.discard_pile[15].id if opponent.discard_pile and len(opponent.discard_pile) > 15 else 0
        self.state[o_discard_pile_card_id_16] = opponent.discard_pile[16].id if opponent.discard_pile and len(opponent.discard_pile) > 16 else 0
        self.state[o_discard_pile_card_id_17] = opponent.discard_pile[17].id if opponent.discard_pile and len(opponent.discard_pile) > 17 else 0
        self.state[o_discard_pile_card_id_18] = opponent.discard_pile[18].id if opponent.discard_pile and len(opponent.discard_pile) > 18 else 0

        # Opponent hand card count
        self.state[p_hand_card_count] = len(player.cards_in_hand)
        self.state[p_deck_card_count] = len(player.deck)
        self.state[o_hand_card_count] = len(opponent.cards_in_hand) if opponent.cards_in_hand else 0
        self.state[o_deck_card_count] = len(opponent.deck) if opponent.deck else 0
        self.state[p_energy_type_available_to_attach] = ENERGY_TYPES[player.energy_zone[0]] if player.energy_zone else 0
        self.state[p_next_turn_energy_type_available_to_attach] = ENERGY_TYPES[player.energy_zone[1]] if player.energy_zone else 0
        self.state[o_energy_type_available_to_attach] = ENERGY_TYPES[opponent.energy_zone[0]] if opponent.energy_zone else 0
        self.state[o_next_turn_energy_type_available_to_attach] = ENERGY_TYPES[opponent.energy_zone[1]] if opponent.energy_zone else 0
        self.state[p_score] = player.points
        self.state[o_score] = opponent.points
        self.state[turn_number] = self.turn
        
        return self.state