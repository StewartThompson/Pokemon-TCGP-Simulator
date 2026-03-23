# This would be like a pokemon but without alot of the variables
from .card import Card
from .tool import Tool
class Fossil(Card):
    def __init__(self, id, name, type, subtype, health, set, pack, abilities, rarity):
        # Call the parent Card constructor
        super().__init__(id, name, type, subtype, set, pack, rarity)

        self.max_hp = health
        self.abilities = abilities

        # Evolution tracking (same as Pokemon)
        self.evolves_from_ids = []
        self.evolves_to_ids = []

        # Game variables
        self.poketool: Tool = None
        self.can_retreat = False  # Fossils typically can't retreat
        self.damage_nerf = 0
        self.damage_taken = 0
        self.effect_status = []
        self.equipped_energies = {'grass': 0, 'fire': 0, 'water': 0, 'lightning': 0, 'psychic': 0, 'fighting': 0, 'darkness': 0, 'metal': 0, 'fairy': 0, 'normal': 0}
        self.placed_or_evolved_this_turn = 1
        self.used_ability_this_turn = False

    def add_evolves_from_id(self, pokemon_id):
        """Add a Pokemon ID that this Fossil can evolve from"""
        if pokemon_id not in self.evolves_from_ids:
            self.evolves_from_ids.append(pokemon_id)
    
    def add_evolves_to_id(self, pokemon_id):
        """Add a Pokemon ID that this Fossil can evolve to"""
        if pokemon_id not in self.evolves_to_ids:
            self.evolves_to_ids.append(pokemon_id)
    
    def get_evolves_from_ids(self):
        """Get list of Pokemon IDs this can evolve from"""
        return self.evolves_from_ids.copy()
    
    def get_evolves_to_ids(self):
        """Get list of Pokemon IDs this can evolve to"""
        return self.evolves_to_ids.copy()
    
    def get_hp(self):
        """Get the current HP of the Fossil"""
        return self.max_hp - self.damage_taken

    def __str__(self):
        return f"{self.name} (Fossil - {self.max_hp} HP)"


