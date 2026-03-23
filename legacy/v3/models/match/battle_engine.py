import random
import sys
import os
from typing import List, Dict, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum

from v3.models.match.player import Player
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card
from v3.models.cards.energy import Energy
from v3.models.cards.attack import Attack
from v3.models.match.game_rules import GameRules, GamePhase

"""Core battle engine - simplified and modular"""
class BattleEngine:
    def __init__(self, player1: Player, player2: Player, debug: bool = False):
        self.players = [player1, player2]
        self.player1 = player1
        self.player2 = player2
        self.debug = debug

        self.current_player_index = 0
        self.turn = 0
        self.phase = GamePhase.SETUP
        self.first_player_first_turn = False  # Track if first player is on their first turn (no energy attachment)
        self.first_player_index = None  # Track which player goes first
        self.last_action_taken = None  # Track last action taken for debug display
    
    def start_battle(self) -> Optional[Player]:
        """Main battle execution"""
        try:
            self._setup_game()
            
            # Display initial board in debug mode
            if self.debug:
                current = self._get_current_player()
                opponent = self._get_opponent(current)
                board_view = self.generate_board_view(current, opponent)
                print("\n" + board_view + "\n")
            
            while not self._is_game_over():
                self._execute_turn()
            return self._determine_winner()
        except Exception as e:
            self.log(f"Battle error: {e}")
            import traceback
            if self.debug:
                traceback.print_exc()
            return None
        


    
    def log(self, message: str):
        """Log a message. Future enhancement: Make logging agent-aware (human vs AI)"""
        if self.debug:
            print(f"[Turn {self.turn}] {message}")
        
    #### PRIVATE METHODS ####

    def _setup_game(self):
        """Setup initial game state"""
        self.log("Setting up battle...")

        self._determine_first_player()
        
        # Setup both players
        for player in self.players:
            self._setup_player(player)

        # Each player gets a turn zero
        for i in range(2):
            current = self._get_current_player()
            opponent = self._get_opponent(current)
            self._turn_zero(current, opponent)
            self._switch_players()
    
    def _determine_first_player(self):
        """Determine which player goes first (coin toss)"""
        # Coin toss: randomly determine first player
        self.first_player_index = random.randint(0, 1)
        self.current_player_index = self.first_player_index
        self.log(f"Coin toss: {self.players[self.first_player_index].name} goes first!")
    
    def _setup_player(self, player: Player):
        """Setup individual player by drawing initial hand and adding energies to energy zone"""
        # Draw initial hand
        player.draw_inital_hand()
        player._add_energies_to_energy_zone()

    def _switch_players(self):
        self.current_player_index = 1 - self.current_player_index

    def _get_current_player(self) -> Player:
        return self.players[self.current_player_index]
    
    def _get_opponent(self, player: Optional[Player] = None) -> Player:
        """Get the opponent player. If player is provided, returns the other player."""
        if player is None:
            return self.players[1 - self.current_player_index]
        return self.player2 if player == self.player1 else self.player1
    

    def _turn_zero(self, player: Player, opponent: Player):
        """Execute turn zero for a player - must play at least 1 basic Pokemon to active"""
        self.log(f"=== Setup Phase - {player.name} ===")
        player_state = self._get_player_state(player, opponent)
        self.log(f"{player_state}")
        
        # Display board for human players or in debug mode
        if self.debug or (hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human):
            board_view = self.generate_board_view(player, opponent)
            
            # Clear screen for human players (but not in debug mode)
            if hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human and not self.debug:
                import os
                os.system('clear' if os.name != 'nt' else 'cls')
            
            print("\n" + board_view + "\n")
        
        # Player must play at least 1 basic Pokemon to active
        # Keep looping until they have an active Pokemon
        max_actions = 50  # Prevent infinite loops
        action_count = 0
        
        while player.active_pokemon is None and action_count < max_actions:
            # Get Actions
            actions = player._get_turn_zero_actions()
            
            # Only allow active actions - filter out bench and end_turn
            active_actions = [a for a in actions if "_active" in a]
            if not active_actions:
                # No valid actions - this shouldn't happen if deck has basic Pokemon
                self.log(f"ERROR: {player.name} has no basic Pokemon to play to active!")
                break
            
            actions = active_actions  # Only allow active actions

            # Display board again with filtered actions for human players
            if hasattr(player.agent, 'is_human') and player.agent.is_human:
                board_view = self.generate_board_view(player, opponent)
                # Clear screen for human players (but not in debug mode)
                if not self.debug:
                    import os
                    os.system('clear' if os.name != 'nt' else 'cls')
                print("\n" + board_view + "\n")
            
            # Play Action - handle different agent interfaces
            action_str = None
            if hasattr(player.agent, 'play_action'):
                # HumanAgent interface - pass the filtered actions
                action_str = player.agent.play_action(actions)
            elif hasattr(player.agent, 'get_action'):
                # RandomAgent interface - convert to string
                action_indices = list(range(len(actions)))
                action_index = player.agent.get_action({}, action_indices)
                if action_index is not None and 0 <= action_index < len(actions):
                    action_str = actions[action_index]
                else:
                    # Force play to active if available
                    active_actions = [a for a in actions if "_active" in a]
                    if active_actions:
                        action_str = active_actions[0]
                    else:
                        action_str = actions[0] if actions else "end_turn"
            else:
                # Default: play first available action
                active_actions = [a for a in actions if "_active" in a]
                action_str = active_actions[0] if active_actions else (actions[0] if actions else "end_turn")
            
            # Handle None return from agent
            if action_str is None:
                action_str = "end_turn"
            
            # Execute the action
            self.log(f"{player.name} chose action: {action_str}")
            if action_str != "end_turn":
                self._execute_action(action_str, player)
                action_count += 1
            else:
                break
        
        # Now allow playing more Pokemon to bench (optional)
        action_count = 0
        while action_count < max_actions:
            actions = player._get_turn_zero_actions()
            
            # Only allow bench actions and end_turn now
            bench_actions = [a for a in actions if "_bench" in a]
            if not bench_actions:
                # No more bench actions available
                break
            
            # Add end_turn option
            if "end_turn" not in actions:
                actions.append("end_turn")
            
            # Limit bench actions to available slots only
            valid_bench_actions = []
            for bench_action_str in bench_actions:
                # Validate that the bench slot is actually empty
                try:
                    from v3.models.match.actions.play_pokemon import PlayPokemonAction
                    action_obj = PlayPokemonAction.from_string(bench_action_str, player)
                    is_valid, error = action_obj.validate(player, self)
                    if is_valid:
                        valid_bench_actions.append(bench_action_str)
                except:
                    pass
            
            if not valid_bench_actions:
                # No valid bench actions
                break
            
            # Add end_turn to valid actions
            valid_actions = valid_bench_actions + ["end_turn"]
            
            # Display board again with filtered actions for human players
            if hasattr(player.agent, 'is_human') and player.agent.is_human:
                board_view = self.generate_board_view(player, opponent)
                # Clear screen for human players (but not in debug mode)
                if not self.debug:
                    import os
                    os.system('clear' if os.name != 'nt' else 'cls')
                print("\n" + board_view + "\n")
            
            # Get action from agent
            action_str = None
            if hasattr(player.agent, 'play_action'):
                action_str = player.agent.play_action(valid_actions)
            elif hasattr(player.agent, 'get_action'):
                action_indices = list(range(len(valid_actions)))
                action_index = player.agent.get_action({}, action_indices)
                if action_index is not None and 0 <= action_index < len(valid_actions):
                    action_str = valid_actions[action_index]
                else:
                    action_str = "end_turn"
            else:
                action_str = "end_turn"
            
            # Handle None return from agent
            if action_str is None:
                action_str = "end_turn"
            
            if action_str == "end_turn":
                break
            
            self.log(f"{player.name} chose action: {action_str}")
            # Validate before executing
            action_obj = None
            try:
                from v3.models.match.actions.play_pokemon import PlayPokemonAction
                action_obj = PlayPokemonAction.from_string(action_str, player)
                is_valid, error = action_obj.validate(player, self)
                if is_valid:
                    self._execute_action(action_str, player)
                    action_count += 1
                else:
                    # Invalid action - end turn
                    if self.debug:
                        self.log(f"DEBUG: Invalid bench action: {error}")
                    break
            except Exception as e:
                if self.debug:
                    self.log(f"DEBUG: Error validating bench action: {e}")
                break
        
        # Ensure active Pokemon is set
        if player.active_pokemon is None:
            self.log(f"ERROR: {player.name} did not set an active Pokemon during setup!")
        
        self.log(f"{player.name} finished setup phase")

    def _get_player_state(self, player: Player, opponent: Player) -> str:
        """Get the state for a player as a string representation of the board"""
        return self.generate_board_view(player, opponent)
    
    def generate_board_view(self, player: Player, opponent: Player, actions: Optional[List[str]] = None) -> str:
        """Generate a complete board view from the player's perspective with ASCII art
        
        Args:
            player: The player whose perspective to show
            opponent: The opponent player
            actions: Optional list of actions to display. If None, will get actions from player.
        """
        lines = []
        
        # Header with turn number (right-aligned)
        header_line = f"  POKEMON TCG BATTLE - {player.name}'s Turn"
        turn_text = f"Turn {self.turn}"
        # Calculate spacing: 100 (total width) - header length - turn length
        spacing = 100 - len(header_line) - len(turn_text)
        if spacing < 0:
            spacing = 0
        header_with_turn = header_line + " " * spacing + turn_text
        
        lines.append("=" * 100)
        lines.append(header_with_turn)
        lines.append("=" * 100)
        lines.append("")
        
        # Opponent's field info
        opponent_energy = self._format_energy_type(opponent.energy_zone_current_energy)
        next_opponent_energy = self._format_energy_type(opponent.energy_zone_next_energy)
        lines.append(f"OPPONENT: {opponent.name}  |  Points: {opponent.points}  |  Next Energy: {next_opponent_energy}  |  Cards in hand: {len(opponent.cards_in_hand)}  |  Deck: {len(opponent.deck)}")
        lines.append("")
        
        # Opponent's bench (side by side)
        opponent_bench_cards = []
        for i, pokemon in enumerate(opponent.bench_pokemons):
            if pokemon:
                opponent_bench_cards.append(self._format_pokemon_card(pokemon, compact=True))
            else:
                opponent_bench_cards.append(self._format_empty_card())
        
        # Display opponent's bench in a row
        if opponent_bench_cards:
            bench_lines = self._combine_cards_horizontally(opponent_bench_cards)
            for line in bench_lines:
                lines.append(line)
            lines.append("")
        
        # Opponent's active Pokemon (centered)
        if opponent.active_pokemon:
            active_card = self._format_pokemon_card(opponent.active_pokemon, compact=False)
            # Center the active Pokemon
            card_width = max(len(line) for line in active_card) if active_card else 0
            padding = (100 - card_width) // 2
            for line in active_card:
                lines.append(" " * padding + line)
        else:
            empty_card = self._format_empty_card()
            card_width = max(len(line) for line in empty_card) if empty_card else 0
            padding = (100 - card_width) // 2
            for line in empty_card:
                lines.append(" " * padding + line)
        
        lines.append("")
        lines.append("=" * 100)
        lines.append("")
        
        # Player's active Pokemon (centered)
        if player.active_pokemon:
            active_card = self._format_pokemon_card(player.active_pokemon, compact=False)
            card_width = max(len(line) for line in active_card) if active_card else 0
            padding = (100 - card_width) // 2
            for line in active_card:
                lines.append(" " * padding + line)
        else:
            empty_card = self._format_empty_card()
            card_width = max(len(line) for line in empty_card) if empty_card else 0
            padding = (100 - card_width) // 2
            for line in empty_card:
                lines.append(" " * padding + line)
        
        lines.append("")
        
        # Player's bench (side by side)
        player_bench_cards = []
        for i, pokemon in enumerate(player.bench_pokemons):
            if pokemon:
                player_bench_cards.append(self._format_pokemon_card(pokemon, compact=True))
            else:
                player_bench_cards.append(self._format_empty_card())
        
        # Display player's bench in a row
        if player_bench_cards:
            bench_lines = self._combine_cards_horizontally(player_bench_cards)
            for line in bench_lines:
                lines.append(line)
            lines.append("")
        
        # Player's field info
        player_energy = self._format_energy_type(player.energy_zone_current_energy)
        next_player_energy = self._format_energy_type(player.energy_zone_next_energy)
        lines.append(f"YOU: {player.name}  |  Points: {player.points}  |  Next Energy: {next_player_energy}  |  Cards in hand: {len(player.cards_in_hand)}  |  Deck: {len(player.deck)}")
        lines.append("")
        
        # Player's hand
        lines.append("Cards in hand:")
        if player.cards_in_hand:
            for i, card in enumerate(player.cards_in_hand, 1):
                card_str = self._format_hand_card(card)
                lines.append(f"  {i}. {card_str}")
        else:
            lines.append("  [No cards in hand]")
        lines.append("")
        
        # Available actions
        # If actions were provided, use them; otherwise get from player
        if actions is None:
            # During setup phase (turn zero), use turn zero actions
            if self.phase == GamePhase.SETUP or self.turn == 0:
                actions = player._get_turn_zero_actions() if hasattr(player, '_get_turn_zero_actions') else []
                
                # If no active Pokemon yet, only show actions to play to active
                if player.active_pokemon is None:
                    actions = [a for a in actions if "_active" in a]
                # If active Pokemon exists, only show bench actions and end_turn
                else:
                    actions = [a for a in actions if "_bench" in a or a == "end_turn"]
            else:
                actions = player._get_actions() if hasattr(player, '_get_actions') else []
                
                # Filter out energy attachment on first player's first turn (for display)
                if self.first_player_first_turn:
                    actions = [a for a in actions if not a.startswith("attach_energy_")]
        
        if actions:
            # Show last action taken in debug mode
            if self.debug and self.last_action_taken:
                formatted_action = self._format_action_for_display(self.last_action_taken, player)
                lines.append(f"Last action taken: {formatted_action}")
                lines.append("")
            
            lines.append("Available actions:")
            
            # Format all actions (may be multi-line for attacks)
            formatted_actions = []
            for action in actions:
                formatted_action = self._format_action_for_display(action, player)
                # Convert to list if it's a string
                if isinstance(formatted_action, str):
                    formatted_actions.append([formatted_action])
                else:
                    formatted_actions.append(formatted_action)
            
            # Display in two columns (10 per column, 20 total)
            max_display = 20
            actions_to_show = formatted_actions[:max_display]
            total_actions = len(formatted_actions)
            
            # Calculate column widths (accounting for numbering and spacing)
            # Left column: "  X. " (5 chars) + action text
            # Right column: "  X. " (5 chars) + action text
            # Separator: " | " (3 chars)
            # Total width: 100 chars
            # Increased width to allow full descriptions
            left_col_width = 60  # Increased from 48 to allow full descriptions
            right_col_width = 60  # Increased from 48
            
            # Split into two columns
            left_column = actions_to_show[:10]
            right_column = actions_to_show[10:20]
            
            # Display in two columns (handle multi-line actions)
            max_rows = max(len(left_column), len(right_column))
            for row in range(max_rows):
                left_action_lines = left_column[row] if row < len(left_column) else []
                right_action_lines = right_column[row] if row < len(right_column) else []
                
                # Get the maximum number of lines for this row (for multi-line actions)
                max_lines = max(len(left_action_lines) if left_action_lines else 0, 
                              len(right_action_lines) if right_action_lines else 0)
                
                # Display each line of the action
                for line_idx in range(max_lines):
                    left_line = left_action_lines[line_idx] if left_action_lines and line_idx < len(left_action_lines) else ""
                    right_line = right_action_lines[line_idx] if right_action_lines and line_idx < len(right_action_lines) else ""
                    
                    # Format left column
                    if left_line:
                        if line_idx == 0:
                            left_num = row + 1
                            left_text = f"  {left_num}. {left_line}"
                        else:
                            # Indent continuation lines
                            left_text = f"      {left_line}"
                        # Truncate if too long
                        if len(left_text) > left_col_width:
                            left_text = left_text[:left_col_width-3] + "..."
                    else:
                        left_text = ""
                    
                    # Format right column
                    if right_line:
                        if line_idx == 0:
                            right_num = row + 11
                            right_text = f"  {right_num}. {right_line}"
                        else:
                            # Indent continuation lines
                            right_text = f"      {right_line}"
                        # Truncate if too long
                        if len(right_text) > right_col_width:
                            right_text = right_text[:right_col_width-3] + "..."
                    else:
                        right_text = ""
                    
                    # Combine with separator
                    if left_text or right_text:
                        # Pad left column to fixed width
                        left_padded = left_text.ljust(left_col_width)
                        line = f"{left_padded} | {right_text}" if right_text else left_padded
                        lines.append(line)
            
            # Show message if there are more actions
            if total_actions > max_display:
                lines.append(f"  ... and {total_actions - max_display} more actions")
        lines.append("")
        
        lines.append("=" * 100)
        
        return "\n".join(lines)
    
    def _indent_text(self, text: str, spaces: int) -> str:
        """Helper method to indent multi-line text"""
        indent = " " * spaces
        return "\n".join(indent + line for line in text.split("\n"))
    
    def _format_energy_type(self, energy_type) -> str:
        """Format energy type for display - returns full name"""
        if energy_type is None:
            return "None"
        
        # Handle Energy.Type enum
        from v3.models.cards.energy import Energy
        if isinstance(energy_type, Energy.Type):
            # Map enum to full name
            energy_map = {
                Energy.Type.FIRE: 'Fire',
                Energy.Type.WATER: 'Water',
                Energy.Type.GRASS: 'Grass',
                Energy.Type.ELECTRIC: 'Electric',
                Energy.Type.PSYCHIC: 'Psychic',
                Energy.Type.ROCK: 'Rock',
                Energy.Type.DARK: 'Dark',
                Energy.Type.METAL: 'Metal',
                Energy.Type.NORMAL: 'Colorless',  # Normal/Colorless energy
            }
            return energy_map.get(energy_type, str(energy_type).title())
        
        # Fallback: try string matching
        energy_str = str(energy_type).lower()
        energy_map = {
            'fire': 'Fire',
            'water': 'Water',
            'grass': 'Grass',
            'electric': 'Electric',
            'lightning': 'Electric',
            'psychic': 'Psychic',
            'rock': 'Rock',
            'fighting': 'Rock',
            'dark': 'Dark',
            'darkness': 'Dark',
            'metal': 'Metal',
            'normal': 'Colorless',
            'colorless': 'Colorless'
        }
        return energy_map.get(energy_str, str(energy_type).title())
    
    def _format_energy_type_abbrev(self, energy_type) -> str:
        """Format energy type as single-letter abbreviation for card display (e.g., G, F, C)"""
        if energy_type is None:
            return "?"
        
        # Handle Energy.Type enum
        from v3.models.cards.energy import Energy
        if isinstance(energy_type, Energy.Type):
            # Map enum to single letter
            energy_map = {
                Energy.Type.FIRE: 'F',
                Energy.Type.WATER: 'W',
                Energy.Type.GRASS: 'G',
                Energy.Type.ELECTRIC: 'E',
                Energy.Type.PSYCHIC: 'P',
                Energy.Type.ROCK: 'R',
                Energy.Type.DARK: 'D',
                Energy.Type.METAL: 'M',
                Energy.Type.NORMAL: 'C',  # Colorless
            }
            return energy_map.get(energy_type, str(energy_type)[0].upper())
        
        # Fallback: try string matching
        energy_str = str(energy_type).lower()
        energy_map = {
            'fire': 'F',
            'water': 'W',
            'grass': 'G',
            'electric': 'E',
            'lightning': 'E',
            'psychic': 'P',
            'rock': 'R',
            'fighting': 'R',
            'dark': 'D',
            'darkness': 'D',
            'metal': 'M',
            'normal': 'C',
            'colorless': 'C'
        }
        return energy_map.get(energy_str, str(energy_type)[0].upper())
    
    def _format_pokemon_card(self, pokemon: Pokemon, compact: bool = False) -> List[str]:
        """Format a Pokemon card as ASCII art"""
        from v3.models.cards.energy import Energy
        
        lines = []
        card_width = 40 if compact else 50
        
        # Get Pokemon info
        max_hp = pokemon.max_health()
        current_hp = pokemon.current_health()
        hp_str = f"{current_hp}/{max_hp} HP"
        
        # Format element/type
        element_str = self._format_energy_type(pokemon.element)
        if pokemon.subtype == Card.Subtype.BASIC:
            stage_str = "Basic"
        elif pokemon.subtype == Card.Subtype.STAGE_1:
            stage_str = "Stage 1"
        elif pokemon.subtype == Card.Subtype.STAGE_2:
            stage_str = "Stage 2"
        else:
            stage_str = str(pokemon.subtype)
        
        # Format attached energy (use abbreviations: 1G, 2F, etc.)
        energy_parts = []
        for energy_type, count in pokemon.equipped_energies.items():
            if count > 0:
                energy_symbol = self._format_energy_type_abbrev(energy_type)
                energy_parts.append(f"{count}{energy_symbol}")
        energy_str = f"({' '.join(energy_parts)})" if energy_parts else "(No Energy)"
        
        # Format name (truncate if too long)
        name = pokemon.name
        if len(name) > card_width - 10:
            name = name[:card_width - 13] + "..."
        
        # Top border
        lines.append("-" * card_width)
        
        # Name (left) and HP (right) on same line
        name_display = name[:card_width-12] if len(name) <= card_width-12 else name[:card_width-15] + "..."
        # Don't truncate HP - it's important information (max 15 chars should be enough: "999/999 HP")
        hp_display = hp_str
        # Calculate spacing: card_width - 4 (borders + spaces) - name_len - hp_len
        name_len = len(name_display)
        hp_len = len(hp_display)
        spacing = card_width - 4 - name_len - hp_len
        if spacing < 0:
            # If HP is too long, truncate name instead
            name_display = name[:card_width - hp_len - 4] if len(name) > card_width - hp_len - 4 else name
            name_len = len(name_display)
            spacing = card_width - 4 - name_len - hp_len
        lines.append(f"| {name_display}{' ' * spacing}{hp_display} |")
        
        # Type (left) and Stage (right) on same line
        type_display = element_str[:card_width-14] if len(element_str) <= card_width-14 else element_str[:card_width-17] + "..."
        stage_display = stage_str[:10] if len(stage_str) <= 10 else stage_str[:7] + "..."
        type_len = len(type_display)
        stage_len = len(stage_display)
        spacing = card_width - 4 - type_len - stage_len
        lines.append(f"| {type_display}{' ' * spacing}{stage_display} |")
        
        # Attached Energy
        energy_padding = card_width - 4
        energy_display = energy_str[:energy_padding] if len(energy_str) <= energy_padding else energy_str[:energy_padding-3] + "..."
        lines.append(f"| {energy_display:<{energy_padding}} |")
        
        # Empty line
        lines.append(f"|{' ' * (card_width-2)}|")
        
        if not compact:
            # Abilities
            if pokemon.abilities:
                for ability in pokemon.abilities:
                    if ability and ability.effect:
                        effect_text = ability.effect[:card_width-15]
                        ability_line = f"| Ability: {effect_text:<{card_width-15}} |"
                        lines.append(ability_line[:card_width-1] + "|")
            
            # Attacks
            if pokemon.attacks:
                for attack in pokemon.attacks:
                    # Format energy cost (use abbreviations: 1G, 1C, etc.)
                    cost_parts = []
                    attack_cost = attack.cost.cost if hasattr(attack.cost, 'cost') else attack.cost
                    for energy_type, amount in attack_cost.items():
                        if amount > 0:
                            energy_symbol = self._format_energy_type_abbrev(energy_type)
                            cost_parts.append(f"{amount}{energy_symbol}")
                    cost_str = " ".join(cost_parts) if cost_parts else "0"
                    
                    damage = attack.damage if attack.damage else 0
                    attack_name = attack.name[:15] if len(attack.name) <= 15 else attack.name[:12] + "..."
                    
                    # Format attack: energy cost (left), name (center), damage (right)
                    cost_display = f"({cost_str})"[:8] if len(f"({cost_str})") <= 8 else f"({cost_str})"[:5] + "..."
                    name_display = attack_name[:card_width-22] if len(attack_name) <= card_width-22 else attack_name[:card_width-25] + "..."
                    damage_display = f"{damage} dmg"[:8] if len(f"{damage} dmg") <= 8 else f"{damage} dmg"[:5] + "..."
                    
                    # Calculate spacing for center alignment (accounting for border spaces)
                    cost_len = len(cost_display)
                    name_len = len(name_display)
                    damage_len = len(damage_display)
                    total_used = cost_len + name_len + damage_len
                    available_space = card_width - 4 - total_used  # -4 for border spaces
                    
                    # Split available space: half before name, half after
                    left_spacing = available_space // 2
                    right_spacing = available_space - left_spacing
                    
                    lines.append(f"| {cost_display}{' ' * left_spacing}{name_display}{' ' * right_spacing}{damage_display} |")
                    
                    # Attack effect if any
                    if attack.ability and attack.ability.effect:
                        effect_padding = card_width - 4
                        effect_text = attack.ability.effect[:effect_padding] if len(attack.ability.effect) <= effect_padding else attack.ability.effect[:effect_padding-3] + "..."
                        lines.append(f"| {effect_text:<{effect_padding}} |")
            
            # Weakness and Retreat
            weakness_str = ""
            if pokemon.weakness:
                weakness_str = f"Weak: {self._format_energy_type(pokemon.weakness)}"
            retreat_str = f"Retreat: {pokemon.retreat_cost}" if pokemon.retreat_cost > 0 else ""
            
            if weakness_str or retreat_str:
                stats_text = f"{weakness_str} {retreat_str}".strip()
                stats_padding = card_width - 4
                stats_display = stats_text[:stats_padding] if len(stats_text) <= stats_padding else stats_text[:stats_padding-3] + "..."
                lines.append(f"| {stats_display:<{stats_padding}} |")
        
        # Bottom border
        lines.append("-" * card_width)
        
        return lines
    
    def _format_empty_card(self) -> List[str]:
        """Format an empty card slot"""
        card_width = 40
        lines = []
        lines.append("-" * card_width)
        lines.append(f"|{' ' * (card_width-2)}|")
        lines.append(f"|{'[Empty]':^{card_width-2}}|")
        lines.append(f"|{' ' * (card_width-2)}|")
        lines.append("-" * card_width)
        return lines
    
    def _combine_cards_horizontally(self, cards: List[List[str]]) -> List[str]:
        """Combine multiple card representations side by side"""
        if not cards:
            return []
        
        # Find max height
        max_height = max(len(card) for card in cards)
        
        # Pad all cards to same height
        padded_cards = []
        for card in cards:
            card_width = max(len(line) for line in card) if card else 0
            padded = []
            for i in range(max_height):
                if i < len(card):
                    # Pad line to card width
                    line = card[i]
                    padded.append(line + " " * (card_width - len(line)))
                else:
                    padded.append(" " * card_width)
            padded_cards.append(padded)
        
        # Combine horizontally
        combined = []
        for i in range(max_height):
            line_parts = [card[i] for card in padded_cards]
            combined.append("  ".join(line_parts))  # 2 spaces between cards
        
        return combined
    
    def _format_action_for_display(self, action_str: str, player: Player) -> Union[str, List[str]]:
        """Format action string for display in human-readable form
        
        Returns:
            str: Single-line action description
            List[str]: Multi-line action description (for attacks with effects)
        """
        if action_str.startswith("play_pokemon_"):
            parts = action_str.replace("play_pokemon_", "").split("_", 1)
            if len(parts) >= 1:
                card_id = parts[0]
                position = parts[1] if len(parts) > 1 else "active"
                
                # Find card in player's hand
                card = next((c for c in player.cards_in_hand if c.id == card_id), None)
                if card:
                    if position == "active":
                        return f"Play {card.name} to Active"
                    elif position == "bench" or position.startswith("bench_"):
                        return f"Play {card.name} to Bench"
                    else:
                        return f"Play {card.name} to {position}"
        
        elif action_str.startswith("attack_"):
            parts = action_str.replace("attack_", "").split("_")
            attack_index = int(parts[0]) if parts and parts[0].isdigit() else 0
            
            if player.active_pokemon:
                pokemon = player.active_pokemon
                if pokemon.attacks and attack_index < len(pokemon.attacks):
                    attack = pokemon.attacks[attack_index]
                    damage = attack.damage if attack.damage else 0
                    
                    # Build main attack line
                    main_line = f"Attack: {attack.name} - {damage} dmg"
                    
                    # Parse effect to get description
                    effect_description = self._get_attack_effect_description(attack, player)
                    if effect_description:
                        # Return as list for multi-line display
                        return [main_line, f"   - {effect_description}"]
                    else:
                        return main_line
        
        elif action_str == "end_turn":
            return "End Turn"
        
        elif action_str.startswith("attach_energy_"):
            # Format: "attach_energy_active" or "attach_energy_bench_{i}"
            parts = action_str.replace("attach_energy_", "").split("_")
            if len(parts) >= 1:
                location = parts[0]
                if location == "active" and player.active_pokemon:
                    energy_type = self._format_energy_type(player.energy_zone_current_energy)
                    return f"Attach {energy_type} energy to {player.active_pokemon.name}"
                elif location == "bench" and len(parts) >= 2:
                    bench_num = parts[1] if parts[1].isdigit() else "?"
                    bench_pokemon = player.bench_pokemons[int(bench_num)] if bench_num.isdigit() and int(bench_num) < len(player.bench_pokemons) else None
                    if bench_pokemon:
                        energy_type = self._format_energy_type(player.energy_zone_current_energy)
                        return f"Attach {energy_type} energy to {bench_pokemon.name} (Bench {bench_num})"
        
        elif action_str.startswith("evolve_"):
            # Format: "evolve_{card_id}_{location}" where location is "active" or "bench_{i}"
            parts = action_str.replace("evolve_", "").split("_")
            if len(parts) >= 2:
                card_id = parts[0]
                # Location could be "active" or "bench" followed by a number
                if parts[1] == "active":
                    location = "active"
                    bench_num = None
                elif parts[1] == "bench" and len(parts) >= 3:
                    location = "bench"
                    bench_num = parts[2] if parts[2].isdigit() else None
                else:
                    # Try to parse as "bench_{i}" format
                    location_str = "_".join(parts[1:])
                    if location_str.startswith("bench_"):
                        location = "bench"
                        bench_num = location_str.split("_")[1] if "_" in location_str else None
                    else:
                        location = parts[1]
                        bench_num = None
                
                # Find card in player's hand
                card = next((c for c in player.cards_in_hand if c.id == card_id), None)
                if card:
                    if location == "active" and player.active_pokemon:
                        return f"Evolve {player.active_pokemon.name} to {card.name}"
                    elif location == "bench" and bench_num is not None:
                        bench_idx = int(bench_num) if bench_num.isdigit() else -1
                        if 0 <= bench_idx < len(player.bench_pokemons):
                            bench_pokemon = player.bench_pokemons[bench_idx]
                            if bench_pokemon:
                                return f"Evolve {bench_pokemon.name} to {card.name} (Bench {bench_num})"
                    # Fallback: just show the card name
                    return f"Evolve to {card.name}"
        
        elif action_str.startswith("retreat_"):
            # Format: "retreat_{bench_index}" - moves active to empty bench slot, then first bench Pokemon becomes active
            if player.active_pokemon:
                parts = action_str.replace("retreat_", "")
                bench_num = parts if parts.isdigit() else None
                if bench_num and int(bench_num) < len(player.bench_pokemons):
                    # Find which bench Pokemon will become active (first non-empty bench that's not the target slot)
                    new_active = None
                    for i, bench_pokemon in enumerate(player.bench_pokemons):
                        if bench_pokemon and i != int(bench_num):
                            new_active = bench_pokemon
                            break
                    if new_active:
                        return f"Retreat {player.active_pokemon.name} to Bench {bench_num}, switch to {new_active.name}"
                    else:
                        return f"Retreat {player.active_pokemon.name} to Bench {bench_num}"
                return f"Retreat {player.active_pokemon.name}"
        
        elif action_str.startswith("play_item_"):
            parts = action_str.replace("play_item_", "")
            card = next((c for c in player.cards_in_hand if c.id == parts), None)
            if card:
                return f"Play {card.name} (Item)"
        
        elif action_str.startswith("play_supporter_"):
            parts = action_str.replace("play_supporter_", "")
            card = next((c for c in player.cards_in_hand if c.id == parts), None)
            if card:
                return f"Play {card.name} (Supporter)"
        
        elif action_str.startswith("attach_tool_"):
            # Format: "attach_tool_{card_id}_active" or "attach_tool_{card_id}_bench_{i}"
            parts = action_str.replace("attach_tool_", "").split("_")
            if len(parts) >= 2:
                card_id = parts[0]
                location = parts[1]  # "active" or "bench"
                
                # Find card in player's hand
                card = next((c for c in player.cards_in_hand if c.id == card_id), None)
                if card:
                    if location == "active" and player.active_pokemon:
                        return f"Attach {card.name} to {player.active_pokemon.name}"
                    elif location == "bench" and len(parts) >= 3:
                        # parts[2] is the bench index
                        bench_num = parts[2] if parts[2].isdigit() else "?"
                        bench_pokemon = player.bench_pokemons[int(bench_num)] if bench_num.isdigit() and int(bench_num) < len(player.bench_pokemons) else None
                        if bench_pokemon:
                            return f"Attach {card.name} to {bench_pokemon.name} (Bench {bench_num})"
                    elif location.startswith("bench_"):
                        # Legacy format: "bench_{i}" in location
                        bench_num = location.split("_")[1] if "_" in location else "?"
                        bench_pokemon = player.bench_pokemons[int(bench_num)] if bench_num.isdigit() and int(bench_num) < len(player.bench_pokemons) else None
                        if bench_pokemon:
                            return f"Attach {card.name} to {bench_pokemon.name} (Bench {bench_num})"
        
        elif action_str.startswith("use_ability_"):
            # Format: "use_ability_active_{i}" or "use_ability_bench_{bench_idx}_{i}"
            parts = action_str.replace("use_ability_", "").split("_")
            if len(parts) >= 1:
                location = parts[0]  # "active" or "bench"
                ability_index = 0
                bench_num = None
                
                if location == "active":
                    if len(parts) >= 2 and parts[1].isdigit():
                        ability_index = int(parts[1])
                    pokemon = player.active_pokemon
                elif location == "bench":
                    if len(parts) >= 2 and parts[1].isdigit():
                        bench_num = int(parts[1])
                        if len(parts) >= 3 and parts[2].isdigit():
                            ability_index = int(parts[2])
                    if bench_num is not None and bench_num < len(player.bench_pokemons):
                        pokemon = player.bench_pokemons[bench_num]
                    else:
                        pokemon = None
                else:
                    pokemon = None
                
                if pokemon and pokemon.abilities and ability_index < len(pokemon.abilities):
                    ability = pokemon.abilities[ability_index]
                    location_str = "Active" if location == "active" else f"Bench {bench_num}"
                    return f"Use {ability.name} on {pokemon.name} ({location_str})"
        
        # Default: return original
        return action_str
    
    def _get_attack_effect_description(self, attack, player) -> Optional[str]:
        """Get a human-readable description of an attack's effect"""
        if not attack.ability or not attack.ability.effect:
            return None
        
        effect_text = attack.ability.effect
        
        # Parse common patterns
        import re
        
        # Pattern: "Take a {Type} Energy from your Energy Zone and attach it to 1 of your Benched {Type} Pokémon. (Bench {N})"
        energy_attach_pattern = r'take.*?(\w+)\s+energy.*?attach.*?benched\s+(\w+).*?pokémon.*?bench\s+(\d+)'
        match = re.search(energy_attach_pattern, effect_text.lower())
        if match:
            energy_type = match.group(1).capitalize()
            pokemon_type = match.group(2).capitalize()
            bench_num = match.group(3)
            return f"Attach {energy_type} energy to {pokemon_type} Pokemon (Bench {bench_num})"
        
        # Pattern: "Take a {Type} Energy from your Energy Zone and attach it to 1 of your Benched {Type} Pokémon."
        energy_attach_pattern2 = r'take.*?(\w+)\s+energy.*?attach.*?benched\s+(\w+).*?pokémon'
        match = re.search(energy_attach_pattern2, effect_text.lower())
        if match:
            energy_type = match.group(1).capitalize()
            pokemon_type = match.group(2).capitalize()
            return f"Attach {energy_type} energy to {pokemon_type} Pokemon"
        
        # Pattern: "Take {N} {Type} Energy from your Energy Zone and attach it to this Pokémon."
        energy_attach_self_pattern = r'take\s+(\d+)\s+(\w+)\s+energy.*?attach.*?this\s+pokémon'
        match = re.search(energy_attach_self_pattern, effect_text.lower())
        if match:
            amount = match.group(1)
            energy_type = match.group(2).capitalize()
            return f"Attach {amount} {energy_type} energy to this Pokemon"
        
        # Pattern: "Discard a {Type} Energy from this Pokémon."
        discard_pattern = r'discard.*?(\w+)\s+energy.*?this\s+pokémon'
        match = re.search(discard_pattern, effect_text.lower())
        if match:
            energy_type = match.group(1).capitalize()
            return f"Discard {energy_type} energy from this Pokemon"
        
        # Pattern: "Draw {N} cards."
        draw_pattern = r'draw\s+(\d+)\s+cards?'
        match = re.search(draw_pattern, effect_text.lower())
        if match:
            amount = match.group(1)
            return f"Draw {amount} cards"
        
        # Pattern: "Search your deck for a {Type} Pokémon and put it into your hand."
        search_pattern = r'search.*?deck.*?(\w+)\s+pokémon|put.*?(\d+).*?random.*?(\w+).*?pokémon.*?deck'
        match = re.search(search_pattern, effect_text.lower())
        if match:
            pokemon_type = match.group(1) or match.group(3)
            if pokemon_type:
                return f"Search deck for {pokemon_type.capitalize()} Pokemon"
        
        # Pattern: "Flip a coin. If heads, the Defending Pokémon can't attack..."
        coin_flip_prevent_pattern = r'flip.*?coin.*?heads.*?can\'?t attack'
        if re.search(coin_flip_prevent_pattern, effect_text.lower()):
            return "Coin flip: If heads, opponent can't attack next turn"
        
        # Pattern: "Flip a coin. If tails, this attack does nothing."
        coin_flip_conditional_pattern = r'flip.*?coin.*?tails.*?does nothing'
        if re.search(coin_flip_conditional_pattern, effect_text.lower()):
            return "Coin flip: If tails, attack does nothing"
        
        # Pattern: "Heal X damage from this Pokémon."
        heal_self_pattern = r'heal\s+(\d+)\s+damage.*?this\s+pokémon'
        match = re.search(heal_self_pattern, effect_text.lower())
        if match:
            amount = match.group(1)
            return f"Heal {amount} damage from this Pokemon"
        
        # Pattern: "Heal X damage from each of your Pokémon."
        heal_all_pattern = r'heal\s+(\d+)\s+damage.*?each.*?pokémon'
        match = re.search(heal_all_pattern, effect_text.lower())
        if match:
            amount = match.group(1)
            return f"Heal {amount} damage from each Pokemon"
        
        # Fallback: return first 60 chars of effect (increased from 50)
        if len(effect_text) > 60:
            return effect_text[:57] + "..."
        return effect_text
    
    def _format_hand_card(self, card: Card) -> str:
        """Format a card for display in hand list"""
        from v3.models.cards.pokemon import Pokemon
        from v3.models.cards.tool import Tool
        from v3.models.cards.supporter import Supporter
        from v3.models.cards.item import Item
        
        if isinstance(card, Pokemon):
            element_str = self._format_energy_type(card.element)
            if card.subtype == Card.Subtype.BASIC:
                stage = "Basic"
            elif card.subtype == Card.Subtype.STAGE_1:
                stage = "Stage 1"
            elif card.subtype == Card.Subtype.STAGE_2:
                stage = "Stage 2"
            else:
                stage = str(card.subtype)
            return f"{card.name} - {stage} - {element_str} - {card.max_health()} HP"
        elif isinstance(card, Tool):
            return f"{card.name} (Tool)"
        elif isinstance(card, Supporter):
            return f"{card.name} (Supporter)"
        elif isinstance(card, Item):
            return f"{card.name} (Item)"
        else:
            return f"{card.name} ({card.type})"
    
    def _parse_action(self, action_str: str, player: Player):
        """Parse action string into Action object (for validation)"""
        from v3.models.match.actions.end_turn import EndTurnAction
        from v3.models.match.actions.play_pokemon import PlayPokemonAction
        from v3.models.match.actions.attach_energy import AttachEnergyAction
        from v3.models.match.actions.evolve import EvolveAction
        
        try:
            # Convert string to Action object
            if action_str == "end_turn":
                return EndTurnAction()
            elif action_str.startswith("attack_"):
                from v3.models.match.actions.attack import AttackAction
                return AttackAction.from_string(action_str, player)
            elif action_str.startswith("play_pokemon_"):
                return PlayPokemonAction.from_string(action_str, player)
            elif action_str.startswith("attach_energy_"):
                return AttachEnergyAction.from_string(action_str, player)
            elif action_str.startswith("evolve_"):
                return EvolveAction.from_string(action_str, player)
            elif action_str.startswith("retreat_"):
                from v3.models.match.actions.retreat import RetreatAction
                return RetreatAction.from_string(action_str, player)
            elif action_str.startswith("play_item_"):
                from v3.models.match.actions.play_item import PlayItemAction
                return PlayItemAction.from_string(action_str, player)
            elif action_str.startswith("play_supporter_"):
                from v3.models.match.actions.play_supporter import PlaySupporterAction
                return PlaySupporterAction.from_string(action_str, player)
            elif action_str.startswith("attach_tool_"):
                from v3.models.match.actions.attach_tool import AttachToolAction
                return AttachToolAction.from_string(action_str, player)
            elif action_str.startswith("use_ability_"):
                from v3.models.match.actions.use_ability import UseAbilityAction
                return UseAbilityAction.from_string(action_str, player)
            else:
                return None
        except Exception as e:
            if self.debug:
                self.log(f"DEBUG: Exception parsing action {action_str}: {e}")
            return None
    
    def _execute_action(self, action_str: str, player: Player) -> bool:
        """Execute an action from string representation"""
        if self.debug:
            self.log(f"DEBUG: _execute_action() called with: {action_str}")
        
        action = None
        try:
            # Parse action
            action = self._parse_action(action_str, player)
            if action is None:
                if self.debug:
                    self.log(f"DEBUG: _parse_action returned None for: {action_str}")
                self.log(f"Unknown action: {action_str}")
                return False
            
            if self.debug:
                self.log(f"DEBUG: Parsed action: {type(action).__name__}")
            
            # Validate
            is_valid, error = action.validate(player, self)
            if not is_valid:
                if self.debug:
                    self.log(f"DEBUG: Action validation failed: {error}")
                self.log(f"Invalid action: {error}")
                return False
            
            if self.debug:
                self.log(f"DEBUG: Action validation passed, executing...")
            
            # Execute
            action.execute(player, self)
            
            if self.debug:
                self.log(f"DEBUG: Action execution completed successfully")
            
            # Track last action for debug display
            if self.debug:
                self.last_action_taken = action_str
            
            # Note: Board display is now handled in _main_phase after action execution
            # to avoid duplicate displays and ensure proper turn continuation
            
            return True
            
        except Exception as e:
            self.log(f"Error executing action {action_str}: {e}")
            import traceback
            if self.debug:
                traceback.print_exc()
            return False




########################################################
#            Turn Execution Methods                    #
########################################################

    def _execute_turn(self):
        """Execute a complete turn"""
        self.turn += 1
        current = self._get_current_player()
        
        # Check if this is first player's first turn (after turn zero)
        is_first_player_first_turn = (self.turn == 1 and self.current_player_index == self.first_player_index)
        if is_first_player_first_turn:
            self.first_player_first_turn = True
            self.log(f"=== Turn {self.turn} - {current.name} (First Turn - No Energy Attachment) ===")
        else:
            self.first_player_first_turn = False
            self.log(f"=== Turn {self.turn} - {current.name} ===")
        
        # Check turn limit before starting turn
        if self.turn > GameRules.MAX_TURNS:
            self.log(f"Maximum turn limit ({GameRules.MAX_TURNS}) exceeded - ending game")
            return
        
        # Draw Phase (first player draws on their first turn)
        self.phase = GamePhase.DRAW
        self._draw_phase(current)
        
        # Check if game ended (deck-out, turn limit, etc.)
        if self._is_game_over():
            return
        
        # Main Phase
        self.phase = GamePhase.MAIN
        self._main_phase(current)
        
        # Check if game ended (after main phase actions)
        if self._is_game_over():
            return
        
        # End Phase
        self.phase = GamePhase.END
        self._end_turn()
        
        # Final check after end phase
        if self._is_game_over():
            return

    def _create_empty_state(self) -> List[float]:
        """Create an empty state array initialized with zeros"""
        # STATE_SIZE not defined - return empty list for now
        # This is for future AI state representation
        return []
    
    # This is a function that gets the state for the human player or for the AI
    def _get_state(self, player: Player, opponent: Player) -> Dict[str, Any]:
        """Get game state representation for agent"""
        # If the player is human, return human-readable state
        if player.agent.is_human:
            return self._get_human_state(player, opponent)
        # If the player is AI, return structured state
        else:
            return self._get_ai_state(player, opponent)
        
    def _get_actions(self, player: Player) -> List[str]:
        """Get all possible actions for the player"""

        # Get the actions from the player
        opponent_pokemon_locations = self._get_opponent_pokemon_locations(player, self.opponent)
        return player._get_actions(opponent_pokemon_locations)

    def _start_turn_effects(self, player: Player):
        """Handle start-of-turn effects (abilities, tools, etc.)"""
        # Check for passive abilities that trigger at start of turn
        # For now, this is a placeholder - passive abilities not yet implemented
        if player.active_pokemon:
            # Check for start-of-turn abilities
            for ability in player.active_pokemon.abilities:
                # Passive abilities would be checked here
                pass
    
    def _draw_phase(self, player: Player):
        """Draw phase: draw 1 card"""
        self.log(f"{player.name} draws a card")
        
        # Check if can draw (only requires deck to have cards - no hand size limit)
        # Note: Running out of cards is NOT a win condition - game continues until all prize points are gotten
        if not player.can_draw():
            self.log(f"{player.name} cannot draw - deck is empty (game continues)")
            # Don't try to draw if we can't, but game continues
            return
        
        # Draw card
        try:
            player.draw(1)
            self.log(f"{player.name} drew a card. Hand size: {len(player.cards_in_hand)}, Deck: {len(player.deck)}")
            
            # Note: If deck becomes empty, game continues - deck-out is NOT a win condition
            if len(player.deck) == 0:
                self.log(f"{player.name} drew their last card - deck is now empty (game continues)")
        except ValueError as e:
            self.log(f"ERROR: Cannot draw - {e}")
            # If deck is empty, game continues - not a win condition
            if len(player.deck) == 0:
                self.log(f"{player.name} has no cards in deck - game continues")
            return
        
        # No hand size limit - players can have any number of cards in hand
    
    def _main_phase(self, player: Player):
        """Main phase: player can perform actions"""
        self.log(f"{player.name} enters main phase")
        
        # First player's first turn: cannot attach energy
        if self.first_player_first_turn:
            self.log(f"{player.name} is on their first turn - energy attachment is not allowed")
        
        max_actions = 50  # Prevent infinite loops
        action_count = 0
        consecutive_invalid = 0  # Track consecutive invalid actions
        
        while action_count < max_actions:
            if self.debug:
                self.log(f"DEBUG: === Main phase loop iteration {action_count + 1} ===")
            
            # Get available actions
            actions = player._get_actions()
            if self.debug:
                self.log(f"DEBUG: Got {len(actions)} actions from player._get_actions()")
            
            # Filter out energy attachment on first player's first turn
            if self.first_player_first_turn:
                actions = [a for a in actions if not a.startswith("attach_energy_")]
                if self.debug:
                    self.log(f"DEBUG: Filtered out energy attachment actions (first player's first turn). Remaining: {len(actions)}")
            
            if not actions:
                if self.debug:
                    self.log(f"DEBUG: No actions available, breaking loop")
                break
            
            # Filter out invalid actions before presenting to agent
            valid_actions = []
            attack_actions = []  # Prioritize attack actions
            
            for action_str in actions:
                if action_str == "end_turn":
                    valid_actions.append(action_str)
                    continue
                
                # Quick validation check
                try:
                    action = self._parse_action(action_str, player)
                    if action is not None:
                        is_valid, error = action.validate(player, self)
                        if is_valid:
                            if action_str.startswith("attack_"):
                                attack_actions.append(action_str)
                                if self.debug:
                                    self.log(f"DEBUG: Attack action {action_str} PASSED validation")
                            else:
                                valid_actions.append(action_str)
                        elif action_str.startswith("attack_"):
                            if self.debug:
                                self.log(f"DEBUG: Attack action {action_str} validation FAILED: {error}")
                except Exception as e:
                    if action_str.startswith("attack_"):
                        if self.debug:
                            self.log(f"DEBUG: Exception validating attack action {action_str}: {e}")
                            import traceback
                            traceback.print_exc()
                    pass  # Skip invalid actions
            
            # Prioritize attack actions - put them first
            valid_actions = attack_actions + valid_actions
            
            # Debug: log available actions if debug mode
            if self.debug:
                attack_actions_in_original = [a for a in actions if a.startswith("attack_")]
                if attack_actions_in_original:
                    self.log(f"DEBUG: {len(attack_actions_in_original)} attack actions in original list: {attack_actions_in_original}")
                if attack_actions:
                    self.log(f"DEBUG: {len(attack_actions)} attack actions passed validation: {attack_actions}")
                elif attack_actions_in_original and not attack_actions:
                    # Attack actions were generated but failed validation
                    self.log(f"DEBUG: WARNING - {len(attack_actions_in_original)} attack actions generated but NONE passed validation!")
                    for action_str in attack_actions_in_original:
                        try:
                            action = self._parse_action(action_str, player)
                            if action is not None:
                                is_valid, error = action.validate(player, self)
                                self.log(f"DEBUG:   {action_str} validation: is_valid={is_valid}, error={error}")
                        except Exception as e:
                            self.log(f"DEBUG:   {action_str} exception: {e}")
                elif player.active_pokemon:
                    # Check why no attacks available
                    possible = player.active_pokemon.get_possible_attacks()
                    self.log(f"DEBUG: Active Pokemon {player.active_pokemon.name} has {len(possible)} possible attacks, energies")
                    # Check what attack actions should be generated
                    attack_actions_should_be = player._get_attack_actions()
                    if attack_actions_should_be:
                        self.log(f"DEBUG: _get_attack_actions() returned: {attack_actions_should_be}")
                    else:
                        self.log(f"DEBUG: _get_attack_actions() returned empty list")
            
            # If no valid actions (except end_turn), end turn
            if not valid_actions or (len(valid_actions) == 1 and valid_actions[0] == "end_turn"):
                break
            
            # Display board view AFTER validation (so it shows the same actions the agent will receive)
            if self.debug or (hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human):
                opponent = self._get_opponent(player)
                board_view = self.generate_board_view(player, opponent, actions=valid_actions)
                
                # Clear screen for human players (but not in debug mode)
                if hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human and not self.debug:
                    import os
                    os.system('clear' if os.name != 'nt' else 'cls')
                
                print("\n" + board_view + "\n")
            
            # Get action from agent (only from valid actions)
            if hasattr(player.agent, 'play_action'):
                # HumanAgent or improved RandomAgent interface
                if self.debug and attack_actions:
                    self.log(f"DEBUG: Presenting {len(valid_actions)} valid actions to agent (including {len(attack_actions)} attacks)")
                action_str = player.agent.play_action(valid_actions)
                if self.debug and action_str and action_str.startswith("attack_"):
                    self.log(f"DEBUG: Agent chose attack action: {action_str}")
            elif hasattr(player.agent, 'get_action'):
                # Legacy RandomAgent interface - convert to string
                action_indices = list(range(len(valid_actions)))
                action_index = player.agent.get_action({}, action_indices)
                if action_index is not None and 0 <= action_index < len(valid_actions):
                    action_str = valid_actions[action_index]
                else:
                    action_str = "end_turn"
            else:
                # Default: end turn
                action_str = "end_turn"
            
            # Check for attack or end turn
            if action_str == "end_turn" or action_str is None:
                break
            
            if action_str.startswith("attack_"):
                # Handle attack
                from v3.models.match.actions.attack import AttackAction
                attack_action = AttackAction.from_string(action_str, player)
                is_valid, error = attack_action.validate(player, self)
                if is_valid:
                    attack_action.execute(player, self)
                    
                    # Track last action for debug display
                    if self.debug:
                        self.last_action_taken = action_str
                    
                    # Display board after attack in debug mode OR for human players
                    # Note: We don't show actions here since we'll show them at the start of the next loop iteration
                    if self.debug or (hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human):
                        opponent = self._get_opponent(player)
                        # Don't show actions here - they'll be shown at the start of the next loop iteration with validation
                        board_view = self.generate_board_view(player, opponent, actions=[])
                        
                        # Clear screen for human players (but not in debug mode)
                        if hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human and not self.debug:
                            import os
                            os.system('clear' if os.name != 'nt' else 'cls')
                        
                        print("\n" + board_view + "\n")
                
                break  # Attack ends main phase
            
            # Execute action
            if self.debug:
                self.log(f"DEBUG: About to execute action: {action_str}")
            success = self._execute_action(action_str, player)
            
            if self.debug:
                self.log(f"DEBUG: Action execution result: success={success}")
            
            if not success:
                consecutive_invalid += 1
                if self.debug:
                    self.log(f"DEBUG: Invalid action count: {consecutive_invalid}")
                if consecutive_invalid >= 3:
                    # Too many invalid actions, end turn
                    self.log(f"{player.name} had too many invalid actions, ending turn")
                    break
            else:
                consecutive_invalid = 0
                action_count += 1
                
                if self.debug:
                    self.log(f"DEBUG: Action executed successfully. Action count: {action_count}, Max: {max_actions}")
                
                # Track last action for debug display
                if self.debug:
                    self.last_action_taken = action_str
                
                # Check what actions are available after this action (for next iteration)
                if self.debug:
                    next_actions = player._get_actions() if hasattr(player, '_get_actions') else []
                    if self.first_player_first_turn:
                        next_actions = [a for a in next_actions if not a.startswith("attach_energy_")]
                    self.log(f"DEBUG: Available actions after execution: {len(next_actions)} actions")
                    if len(next_actions) <= 5:
                        self.log(f"DEBUG: Actions list: {next_actions}")
                    else:
                        self.log(f"DEBUG: First 5 actions: {next_actions[:5]}")
                
                # Display board after action in debug mode OR for human players
                # Note: We don't show actions here since we'll show them at the start of the next loop iteration
                # This is just to show the updated game state
                if self.debug or (hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human):
                    opponent = self._get_opponent(player)
                    # Don't show actions here - they'll be shown at the start of the next loop iteration with validation
                    board_view = self.generate_board_view(player, opponent, actions=[])
                    
                    # Clear screen for human players (but not in debug mode)
                    if hasattr(player, 'agent') and hasattr(player.agent, 'is_human') and player.agent.is_human and not self.debug:
                        import os
                        os.system('clear' if os.name != 'nt' else 'cls')
                    
                    print("\n" + board_view + "\n")
            
            # If action failed and we've tried a few times, end turn
            if not success and consecutive_invalid >= 2:
                if self.debug:
                    self.log(f"DEBUG: Breaking due to consecutive invalid actions: {consecutive_invalid}")
                break
            
            # Check if we should continue the loop
            if self.debug:
                self.log(f"DEBUG: Loop check - action_count: {action_count}, max_actions: {max_actions}, will continue: {action_count < max_actions}")
    
    def _get_player_action(self, player: Player, has_attacked: bool) -> Optional[str]:
        """Get and execute player action"""
        # This is handled by _main_phase() which calls the agent
        # This method is kept for backward compatibility
        actions = self._get_actions(player)
        if actions:
            return player.agent.get_action(self._get_state(player, self._get_opponent(player)), list(range(len(actions))))
        return None
    
    def _default_ai_action(self, player: Player, has_attacked: bool) -> str:
        """Simple default AI logic"""
        # This is handled by the agent system (RandomAgent, etc.)
        # This method is kept for backward compatibility
        actions = self._get_actions(player)
        if actions:
            # Default: try to attack if possible
            attack_actions = [a for a in actions if a.startswith("attack_")]
            if attack_actions and not has_attacked:
                return attack_actions[0]
            # Otherwise return first available action
            return actions[0] if actions else "end_turn"
        return "end_turn"
    
    def _get_playable_cards(self, player: Player) -> List[Card]:
        """Get cards that can be played this turn"""
        # This is handled by player._get_actions() which generates all valid actions
        # Including play_pokemon, play_item, play_supporter, etc.
        # This method is kept for backward compatibility but actions handle it
        playable = []
        for card in player.cards_in_hand:
            if isinstance(card, Pokemon) and card.subtype == Card.Subtype.BASIC:
                playable.append(card)
            elif isinstance(card, (Card)) and hasattr(card, 'type'):
                # Items, Supporters, Tools can be played
                playable.append(card)
        return playable
    
    def _can_evolve_any(self, evolution: Pokemon, player: Player) -> bool:
        """Check if evolution can be played on any Pokemon"""
        from v3.models.match.game_rules import GameRules
        # Check active Pokemon
        if player.active_pokemon and GameRules.can_evolve(player.active_pokemon, evolution):
            return True
        # Check bench Pokemon
        for bench_pokemon in player.bench_pokemons:
            if bench_pokemon and GameRules.can_evolve(bench_pokemon, evolution):
                return True
        return False
    
    def _play_card(self, card: Card, player: Player):
        """Play a card from hand (legacy method - use actions instead)"""
        # This method is kept for backward compatibility
        # Actual card playing is handled by action classes:
        # - PlayPokemonAction
        # - PlayItemAction
        # - PlaySupporterAction
        # - AttachToolAction
        # Use _execute_action() with appropriate action string instead
        self.log(f"Warning: _play_card called directly - use action system instead")
    
    def _evolve_pokemon(self, evolution: Pokemon, player: Player):
        """Handle Pokemon evolution (legacy method - use EvolveAction instead)"""
        # This method is kept for backward compatibility
        # Actual evolution is handled by EvolveAction
        # Use _execute_action() with "evolve_{evolution_id}_{location}" instead
        self.log(f"Warning: _evolve_pokemon called directly - use EvolveAction instead")
    
    def _execute_attack(self, attacker: Pokemon, attack: Attack, player: Player, opponent: Player):
        """Execute an attack"""
        # Check for Confused status - may attack self
        from v3.models.match.status_effects.confused import Confused
        if attacker.has_status_effect(Confused):
            confused_status = next((se for se in attacker.status_effects if isinstance(se, Confused)), None)
            if confused_status and confused_status.check_attack_self(attacker, self):
                # Pokemon attacked itself, don't proceed with normal attack
                attacker.attacked_this_turn = True
                return
        
        defender = opponent.active_pokemon
        
        if not defender:
            self.log("No opponent Pokemon to attack")
            return
        
        # Check for coin flip effects BEFORE applying damage
        # Some attacks have coin flips that determine if they do anything
        coin_flip_cancelled = False
        if attack.ability and attack.ability.effect:
            from v3.models.match.effects import EffectParser
            from v3.models.match.effects.coin_flip_effect import CoinFlipEffect
            effects = EffectParser.parse_multiple(attack.ability.effect)
            for effect in effects:
                if isinstance(effect, CoinFlipEffect) and effect.effect_type == "conditional_damage":
                    # This attack requires a coin flip - if tails, does nothing
                    result = effect.execute(player, self, attacker)
                    if result is False:
                        coin_flip_cancelled = True
                        self.log(f"{attack.name} failed - attack does nothing")
                        attacker.attacked_this_turn = True
                        return
        
        # Display attack with damage
        damage = attack.damage if attack.damage else 0
        self.log(f"{attacker.name} uses {attack.name} - {damage} dmg!")
        
        # Calculate damage
        base_damage = int(attack.damage) if isinstance(attack.damage, int) else (int(attack.damage) if str(attack.damage).isdigit() else 0)
        final_damage = self._calculate_damage(attacker, defender, base_damage)
        
        # Note: Energy is NOT discarded when using an attack in Pokemon TCG Pocket
        
        # Apply damage
        knocked_out = self._apply_damage(defender, final_damage)
        
        # Execute attack effects (if any) - but skip coin flip effects we already handled
        if attack.ability and attack.ability.effect:
            from v3.models.match.effects import EffectParser
            from v3.models.match.effects.coin_flip_effect import CoinFlipEffect
            effects = EffectParser.parse_multiple(attack.ability.effect)
            for effect in effects:
                # Skip coin flip effects we already handled
                if isinstance(effect, CoinFlipEffect) and effect.effect_type == "conditional_damage":
                    continue
                try:
                    effect.execute(player, self, attacker)
                except Exception as e:
                    self.log(f"Error executing attack effect: {e}")
                    import traceback
                    if self.debug:
                        traceback.print_exc()
        
        # Set attacked flag
        attacker.attacked_this_turn = True
        
        # Handle knockout
        if knocked_out:
            self._handle_knockout(defender, opponent, player)
    
    def _calculate_damage(self, attacker: Pokemon, defender: Pokemon, base_damage: int) -> int:
        """Calculate final damage with modifiers"""
        damage = base_damage
        
        # Apply weakness (+20 damage) - ONLY if base damage > 0
        # Rule: If an attack does no damage, no weakness addition is applied
        if base_damage > 0 and defender.weakness and attacker.element == defender.weakness:
            damage += GameRules.WEAKNESS_BONUS
            self.log(f"Weakness! +{GameRules.WEAKNESS_BONUS} damage (total: {damage})")
        
        # Apply damage modifiers
        damage = max(0, damage - attacker.damage_nerf)
        
        return damage
    
    def _apply_damage(self, pokemon: Pokemon, damage: int) -> bool:
        """Apply damage to Pokemon, return True if knocked out"""
        pokemon.damage_taken += damage
        max_hp = pokemon.max_health()
        
        # Display damage - cap damage_taken at max_hp for display (can't exceed max)
        display_damage = min(pokemon.damage_taken, max_hp)
        self.log(f"{pokemon.name} takes {damage} damage ({display_damage}/{max_hp} HP)")
        
        # Check knockout (use max_health() which includes tool bonuses)
        if pokemon.damage_taken >= max_hp:
            return True
        return False
    
    def _handle_knockout(self, knocked_out: Pokemon, owner: Player, attacker: Player):
        """Handle Pokemon knockout"""
        self.log(f"{knocked_out.name} was knocked out!")
        
        # Calculate prize value
        prize_value = GameRules.calculate_prize_value(knocked_out)
        
        # Award prizes
        self._award_prizes(attacker, prize_value)
        
        # Remove Pokemon from play
        if owner.active_pokemon == knocked_out:
            owner.active_pokemon = None
            knocked_out.card_position = Card.Position.DISCARD
            owner.discard_card(knocked_out)
            
            # Force replacement
            self._force_active_replacement(owner)
        else:
            # Remove from bench
            for i, bench_pokemon in enumerate(owner.bench_pokemons):
                if bench_pokemon == knocked_out:
                    owner.bench_pokemons[i] = None
                    knocked_out.card_position = Card.Position.DISCARD
                    owner.discard_card(knocked_out)
                    break
        
        self.log(f"{attacker.name} takes {prize_value} prize(s)! Total: {attacker.points}")
    
    def _award_prizes(self, player: Player, amount: int):
        """Award prize points to player"""
        player.points += amount
        self.log(f"{player.name} now has {player.points} points")
    
    def _force_active_replacement(self, player: Player):
        """Force player to replace KO'd active Pokemon - let player choose which bench Pokemon"""
        # Check if player has benched Pokemon
        benched_pokemon = [p for p in player.bench_pokemons if p is not None]
        
        if self.debug:
            self.log(f"DEBUG: Checking bench for {player.name}: {[p.name if p else None for p in player.bench_pokemons]}")
        
        if not benched_pokemon:
            self.log(f"{player.name} has no benched Pokemon - GAME OVER")
            return  # Game will end in _is_game_over()
        
        # Generate actions for choosing which bench Pokemon to bring to active
        replacement_actions = []
        for i, bench_pokemon in enumerate(player.bench_pokemons):
            if bench_pokemon:
                replacement_actions.append(f"replace_active_{i}")
        
        if not replacement_actions:
            self.log(f"{player.name} has no benched Pokemon - GAME OVER")
            return
        
        # Get action from agent
        action_str = None
        if hasattr(player.agent, 'play_action'):
            # HumanAgent interface
            if self.debug or player.agent.is_human:
                # Display board and available replacement options
                if player.agent.is_human:
                    print("\n" + "=" * 100)
                    print(f"{player.name}'s Active Pokemon was knocked out!")
                    print("Choose which benched Pokemon to bring to active:")
                    for idx, action in enumerate(replacement_actions, 1):
                        bench_idx = int(action.split("_")[-1])
                        bench_pokemon = player.bench_pokemons[bench_idx]
                        print(f"  {idx}. {bench_pokemon.name} (Bench {bench_idx})")
                    print("=" * 100 + "\n")
                action_str = player.agent.play_action(replacement_actions)
            else:
                # For non-human agents, use get_action if available
                if hasattr(player.agent, 'get_action'):
                    action_indices = list(range(len(replacement_actions)))
                    action_index = player.agent.get_action({}, action_indices)
                    if action_index is not None and 0 <= action_index < len(replacement_actions):
                        action_str = replacement_actions[action_index]
        elif hasattr(player.agent, 'get_action'):
            # RandomAgent interface
            action_indices = list(range(len(replacement_actions)))
            action_index = player.agent.get_action({}, action_indices)
            if action_index is not None and 0 <= action_index < len(replacement_actions):
                action_str = replacement_actions[action_index]
        
        # Default: choose first available
        if not action_str:
            action_str = replacement_actions[0]
        
        # Parse and execute replacement
        if action_str.startswith("replace_active_"):
            try:
                bench_idx = int(action_str.split("_")[-1])
                if 0 <= bench_idx < len(player.bench_pokemons) and player.bench_pokemons[bench_idx]:
                    bench_pokemon = player.bench_pokemons[bench_idx]
                    # Move to active
                    player.active_pokemon = bench_pokemon
                    player.bench_pokemons[bench_idx] = None
                    bench_pokemon.card_position = Card.Position.ACTIVE
                    self.log(f"{player.name} replaces active with {bench_pokemon.name}")
                else:
                    # Fallback: choose first available
                    for i, bench_pokemon in enumerate(player.bench_pokemons):
                        if bench_pokemon:
                            player.active_pokemon = bench_pokemon
                            player.bench_pokemons[i] = None
                            bench_pokemon.card_position = Card.Position.ACTIVE
                            self.log(f"{player.name} replaces active with {bench_pokemon.name}")
                            break
            except (ValueError, IndexError):
                # Fallback: choose first available
                for i, bench_pokemon in enumerate(player.bench_pokemons):
                    if bench_pokemon:
                        player.active_pokemon = bench_pokemon
                        player.bench_pokemons[i] = None
                        bench_pokemon.card_position = Card.Position.ACTIVE
                        self.log(f"{player.name} replaces active with {bench_pokemon.name}")
                        break
    
    def _process_status_effects(self, player: Player):
        """Handle status effects at turn start"""
        # Status effects are now handled in _apply_status_effects() during _end_turn()
        # This method is kept for backward compatibility
        # Start-of-turn status effects would be processed here if needed
        pass
    
    def _end_turn(self):
        """End current turn: reset flags, increment turns, switch players"""
        current = self._get_current_player()
        
        # Reset turn flags
        if current.active_pokemon:
            current.active_pokemon.attacked_this_turn = False
            current.active_pokemon.placed_or_evolved_this_turn = False
            current.active_pokemon.used_ability_this_turn = False
            current.active_pokemon.turns_in_play += 1
        
        for bench_pokemon in current.bench_pokemons:
            if bench_pokemon:
                bench_pokemon.attacked_this_turn = False
                bench_pokemon.placed_or_evolved_this_turn = False
                bench_pokemon.used_ability_this_turn = False
                bench_pokemon.turns_in_play += 1
        
        # Reset trainer card flags
        current.played_supporter_this_turn = False
        current.can_play_trainer = True
        
        # Reset action limits
        current.attached_energy_this_turn = False
        current.played_pokemon_this_turn = False
        current.used_rare_candy_this_turn = False
        
        # Switch to next player
        self.current_player_index = 1 - self.current_player_index
        next_player = self._get_current_player()
        
        # Reset attack prevention flag for next player (they can attack unless prevented)
        next_player.can_attack_next_turn = True
        
        # Apply status effects before switching players
        self._apply_status_effects(current)
        
        # Generate energy for next turn
        current.energy_zone.generate_energy()
        
        self.log(f"{current.name}'s turn ends")
        
        # Switch players
        self._switch_players()
        
        # Generate energy for new current player
        new_current = self._get_current_player()
        new_current.energy_zone.generate_energy()
    
    def _is_game_over(self) -> bool:
        """Check if game should end"""
        # Don't check game over during setup or turn zero
        if self.phase == GamePhase.SETUP or self.turn == 0:
            return False
        
        # Check maximum turn limit
        if self.turn >= GameRules.MAX_TURNS:
            self.log(f"Maximum turn limit reached ({GameRules.MAX_TURNS} turns) - Game ends in a draw")
            return True
        
        for player in self.players:
            # Check prize victory
            if player.points >= GameRules.WINNING_POINTS:
                return True
            
            # Check no Pokemon (only after turn zero)
            if player.active_pokemon is None:
                has_bench = any(p is not None for p in player.bench_pokemons)
                if not has_bench:
                    # Only end game if we're past turn zero
                    if self.turn > 0:
                        return True
            
            # Note: Deck-out is NOT a win condition - game continues until all prize points are gotten
        
        return False
    
    def _apply_status_effects(self, player):
        """Apply status effects between turns"""
        if player.active_pokemon:
            pokemon = player.active_pokemon
            for status in pokemon.status_effects[:]:  # Copy list to modify
                if hasattr(status, 'apply_damage'):
                    status.apply_damage(pokemon, self)
                if status.check_removal(pokemon, self):
                    status.remove(pokemon)
        
        # Also check bench Pokemon
        for bench_pokemon in player.bench_pokemons:
            if bench_pokemon:
                for status in bench_pokemon.status_effects[:]:
                    if hasattr(status, 'apply_damage'):
                        status.apply_damage(bench_pokemon, self)
                    if status.check_removal(bench_pokemon, self):
                        status.remove(bench_pokemon)
    
    def _get_player_with_pokemon(self, pokemon):
        """Helper to find which player owns a Pokemon"""
        for player in self.players:
            if player.active_pokemon == pokemon:
                return player
            if pokemon in player.bench_pokemons:
                return player
        return None
    
    def _determine_winner(self) -> Optional[Player]:
        """Determine game winner"""
        # Check maximum turn limit - if reached, it's a draw
        if self.turn >= GameRules.MAX_TURNS:
            self.log(f"Game reached maximum turn limit ({GameRules.MAX_TURNS} turns) - Draw!")
            return None  # Draw
        
        for player in self.players:
            # Check prize victory
            if player.points >= GameRules.WINNING_POINTS:
                return player
            
            # Check no Pokemon
            if player.active_pokemon is None:
                has_bench = any(p is not None for p in player.bench_pokemons)
                if not has_bench:
                    return self._get_opponent(player)  # Opponent wins
            
            # Note: Deck-out is NOT a win condition - game continues until all prize points are gotten
        
        return None  # Draw (e.g., max turns reached)
    
    def _get_human_state(self, player: Player, opponent: Player) -> List[float]:
        """Get the state for the human player"""
        # Placeholder for GUI state representation
        # Future: Return structured state for human player display
        return []
    
    def _get_opponent_pokemon_locations(self, player: Player, opponent: Player) -> List[int]:
        """Get the location of the opponent's Pokemon (active + 3 bench slots)"""
        pokemon_locations = [0] * 4  # [active, bench1, bench2, bench3]
        if opponent.active_pokemon:
            pokemon_locations[0] = 1
        if opponent.bench_pokemons[0]:
            pokemon_locations[1] = 1
        if opponent.bench_pokemons[1]:
            pokemon_locations[2] = 1
        if opponent.bench_pokemons[2]:
            pokemon_locations[3] = 1
        return pokemon_locations
