class Energy:
    class Type:
        FIRE = 'fire'
        WATER = 'water'
        ROCK = 'rock'
        GRASS = 'grass'
        NORMAL = 'normal'
        ELECTRIC = 'electric'
        PSYCHIC = 'psychic'
        DARK = 'dark'
        METAL = 'metal'

    def __init__(self, cost: dict[Type, int] = None):
        self.cost: dict[Energy.Type, int] = cost if cost else {
            Energy.Type.FIRE: 0,
            Energy.Type.WATER: 0,
            Energy.Type.ROCK: 0,
            Energy.Type.GRASS: 0,
            Energy.Type.NORMAL: 0,
            Energy.Type.ELECTRIC: 0,
            Energy.Type.PSYCHIC: 0,
            Energy.Type.DARK: 0,
            Energy.Type.METAL: 0
        }

    @classmethod
    def from_string_list(cls, energy_list: list[str]) -> 'Energy':
        """Create an Energy object from a list of energy type strings"""
        cost = {
            Energy.Type.FIRE: 0,
            Energy.Type.WATER: 0,
            Energy.Type.ROCK: 0,
            Energy.Type.GRASS: 0,
            Energy.Type.NORMAL: 0,
            Energy.Type.ELECTRIC: 0,
            Energy.Type.PSYCHIC: 0,
            Energy.Type.DARK: 0,
            Energy.Type.METAL: 0
        }
        
        # Map string names to Energy.Type values
        energy_map = {
            'FIRE': Energy.Type.FIRE,
            'WATER': Energy.Type.WATER,
            'ROCK': Energy.Type.ROCK,
            'GRASS': Energy.Type.GRASS,
            'NORMAL': Energy.Type.NORMAL,
            'COLORLESS': Energy.Type.NORMAL,  # Colorless maps to Normal
            'ELECTRIC': Energy.Type.ELECTRIC,
            'PSYCHIC': Energy.Type.PSYCHIC,
            'DARK': Energy.Type.DARK,
            'DARKNESS': Energy.Type.DARK,
            'METAL': Energy.Type.METAL,
        }
        
        for energy_str in energy_list:
            energy_upper = energy_str.upper()
            if energy_upper in energy_map:
                energy_type = energy_map[energy_upper]
                cost[energy_type] += 1
            else:
                raise ValueError(f"Unknown energy type: {energy_str}")
        
        return cls(cost)

    @classmethod
    def from_string(cls, energy_str: str) -> 'Energy':
        """Create an Energy object from a single energy type string"""
        return cls.from_string_list([energy_str])

    def can_afford(self, required_energy: 'Energy') -> bool:
        """Check if this energy can afford the required energy cost"""
        for energy_type, required_amount in required_energy.cost.items():
            if self.cost[energy_type] < required_amount:
                return False
        return True

    def get_total_cost(self) -> int:
        """Get the total number of energy required"""
        return sum(self.cost.values())

    def is_empty(self) -> bool:
        """Check if no energy is required"""
        return self.get_total_cost() == 0

    def __str__(self) -> str:
        """String representation of energy cost"""
        parts = []
        for energy_type, amount in self.cost.items():
            if amount > 0:
                parts.append(f"{amount} {energy_type}")
        return ", ".join(parts) if parts else "No energy required"

    def __repr__(self) -> str:
        return f"Energy({self.cost})"
