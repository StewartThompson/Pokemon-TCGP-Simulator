from .card import Card
from .tool import Tool
from .attack import Attack
from .ability import Ability
from game.ids.action_id_generation import ActionIdGenerator
from game.ids.stages import STAGES
class Pokemon(Card):
    def __init__(self, id, name, element, type, subtype, stage, health, set, pack, attacks, retreat_cost, weakness, abilities, evolves_from, rarity, action_ids):
        # Call the parent Card constructor
        super().__init__(id, name, type, subtype, set, pack, rarity, action_ids)

        self.element = element
        self.stage = stage
        self.max_hp = health
        self.attacks: list[Attack] = attacks
        self.retreat_cost = retreat_cost
        self.weakness = weakness
        self.abilities: list[Ability] = abilities
        self.evolves_from = evolves_from

        # Additional inferred variables
        self.is_ex = True if name.endswith(' ex') else False

        # Evolution tracking
        self.evolves_from_ids = []
        self.evolves_to_ids = []

        # Game variables
        self.poketool: Tool = None
        self.can_retreat = True
        self.damage_nerf = 0
        self.damage_taken = 0
        self.effect_status = []
        self.equipped_energies = {'grass': 0, 'fire': 0, 'water': 0, 'lightning': 0, 'psychic': 0, 'fighting': 0, 'darkness': 0, 'metal': 0, 'fairy': 0, 'normal': 0}
        self.placed_or_evolved_this_turn = 1
        self.used_ability_this_turn = False

    def add_evolves_from_id(self, pokemon_id):
        """Add a Pokemon ID that this Pokemon can evolve from"""
        if pokemon_id not in self.evolves_from_ids:
            self.evolves_from_ids.append(pokemon_id)
    
    def add_evolves_to_id(self, pokemon_id):
        """Add a Pokemon ID that this Pokemon can evolve to"""
        if pokemon_id not in self.evolves_to_ids:
            self.evolves_to_ids.append(pokemon_id)
    
    def get_evolves_from_ids(self):
        """Get list of Pokemon IDs this can evolve from"""
        return self.evolves_from_ids.copy()
    
    def get_evolves_to_ids(self):
        """Get list of Pokemon IDs this can evolve to"""
        return self.evolves_to_ids.copy()
    
    def get_hp(self):
        """Get the current HP of the Pokemon"""
        return self.max_hp - self.damage_taken

    def __str__(self):
        return f"{self.name} ({self.element} - {self.max_hp} HP)"
    
    def _get_actions(self, player, opponent_pokemon_locations):
        """Get all possible actions for the Pokemon"""

        available_actions = []
        
        for action_id in self.action_ids:
            if '_action_retreat_' in action_id:
                if self.can_retreat and sum(self.equipped_energies.values()) >= self.retreat_cost:
                    available_actions.append(action_id)
                
            elif '_action_evolve_' in action_id:
                if self._can_evolve_pokemeon(player):
                    available_actions.append(action_id)

            elif '_action_attack_' in action_id:
                for attack in self.attacks:
                    if attack.has_enough_energy_for_attack(player) and self.card_position == Card.Position.ACTIVE:
                        if 'oactive' in action_id and opponent_pokemon_locations[0] == 1:
                            available_actions.append(action_id)
                        elif 'obench1' in action_id and opponent_pokemon_locations[1] == 1:
                            available_actions.append(action_id)
                        elif 'obench2' in action_id and opponent_pokemon_locations[2] == 1:
                            available_actions.append(action_id)
                        elif 'obench3' in action_id and opponent_pokemon_locations[3] == 1:
                            available_actions.append(action_id)
                
            elif '_action_ability_' in action_id:
                continue

            elif '_play_' in action_id:
                if self.stage == 'basic' and self.card_position == Card.Position.HAND:
                    if 'pactive' in action_id and player.active_pokemon is None:
                        available_actions.append(action_id)
                    elif player.bench_pokemons[0] is None:
                        available_actions.append(action_id)
                    elif player.bench_pokemons[1] is None:
                        available_actions.append(action_id)
                    elif player.bench_pokemons[2] is None:
                        available_actions.append(action_id)
            

        # available_actions.extend(self._get_attack_action_ids())
        # available_actions.extend(self._get_ability_action_ids())

        return available_actions
    
    def _can_evolve_pokemeon(self, player):
        """Get the evolve action ids for the Pokemon"""
        for card in [player.active_pokemon] + player.bench_pokemons:
            if isinstance(card, Pokemon) and card.id in self.get_evolves_from_ids() and card.placed_or_evolved_this_turn == 0:
                return True
        return False
        