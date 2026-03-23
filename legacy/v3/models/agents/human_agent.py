class HumanAgent:
    """Human-controlled agent for Pokemon TCG Pocket battles via terminal input"""
    
    def __init__(self, player):
        self.player = player
        self.is_human = True

    def play_action(self, actions):
        """Play an action from the list of actions - returns action string"""
        # Actions may be displayed (1-indexed) or raw list, so we handle both
        while True:
            try:
                user_input = input("Enter the number of the action you want to play: ").strip()
                user_index = int(user_input)
                # Convert from 1-indexed (what user sees) to 0-indexed (array index)
                action_index = user_index - 1
                if 0 <= action_index < len(actions):
                    return actions[action_index]  # Return original action string
                else:
                    print(f"Invalid action number. Please enter a number between 1 and {len(actions)}")
            except ValueError:
                print("Please enter a valid number.")
    
    def _format_action(self, action_str: str) -> str:
        """Format action string to show Pokemon names instead of IDs"""
        # Find the card in hand to get its name
        if action_str.startswith("play_pokemon_"):
            parts = action_str.replace("play_pokemon_", "").split("_", 1)
            if len(parts) >= 1:
                card_id = parts[0]
                position = parts[1] if len(parts) > 1 else "active"
                
                # Find card in player's hand
                card = next((c for c in self.player.cards_in_hand if c.id == card_id), None)
                if card:
                    card_name = card.name
                    if position == "active":
                        return f"Play {card_name} to Active"
                    elif position.startswith("bench_"):
                        bench_num = position.split("_")[1] if "_" in position else "?"
                        return f"Play {card_name} to Bench {bench_num}"
                    else:
                        return f"Play {card_name} to {position}"
        
        elif action_str.startswith("attack_"):
            # Format: "attack_{attack_index}"
            parts = action_str.replace("attack_", "").split("_")
            attack_index = int(parts[0]) if parts and parts[0].isdigit() else 0
            
            if self.player.active_pokemon:
                pokemon = self.player.active_pokemon
                if pokemon.attacks and attack_index < len(pokemon.attacks):
                    attack = pokemon.attacks[attack_index]
                    damage = attack.damage if attack.damage else 0
                    return f"Attack: {attack.name} - {damage} dmg"
        
        elif action_str == "end_turn":
            return "End Turn"
        
        elif action_str.startswith("attach_energy_"):
            parts = action_str.replace("attach_energy_", "").split("_")
            if len(parts) >= 2:
                pokemon_id = parts[0]
                energy_type = parts[1]
                
                # Find Pokemon
                pokemon = None
                if self.player.active_pokemon and self.player.active_pokemon.id == pokemon_id:
                    pokemon = self.player.active_pokemon
                else:
                    for bench_pokemon in self.player.bench_pokemons:
                        if bench_pokemon and bench_pokemon.id == pokemon_id:
                            pokemon = bench_pokemon
                            break
                
                if pokemon:
                    return f"Attach {energy_type} Energy to {pokemon.name}"
        
        # Default: return original
        return action_str
