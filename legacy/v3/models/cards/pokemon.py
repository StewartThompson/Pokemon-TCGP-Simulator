from .card import Card
from .tool import Tool
from .attack import Attack
from .ability import Ability
from .energy import Energy
from typing import Dict, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from .attack import Attack


class Pokemon(Card):

    class PokemonType:
        EX = "ex"
        BEAST = "beast"
        ALOLAN = "alolan"
    
    def __init__(self, id: str, name: str, element: Energy.Type, type: Card.Type, subtype: Card.Subtype, health: int, set: str, pack: str, rarity: str, attacks: list[Attack], retreat_cost: int, weakness: Energy.Type, evolves_from: str, image_url: str = None, ability: Ability = None, abilities: Optional[List[Ability]] = None):
        # Handle abilities - support both single ability and list
        if abilities is not None:
            self.abilities: List[Ability] = abilities
        elif ability is not None:
            self.abilities: List[Ability] = [ability]
        else:
            self.abilities: List[Ability] = []
        
        # Keep ability for backward compatibility (first ability)
        first_ability = self.abilities[0] if self.abilities else None
        
        # Call the parent Card constructor
        super().__init__(id, name, type, subtype, set, pack, rarity, image_url, first_ability)

        self.element: Energy.Type = element
        self.health: int = health # This is the original max health of the pokemon (base HP)
        self._base_health: int = health # Store base HP for tool calculations
        self.attacks: list[Attack] = attacks
        self.retreat_cost: int = retreat_cost
        self.weakness: Energy.Type = weakness
        self.evolves_from = evolves_from

        import builtins
        self.pokemon_types = builtins.set()
        self.pokemon_types.add(Pokemon.PokemonType.EX) if name.endswith(' ex') else None


        # STILL NEED TO FIGURE OUT THESE VALUES
        # Evolution tracking
        self.evolves_from_ids = []
        self.evolves_to_ids = []

        # Status effects
        self.status_effects: List = []  # List of StatusEffect objects
        
        # Game variables
        self.poketool: Tool = None
        self._can_retreat_flag = True  # Internal flag for retreat permission
        self.damage_nerf = 0
        self.damage_taken = 0
        self.effect_status = []
        self.equipped_energies: Dict[Energy.Type, int] = {
            Energy.Type.GRASS: 0,
            Energy.Type.FIRE: 0,
            Energy.Type.WATER: 0,
            Energy.Type.ELECTRIC: 0,
            Energy.Type.PSYCHIC: 0,
            Energy.Type.ROCK: 0,  # Fighting maps to Rock
            Energy.Type.DARK: 0,
            Energy.Type.METAL: 0,
            Energy.Type.NORMAL: 0,
        }
        self.placed_or_evolved_this_turn: bool = False  # Changed from 1 to False
        self.used_ability_this_turn = False
        self.turns_in_play: int = 0  # Increment at end of each turn
        self.attacked_this_turn: bool = False  # Reset at end of turn
    
    def current_health(self) -> int:
        """Get current health (max HP - damage taken)"""
        return self.max_health() - self.damage_taken
    
    def max_health(self) -> int:
        """Get maximum health including tool bonuses"""
        max_hp = self._base_health
        
        # Apply tool HP bonuses
        if self.poketool and self.poketool.ability:
            effect = self.poketool.ability.effect
            if effect:
                # Check for HP bonus effects (e.g., "hp_bonus(20)" or "+20 HP")
                import re
                effect_lower = effect.lower()
                # Look for hp_bonus pattern
                hp_bonus_match = re.search(r'hp_bonus\((\d+)\)', effect_lower)
                if hp_bonus_match:
                    bonus = int(hp_bonus_match.group(1))
                    max_hp += bonus
                # Also check for "+X HP" pattern (more flexible, handles period at end)
                else:
                    plus_hp_match = re.search(r'\+(\d+)\s*hp\.?', effect_lower)
                    if plus_hp_match:
                        bonus = int(plus_hp_match.group(1))
                        max_hp += bonus
        
        return max_hp
    
    def to_display_string(self) -> str:
        """Generate a detailed string representation of the Pokemon for display."""
        lines = []
        
        # Header with name and element
        max_hp = self.max_health()
        current_hp = self.current_health()
        health_str = f"{current_hp}/{max_hp}" if self.damage_taken > 0 else str(max_hp)
        lines.append(f"{self.name} [{self.element.upper()}] HP: {health_str}")
        
        # Show tool if attached
        if self.poketool:
            lines.append(f"Tool: {self.poketool.name}")
        
        # Abilities if present
        if self.abilities:
            for ability in self.abilities:
                lines.append(f"Ability: {ability.name} - {ability.effect}")
        
        # Attacks
        if self.attacks:
            lines.append("Attacks:")
            for attack in self.attacks:
                energy_cost = []
                # Attack.cost is an Energy object, access its cost dict
                cost_dict = attack.cost.cost if hasattr(attack.cost, 'cost') else attack.cost
                for energy_type, amount in cost_dict.items():
                    if amount > 0:
                        # Format energy type for display
                        if energy_type == Energy.Type.NORMAL:
                            energy_display = "Colorless"
                        else:
                            energy_display = str(energy_type).capitalize()
                        energy_cost.append(f"{amount}x{energy_display}")
                cost_str = ", ".join(energy_cost) if energy_cost else "No cost"
                damage = attack.damage if attack.damage else 0
                lines.append(f"  - {attack.name} ({cost_str}) - {damage} dmg")
        
        # Weakness
        if self.weakness:
            lines.append(f"Weakness: {self.weakness}")
        
        # Retreat cost
        if self.retreat_cost > 0:
            lines.append(f"Retreat Cost: {self.retreat_cost}")
        
        return "\n".join(lines)
    
    @property
    def is_ex(self) -> bool:
        """Check if Pokemon is EX variant"""
        return self.name.endswith(' ex')
    
    def get_possible_attacks(self) -> List['Attack']:
        """Return attacks that can be used (energy cost met)"""
        possible = []
        for attack in self.attacks:
            if self._can_afford_attack(attack):
                possible.append(attack)
        return possible
    
    def _can_afford_attack(self, attack: 'Attack') -> bool:
        """Check if Pokemon has enough energy for attack
        
        Note: Energy is NOT discarded when using an attack in Pokemon TCG Pocket.
        This method only checks if the energy requirements are met.
        
        Rules:
        - Colorless energy can be satisfied by ANY energy type
        - Specific types (Grass, Fire, etc.) must be that specific type
        - We need enough total energy to satisfy all requirements
        """
        # Attack.cost is an Energy object, so we need to access its cost dict
        attack_cost = attack.cost.cost if hasattr(attack.cost, 'cost') else attack.cost
        available_energy = self.equipped_energies.copy()
        
        # Calculate total energy needed and specific type requirements
        total_required = 0
        specific_requirements = {}  # Type -> amount needed
        
        for energy_type, required_amount in attack_cost.items():
            if required_amount == 0:
                continue
            
            total_required += required_amount
            
            # Colorless can be satisfied by any energy, so don't add to specific requirements
            if energy_type != Energy.Type.NORMAL:
                specific_requirements[energy_type] = specific_requirements.get(energy_type, 0) + required_amount
        
        # Check if we have enough total energy
        total_available = sum(available_energy.values())
        if total_available < total_required:
            return False
        
        # Check if we have enough of each specific type required
        # For specific types, we need that exact type (can't use Colorless substitution)
        for energy_type, required_amount in specific_requirements.items():
            specific_available = available_energy.get(energy_type, 0)
            if specific_available < required_amount:
                return False
        
        # All requirements met
        return True
    
    def get_usable_abilities(self) -> List[Ability]:
        """Get abilities that can be used this turn"""
        usable = []
        for ability in self.abilities:
            # Check if ability can be used (not used this turn, etc.)
            if not self.used_ability_this_turn:
                usable.append(ability)
        return usable
    
    def has_status_effect(self, status_type):
        """Check if Pokemon has specific status effect"""
        return any(isinstance(se, status_type) for se in self.status_effects)
    
    def can_attack(self) -> bool:
        """Check if Pokemon can attack (not Asleep, Paralyzed, or Confused self-hit)"""
        from v3.models.match.status_effects.asleep import Asleep
        from v3.models.match.status_effects.paralyzed import Paralyzed
        if self.has_status_effect(Asleep):
            return False
        if self.has_status_effect(Paralyzed):
            return False
        return True
    
    def can_retreat(self) -> bool:
        """Check if Pokemon can retreat (not Paralyzed and flag is True)"""
        from v3.models.match.status_effects.paralyzed import Paralyzed
        if not self._can_retreat_flag:
            return False
        if self.has_status_effect(Paralyzed):
            return False
        return True