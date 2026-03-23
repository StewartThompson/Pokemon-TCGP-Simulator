from abc import ABC, abstractmethod
import random
# from sb3_contrib import MaskablePPO  # Not needed for RandomAgent
from v3.models.agents.agent import Agent
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.models.cards.pokemon import Pokemon

class RandomAgent(Agent):
    """
    An improved agent that uses weighted random selection with heuristics.
    Prioritizes attacking, energy attachment to active Pokemon, and smart play decisions.
    """
    
    def __init__(self, player):
        super().__init__(player)
        self.is_human = False
    
    def get_action(self, state: Dict, valid_action_indices: List[int]) -> Optional[int]:
        """Get action using weighted random selection based on heuristics"""
        if not valid_action_indices:
            return None
        
        # Get the actual action strings from the player
        # We need to access the player's available actions
        if not hasattr(self, 'player') or self.player is None:
            return random.choice(valid_action_indices)
        
        # Get current valid actions from the battle engine context
        # Since we don't have direct access, we'll use weighted selection based on indices
        # Attack actions are typically first (due to prioritization in battle_engine)
        weights = self._calculate_action_weights(valid_action_indices)
        
        # Weighted random selection
        return random.choices(valid_action_indices, weights=weights, k=1)[0]
    
    def _calculate_action_weights(self, action_indices: List[int]) -> List[float]:
        """Calculate weights for each action index based on heuristics"""
        weights = []
        
        for idx in action_indices:
            weight = 1.0  # Base weight
            
            # Attack actions get highest priority (they're typically first in the list)
            # If index is 0-2, it's likely an attack (since attacks are prioritized)
            if idx < 3:
                weight = 10.0  # Very high priority for attacks
            
            # Energy attachment to active Pokemon is important
            # This is harder to detect from index alone, but we can infer
            # Actions after attacks but before end_turn are likely setup actions
            elif idx < len(action_indices) - 1:  # Not the last action (end_turn)
                weight = 3.0  # Medium priority for setup actions
            
            # End turn is lowest priority (unless no other options)
            else:
                weight = 0.5  # Low priority for ending turn
            
            weights.append(weight)
        
        return weights
    
    def play_action(self, actions: List[str]) -> Optional[str]:
        """Play an action from list of action strings (for HumanAgent-like interface)"""
        if not actions:
            return None
        
        # Check if bench is empty - this is CRITICAL and should be addressed before attacking
        bench_count = sum(1 for p in self.player.bench_pokemons if p is not None) if hasattr(self, 'player') and self.player else 0
        bench_actions = [a for a in actions if a.startswith("play_pokemon_") and "_bench" in a]
        
        # If bench is empty and we have Pokemon to play, prioritize that over attacking
        if bench_count == 0 and bench_actions:
            # Very high priority - survival is more important than attacking
            selected = random.choice(bench_actions)
            if hasattr(self, 'player') and self.player:
                print(f"DEBUG AGENT: {self.player.name} prioritizing bench setup (empty bench): {selected}")
            return selected
        
        # First, check if we can attack - if so, prioritize KO potential or highest damage
        attack_actions = [a for a in actions if a.startswith("attack_")]
        if attack_actions:
            # Prioritize attack that can KO or highest damage
            if hasattr(self, 'player') and self.player and self.player.active_pokemon:
                pokemon = self.player.active_pokemon
                best_attack = None
                best_score = -1
                
                for action_str in attack_actions:
                    # Parse attack index from action string (format: "attack_0", "attack_1", etc.)
                    try:
                        attack_index = int(action_str.split("_")[1])
                        if attack_index < len(pokemon.attacks):
                            attack = pokemon.attacks[attack_index]
                            damage = int(attack.damage) if attack.damage and str(attack.damage).isdigit() else 0
                            
                            # Score based on damage (prioritize higher damage)
                            # Also consider attack effects (healing, drawing, etc.)
                            score = damage
                            
                            # Bonus for attacks with beneficial effects
                            if attack.ability and attack.ability.effect:
                                effect_text = attack.ability.effect.lower()
                                if "heal" in effect_text:
                                    score += 5  # Healing is valuable
                                if "draw" in effect_text or "search" in effect_text:
                                    score += 3  # Card draw is valuable
                            
                            if score > best_score:
                                best_score = score
                                best_attack = action_str
                    except (ValueError, IndexError):
                        pass
                
                # Use best attack if found, otherwise random
                selected = best_attack if best_attack else random.choice(attack_actions)
            else:
                selected = random.choice(attack_actions)
            
            # Debug: log that we're attacking
            if hasattr(self, 'player') and self.player:
                print(f"DEBUG AGENT: {self.player.name} choosing to attack: {selected} from {attack_actions}")
            return selected
        
        # Check if active Pokemon can attack
        can_attack = False
        if hasattr(self, 'player') and self.player and self.player.active_pokemon:
            active_pokemon = self.player.active_pokemon
            can_attack = len(active_pokemon.get_possible_attacks()) > 0
        
        # Calculate weights based on action types
        weights = []
        for action in actions:
            weight = 1.0  # Base weight
            
            # Prioritize attacks very highly - almost always attack if possible
            if action.startswith("attack_"):
                weight = 50.0  # Much higher priority
            
            # Prioritize attaching energy to active Pokemon
            # If active can't attack, this becomes CRITICAL
            elif action.startswith("attach_energy_active"):
                if not can_attack:
                    weight = 25.0  # Very high priority if active can't attack
                else:
                    weight = 8.0  # Still high priority, but less critical
            
            # Prioritize attaching energy to bench Pokemon (but less than active)
            # Only if active Pokemon can already attack
            elif action.startswith("attach_energy_bench"):
                if not can_attack:
                    weight = 0.5  # Very low priority if active needs energy
                else:
                    # Check which bench Pokemon would benefit most
                    weight = self._calculate_bench_energy_weight(action)
            
            # Prioritize playing Pokemon to active if no active Pokemon
            elif action.startswith("play_pokemon_") and "_active" in action:
                # Check if player has no active Pokemon
                if hasattr(self, 'player') and self.player and self.player.active_pokemon is None:
                    weight = 20.0  # Very high if no active Pokemon (especially during setup)
                else:
                    weight = 3.0
            
            # Prioritize playing Pokemon to bench (but only if active is already set)
            elif action.startswith("play_pokemon_") and "_bench" in action:
                # During setup, only play to bench if active is already set
                if hasattr(self, 'player') and self.player and self.player.active_pokemon is None:
                    weight = 0.1  # Very low if no active Pokemon (should set active first)
                else:
                    # Check how many bench slots are filled
                    bench_count = sum(1 for p in self.player.bench_pokemons if p is not None) if hasattr(self, 'player') and self.player else 0
                    if bench_count == 0:
                        weight = 12.0  # Very high priority if bench is completely empty (critical for survival)
                    elif bench_count < 2:
                        weight = 8.0  # High priority if bench has only 1 Pokemon
                    elif bench_count < 3:
                        weight = 4.0  # Medium priority if bench has 2 Pokemon
                    else:
                        weight = 1.0  # Low priority if bench is full
            
            # Prioritize evolution - smarter decisions
            elif action.startswith("evolve_"):
                weight = self._calculate_evolution_weight(action)
            
            # Prioritize using abilities - especially beneficial ones
            elif action.startswith("use_ability_"):
                weight = self._calculate_ability_weight(action)
            
            # Prioritize playing items/supporters - strategic usage
            elif action.startswith("play_item_") or action.startswith("play_supporter_"):
                weight = self._calculate_trainer_weight(action)
            
            # Retreat intelligence - strategic retreat decisions
            elif action.startswith("retreat_"):
                weight = self._calculate_retreat_weight(action)
            
            # End turn is lowest priority - only if no other good options
            elif action == "end_turn":
                # Only end turn if we've done something useful this turn
                # Check if we have attack actions available (they should be prioritized)
                has_attack = any(a.startswith("attack_") for a in actions)
                if has_attack:
                    weight = 0.01  # Very low if attacks available
                else:
                    weight = 1.0  # Acceptable if no attacks available
            
            weights.append(weight)
        
        # Weighted random selection
        selected_action = random.choices(actions, weights=weights, k=1)[0]
        return selected_action
    
    def _calculate_evolution_weight(self, action: str) -> float:
        """Calculate weight for evolution action based on strategic value"""
        if not hasattr(self, 'player') or not self.player:
            return 5.0  # Default weight
        
        # Parse evolution action: "evolve_{card_id}_{location}"
        try:
            parts = action.replace("evolve_", "").split("_")
            if len(parts) < 2:
                return 5.0
            
            evolution_card_id = parts[0]
            location = "_".join(parts[1:])
            
            # Find evolution card and target Pokemon
            evolution_card = next((c for c in self.player.cards_in_hand if c.id == evolution_card_id), None)
            if not evolution_card or not isinstance(evolution_card, Pokemon):
                return 5.0
            
            # Get target Pokemon
            target = None
            if location == "active":
                target = self.player.active_pokemon
            elif location.startswith("bench_"):
                try:
                    bench_idx = int(location.split("_")[1])
                    if 0 <= bench_idx < len(self.player.bench_pokemons):
                        target = self.player.bench_pokemons[bench_idx]
                except (ValueError, IndexError):
                    pass
            
            if not target:
                return 5.0
            
            weight = 5.0  # Base weight
            
            # Prioritize evolving active Pokemon (can attack immediately)
            if location == "active":
                weight += 3.0
            
            # Prioritize if target has energy (can attack after evolving)
            total_energy = sum(target.equipped_energies.values())
            if total_energy > 0:
                weight += 2.0
            
            # Prioritize if target has status effects (evolution removes them)
            if target.status_effects:
                weight += 2.0
            
            # Prioritize if evolution has better attacks
            if evolution_card.attacks and target.attacks:
                evolution_max_damage = max((int(a.damage) if a.damage and str(a.damage).isdigit() else 0) for a in evolution_card.attacks)
                target_max_damage = max((int(a.damage) if a.damage and str(a.damage).isdigit() else 0) for a in target.attacks)
                if evolution_max_damage > target_max_damage:
                    weight += 3.0
            
            # Prioritize if target is damaged (evolution can help)
            if target.damage_taken > 0:
                weight += 1.0
            
            return weight
        except Exception:
            return 5.0  # Default on error
    
    def _calculate_ability_weight(self, action: str) -> float:
        """Calculate weight for ability usage based on strategic value"""
        if not hasattr(self, 'player') or not self.player:
            return 3.0  # Default weight
        
        weight = 3.0  # Base weight
        
        # Parse ability action: "use_ability_{location}_{ability_index}"
        try:
            parts = action.replace("use_ability_", "").split("_")
            if len(parts) < 2:
                return weight
            
            location = "_".join(parts[:-1])
            ability_index = int(parts[-1])
            
            # Get Pokemon
            pokemon = None
            if location == "active":
                pokemon = self.player.active_pokemon
            elif location.startswith("bench_"):
                try:
                    bench_idx = int(location.split("_")[1])
                    if 0 <= bench_idx < len(self.player.bench_pokemons):
                        pokemon = self.player.bench_pokemons[bench_idx]
                except (ValueError, IndexError):
                    pass
            
            if not pokemon or ability_index >= len(pokemon.abilities):
                return weight
            
            ability = pokemon.abilities[ability_index]
            
            # Prioritize abilities that draw cards (especially if hand is small)
            if ability.effect and ("draw" in ability.effect.lower() or "search" in ability.effect.lower()):
                if len(self.player.cards_in_hand) < 5:
                    weight += 3.0  # Very useful if hand is small
                else:
                    weight += 1.0
            
            # Prioritize healing abilities (especially if Pokemon is damaged)
            if ability.effect and "heal" in ability.effect.lower():
                if pokemon.damage_taken > 0:
                    weight += 2.0
            
            # Prioritize abilities on active Pokemon (more immediately useful)
            if location == "active":
                weight += 1.0
            
            return weight
        except Exception:
            return 3.0  # Default on error
    
    def _calculate_trainer_weight(self, action: str) -> float:
        """Calculate weight for trainer card usage based on strategic value"""
        if not hasattr(self, 'player') or not self.player:
            return 2.0  # Default weight
        
        weight = 2.0  # Base weight
        
        # Parse trainer action: "play_item_{card_id}" or "play_supporter_{card_id}"
        try:
            if action.startswith("play_item_"):
                card_id = action.replace("play_item_", "")
            elif action.startswith("play_supporter_"):
                card_id = action.replace("play_supporter_", "")
            else:
                return weight
            
            # Find card in hand
            card = next((c for c in self.player.cards_in_hand if c.id == card_id), None)
            if not card:
                return weight
            
            # Check card effect/ability
            effect_text = ""
            if hasattr(card, 'ability') and card.ability and card.ability.effect:
                effect_text = card.ability.effect.lower()
            elif hasattr(card, 'effect'):
                effect_text = str(card.effect).lower()
            
            # Prioritize cards that draw/search (especially if hand is small or bench is empty)
            if "draw" in effect_text or "search" in effect_text:
                bench_count = sum(1 for p in self.player.bench_pokemons if p is not None)
                if len(self.player.cards_in_hand) < 5:
                    weight += 4.0  # Very useful if hand is small
                if bench_count < 2:
                    weight += 3.0  # Very useful if bench is empty
                else:
                    weight += 1.0
            
            # Prioritize healing cards if Pokemon are damaged
            if "heal" in effect_text:
                has_damaged = False
                if self.player.active_pokemon and self.player.active_pokemon.damage_taken > 0:
                    has_damaged = True
                for bench_pokemon in self.player.bench_pokemons:
                    if bench_pokemon and bench_pokemon.damage_taken > 0:
                        has_damaged = True
                        break
                if has_damaged:
                    weight += 2.0
            
            # Prioritize items over supporters (items are unlimited)
            if action.startswith("play_item_"):
                weight += 0.5
            
            return weight
        except Exception:
            return 2.0  # Default on error
    
    def _calculate_retreat_weight(self, action: str) -> float:
        """Calculate weight for retreat action based on strategic value"""
        if not hasattr(self, 'player') or not self.player or not self.player.active_pokemon:
            return 1.0  # Default weight
        
        weight = 1.0  # Base weight (retreat is generally low priority)
        
        try:
            active = self.player.active_pokemon
            
            # Check if active Pokemon is heavily damaged (likely to be KO'd)
            health_percentage = (active.health - active.damage_taken) / active.health if active.health > 0 else 0
            if health_percentage < 0.3:  # Less than 30% health
                weight += 8.0  # High priority to retreat
            elif health_percentage < 0.5:  # Less than 50% health
                weight += 4.0  # Medium priority to retreat
            
            # Check if active Pokemon can't attack
            if len(active.get_possible_attacks()) == 0:
                # Check if bench Pokemon can attack
                bench_can_attack = False
                for bench_pokemon in self.player.bench_pokemons:
                    if bench_pokemon and len(bench_pokemon.get_possible_attacks()) > 0:
                        bench_can_attack = True
                        break
                
                if bench_can_attack:
                    weight += 6.0  # High priority if bench can attack but active can't
            
            # Check for status effects that prevent attacking
            if active.status_effects:
                status_names = [s.__class__.__name__.lower() for s in active.status_effects]
                if "paralyzed" in status_names or "confused" in status_names:
                    weight += 5.0  # Retreat if paralyzed or confused
            
            # Check if bench Pokemon have better attacks
            if active.attacks:
                active_max_damage = max((int(a.damage) if a.damage and str(a.damage).isdigit() else 0) for a in active.attacks)
            else:
                active_max_damage = 0
            
            bench_better_attack = False
            for bench_pokemon in self.player.bench_pokemons:
                if bench_pokemon and bench_pokemon.attacks:
                    bench_max_damage = max((int(a.damage) if a.damage and str(a.damage).isdigit() else 0) for a in bench_pokemon.attacks)
                    if bench_max_damage > active_max_damage:
                        # Check if bench Pokemon can afford the attack
                        for attack in bench_pokemon.attacks:
                            if bench_pokemon._can_afford_attack(attack):
                                bench_better_attack = True
                                break
                        if bench_better_attack:
                            break
            
            if bench_better_attack:
                weight += 3.0  # Medium priority if bench has better attacks
            
            # Lower priority if active Pokemon has a lot of energy (costly to retreat)
            total_energy = sum(active.equipped_energies.values())
            if total_energy > 3:
                weight -= 2.0  # Less likely to retreat if lots of energy invested
            
            # Lower priority if retreat cost is high
            if active.retreat_cost > 2:
                weight -= 1.0
            
            return max(0.1, weight)  # Ensure weight is positive
        except Exception:
            return 1.0  # Default on error
    
    def _calculate_bench_energy_weight(self, action: str) -> float:
        """Calculate weight for attaching energy to bench Pokemon"""
        if not hasattr(self, 'player') or not self.player:
            return 4.0  # Default weight
        
        weight = 4.0  # Base weight
        
        try:
            # Parse bench index from action: "attach_energy_bench_{index}"
            parts = action.replace("attach_energy_bench_", "").split("_")
            if not parts or not parts[0].isdigit():
                return weight
            
            bench_index = int(parts[0])
            if bench_index < 0 or bench_index >= len(self.player.bench_pokemons):
                return weight
            
            bench_pokemon = self.player.bench_pokemons[bench_index]
            if not bench_pokemon:
                return 0.1  # No Pokemon at that bench slot
            
            # Prioritize if this energy would allow the Pokemon to attack
            total_energy = sum(bench_pokemon.equipped_energies.values())
            
            # Check if adding one energy would enable an attack
            for attack in bench_pokemon.attacks:
                if not bench_pokemon._can_afford_attack(attack):
                    # Check if one more energy would help
                    # This is a simplified check - we'd need to know what energy type is being attached
                    # For now, assume any energy might help
                    if total_energy == 0:
                        weight += 2.0  # First energy is valuable
                    elif total_energy < 2:
                        weight += 1.0  # Second energy is also valuable
            
            # Prioritize if bench Pokemon has better attacks than active
            if self.player.active_pokemon and bench_pokemon.attacks:
                if self.player.active_pokemon.attacks:
                    active_max_damage = max((int(a.damage) if a.damage and str(a.damage).isdigit() else 0) for a in self.player.active_pokemon.attacks)
                else:
                    active_max_damage = 0
                
                bench_max_damage = max((int(a.damage) if a.damage and str(a.damage).isdigit() else 0) for a in bench_pokemon.attacks)
                if bench_max_damage > active_max_damage:
                    weight += 2.0  # Prioritize if bench has better attacks
            
            return weight
        except Exception:
            return 4.0  # Default on error