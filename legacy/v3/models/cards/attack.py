from .ability import Ability
from .energy import Energy

# These are the attacks that a pokemon can use
class Attack:
    def __init__(self, name: str, damage: int, cost: Energy = None, ability: Ability = None):
        self.name: str = name
        self.ability: Ability = ability
        self.cost: dict[Energy.Type, int] = Energy(cost).cost if cost else Energy().cost
        self.damage: int = damage


