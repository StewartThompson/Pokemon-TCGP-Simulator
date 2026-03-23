# These are the attacks that a pokemon can use
class Attack:
    def __init__(self, id, name, effect, damage, cost=None):
        self.id = id
        self.name = name
        self.effect = effect
        self.damage = damage
        self.cost = cost if cost else {'fire': 0, 'water': 0, 'rock': 0, 'grass': 0, 'normal': 0, 'electric': 0, 'psychic': 0, 'dark': 0, 'metal': 0, 'dragon': 0, 'fairy': 0}

    def __str__(self):
        return f"{self.name} ({self.damage} damage) ({self.cost})"
    
    def has_enough_energy_for_attack(self, player):
        for energy_type, cost_amount in self.cost.items():
            if player.equipped_energies[energy_type.lower()] < cost_amount:
                return False
        return True
    
    