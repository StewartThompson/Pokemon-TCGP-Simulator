"""Attach Tool action - attach a Tool trainer card to a Pokemon"""
from typing import Optional
from .action import Action, ActionType
from v3.models.cards.tool import Tool
from v3.models.cards.pokemon import Pokemon
from v3.models.cards.card import Card

class AttachToolAction(Action):
    """Action to attach a Tool card to a Pokemon"""
    
    def __init__(self, tool_id: str, pokemon_location: str):
        super().__init__(ActionType.ATTACH_TOOL)
        self.tool_id = tool_id
        self.pokemon_location = pokemon_location  # "active" or "bench_{index}"
    
    def validate(self, player, battle_engine) -> tuple[bool, Optional[str]]:
        """Validate if tool can be attached"""
        tool = next((c for c in player.cards_in_hand if c.id == self.tool_id), None)
        if not tool:
            return False, f"Tool {self.tool_id} not in hand"
        
        if not isinstance(tool, Tool):
            return False, f"Card {self.tool_id} is not a Tool"
        
        # Get target Pokemon
        target = self._get_target_pokemon(player)
        if not target:
            return False, f"No Pokemon at location: {self.pokemon_location}"
        
        # Note: Pokemon can have tools replaced (old tool is discarded when new one is attached)
        # No need to check if Pokemon already has a tool - we'll handle replacement in execute()
        
        if not player.can_play_trainer:
            return False, "Cannot play trainer cards this turn"
        
        return True, None
    
    def _get_target_pokemon(self, player) -> Optional[Pokemon]:
        """Get Pokemon at target location"""
        if self.pokemon_location == "active":
            return player.active_pokemon
        elif self.pokemon_location.startswith("bench_"):
            try:
                bench_index = int(self.pokemon_location.split("_")[1])
                if 0 <= bench_index < len(player.bench_pokemons):
                    return player.bench_pokemons[bench_index]
            except (ValueError, IndexError):
                pass
        return None
    
    def execute(self, player, battle_engine) -> None:
        """Execute attaching tool"""
        tool = next((c for c in player.cards_in_hand if c.id == self.tool_id), None)
        target = self._get_target_pokemon(player)
        
        if not tool or not isinstance(tool, Tool):
            raise ValueError(f"Tool {self.tool_id} not found")
        if not target:
            raise ValueError(f"Target Pokemon not found at {self.pokemon_location}")
        
        # If Pokemon already has a tool, discard it first
        if target.poketool is not None:
            old_tool = target.poketool
            target.poketool = None
            player.discard_card(old_tool)
            battle_engine.log(f"{player.name} discarded {old_tool.name} from {target.name}")
        
        # Remove from hand
        player.cards_in_hand.remove(tool)
        
        # Attach to Pokemon
        target.poketool = tool
        tool.card_position = Card.Position.ACTIVE if self.pokemon_location == "active" else Card.Position.BENCH
        
        # Log tool effect if it has one
        effect_msg = ""
        if tool.ability and tool.ability.effect:
            effect_msg = f" ({tool.ability.effect})"
        
        battle_engine.log(f"{player.name} attached {tool.name} to {target.name}{effect_msg}")
        
        # Apply tool effects immediately (e.g., HP bonuses)
        # The max_health() method will automatically account for tool bonuses
    
    def to_string(self) -> str:
        return f"attach_tool_{self.tool_id}_{self.pokemon_location}"
    
    @classmethod
    def from_string(cls, action_str: str, player) -> 'AttachToolAction':
        if not action_str.startswith("attach_tool_"):
            raise ValueError(f"Invalid action string: {action_str}")
        parts = action_str.replace("attach_tool_", "").split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid tool action format: {action_str}")
        return cls(parts[0], parts[1])

