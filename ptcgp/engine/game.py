"""Core game state and game logic for PTCGP."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Optional

from .types import (
    EnergyType, PokemonStage, CardType, StatusEffect, GamePhase,
    ActionType, EffectType, NUM_ACTIONS,
    DECK_SIZE, BENCH_SIZE, MAX_HAND_SIZE, INITIAL_HAND_SIZE,
    POINTS_TO_WIN, POINTS_PER_KO, POINTS_PER_EX_KO,
    WEAKNESS_BONUS, POISON_DAMAGE, BURN_DAMAGE, CONFUSION_SELF_DAMAGE,
    MAX_TURNS,
)
from .cards import CardData, get_card, Attack, AttackEffect


@dataclass
class PokemonSlot:
    """A slot on the field (active or bench) holding a Pokemon."""
    card_id: Optional[str] = None
    current_hp: int = 0
    max_hp: int = 0
    attached_energy: dict[EnergyType, int] = field(default_factory=dict)
    status_effects: set[StatusEffect] = field(default_factory=set)
    turns_in_play: int = 0
    tool_card_id: Optional[str] = None
    evolved_this_turn: bool = False
    ability_used_this_turn: bool = False
    cant_attack_next_turn: bool = False
    _card_cache: Optional[CardData] = field(default=None, repr=False, compare=False)

    @property
    def is_empty(self) -> bool:
        return self.card_id is None

    @property
    def card(self) -> Optional[CardData]:
        if self._card_cache is not None and self._card_cache.id == self.card_id:
            return self._card_cache
        if self.card_id is None:
            self._card_cache = None
            return None
        self._card_cache = get_card(self.card_id)
        return self._card_cache

    @property
    def is_knocked_out(self) -> bool:
        return not self.is_empty and self.current_hp <= 0

    @property
    def total_energy(self) -> int:
        return sum(self.attached_energy.values())

    def has_energy_for(self, cost: dict[EnergyType, int]) -> bool:
        """Check if this Pokemon has enough energy to pay a cost."""
        available = dict(self.attached_energy)
        colorless_needed = 0
        for etype, count in cost.items():
            if etype == EnergyType.COLORLESS:
                colorless_needed += count
            else:
                if available.get(etype, 0) < count:
                    return False
                available[etype] = available.get(etype, 0) - count
        # Colorless can be paid by any remaining energy
        remaining = sum(available.values())
        return remaining >= colorless_needed

    def copy(self) -> PokemonSlot:
        return PokemonSlot(
            card_id=self.card_id,
            current_hp=self.current_hp,
            max_hp=self.max_hp,
            attached_energy=dict(self.attached_energy),
            status_effects=set(self.status_effects),
            turns_in_play=self.turns_in_play,
            tool_card_id=self.tool_card_id,
            evolved_this_turn=self.evolved_this_turn,
            ability_used_this_turn=self.ability_used_this_turn,
            cant_attack_next_turn=self.cant_attack_next_turn,
            _card_cache=self._card_cache,
        )


@dataclass
class PlayerState:
    """All state for one player."""
    active: PokemonSlot = field(default_factory=PokemonSlot)
    bench: list[PokemonSlot] = field(default_factory=lambda: [PokemonSlot() for _ in range(BENCH_SIZE)])
    hand: list[str] = field(default_factory=list)  # Card IDs
    deck: list[str] = field(default_factory=list)   # Card IDs (top of deck = index 0)
    discard: list[str] = field(default_factory=list)
    points: int = 0
    energy_types: list[EnergyType] = field(default_factory=list)  # Selected energy types (1-3)

    # Per-turn flags (reset at start of each turn)
    has_attached_energy: bool = False
    has_played_supporter: bool = False
    has_retreated: bool = False
    pokemon_played_this_turn: set[str] = field(default_factory=set)  # Slot IDs that had pokemon played

    def all_pokemon_slots(self) -> list[tuple[str, PokemonSlot]]:
        """Return all pokemon slots with labels."""
        result = [("active", self.active)]
        for i, slot in enumerate(self.bench):
            result.append((f"bench_{i}", slot))
        return result

    def non_empty_bench(self) -> list[tuple[int, PokemonSlot]]:
        """Return non-empty bench slots with indices."""
        return [(i, s) for i, s in enumerate(self.bench) if not s.is_empty]

    def empty_bench_slots(self) -> list[int]:
        """Return indices of empty bench slots."""
        return [i for i, s in enumerate(self.bench) if s.is_empty]

    def has_pokemon_in_play(self) -> bool:
        """Check if player has any Pokemon in play."""
        if not self.active.is_empty:
            return True
        return any(not s.is_empty for s in self.bench)

    def copy(self) -> PlayerState:
        return PlayerState(
            active=self.active.copy(),
            bench=[s.copy() for s in self.bench],
            hand=list(self.hand),
            deck=list(self.deck),
            discard=list(self.discard),
            points=self.points,
            energy_types=list(self.energy_types),
            has_attached_energy=self.has_attached_energy,
            has_played_supporter=self.has_played_supporter,
            has_retreated=self.has_retreated,
            pokemon_played_this_turn=set(self.pokemon_played_this_turn),
        )


@dataclass
class GameState:
    """Complete game state. Designed to be cheaply copyable."""
    players: list[PlayerState] = field(default_factory=lambda: [PlayerState(), PlayerState()])
    turn_number: int = 0
    current_player: int = 0  # 0 or 1
    phase: GamePhase = GamePhase.SETUP
    winner: Optional[int] = None
    energy_available: Optional[EnergyType] = None  # Energy generated this turn

    # For multi-step actions
    pending_action: Optional[dict] = None  # Context for target selection

    # RNG state
    rng: random.Random = field(default_factory=random.Random)

    @property
    def current(self) -> PlayerState:
        return self.players[self.current_player]

    @property
    def opponent(self) -> PlayerState:
        return self.players[1 - self.current_player]

    @property
    def is_first_turn(self) -> bool:
        return self.turn_number <= 1

    @property
    def is_game_over(self) -> bool:
        return self.phase == GamePhase.GAME_OVER

    def copy(self, copy_rng: bool = True) -> GameState:
        new = GameState(
            players=[p.copy() for p in self.players],
            turn_number=self.turn_number,
            current_player=self.current_player,
            phase=self.phase,
            winner=self.winner,
            energy_available=self.energy_available,
            pending_action=dict(self.pending_action) if self.pending_action else None,
            rng=self.rng,  # Share RNG by default (fast)
        )
        if copy_rng:
            new.rng = random.Random()
            new.rng.setstate(self.rng.getstate())
        return new


# ============================================================
# Game initialization
# ============================================================

def create_game(
    deck1: list[str],
    deck2: list[str],
    energy_types1: list[EnergyType],
    energy_types2: list[EnergyType],
    seed: Optional[int] = None,
) -> GameState:
    """Create a new game with two decks. Returns state in SETUP phase."""
    state = GameState()
    if seed is not None:
        state.rng = random.Random(seed)
    else:
        state.rng = random.Random()

    # Set up player decks and energy types
    for i, (deck, etypes) in enumerate([(deck1, energy_types1), (deck2, energy_types2)]):
        state.players[i].deck = list(deck)
        state.players[i].energy_types = list(etypes)
        state.rng.shuffle(state.players[i].deck)

    # Draw initial hands (guaranteed to have at least 1 Basic)
    for i in range(2):
        _draw_initial_hand(state, i)

    # Coin flip for first player
    state.current_player = state.rng.randint(0, 1)

    return state


def _draw_initial_hand(state: GameState, player_idx: int) -> None:
    """Draw initial hand, ensuring at least one Basic Pokemon."""
    player = state.players[player_idx]
    max_attempts = 100

    for _ in range(max_attempts):
        # Reset deck and hand
        full_deck = player.deck + player.hand
        state.rng.shuffle(full_deck)
        player.deck = full_deck
        player.hand = []

        # Draw INITIAL_HAND_SIZE cards
        for _ in range(min(INITIAL_HAND_SIZE, len(player.deck))):
            player.hand.append(player.deck.pop(0))

        # Check for at least one Basic
        if any(get_card(cid).is_basic for cid in player.hand if get_card(cid).is_pokemon):
            return

    # Safety: if we can't find a Basic after many attempts, just draw anyway
    # (This shouldn't happen with valid decks)


def setup_active_pokemon(state: GameState, player_idx: int, hand_index: int) -> GameState:
    """Place a Basic Pokemon from hand as the active Pokemon during setup."""
    state = state.copy()
    player = state.players[player_idx]
    card_id = player.hand[hand_index]
    card = get_card(card_id)

    if not card.is_pokemon or not card.is_basic:
        raise ValueError(f"Card {card.name} is not a Basic Pokemon")

    player.hand.pop(hand_index)
    player.active = PokemonSlot(
        card_id=card_id,
        current_hp=card.hp,
        max_hp=card.hp,
    )
    return state


def setup_bench_pokemon(state: GameState, player_idx: int, hand_index: int) -> GameState:
    """Place a Basic Pokemon from hand on the bench during setup."""
    state = state.copy()
    player = state.players[player_idx]
    card_id = player.hand[hand_index]
    card = get_card(card_id)

    if not card.is_pokemon or not card.is_basic:
        raise ValueError(f"Card {card.name} is not a Basic Pokemon")

    empty = player.empty_bench_slots()
    if not empty:
        raise ValueError("No empty bench slots")

    player.hand.pop(hand_index)
    slot_idx = empty[0]
    player.bench[slot_idx] = PokemonSlot(
        card_id=card_id,
        current_hp=card.hp,
        max_hp=card.hp,
    )
    return state


def start_game(state: GameState) -> GameState:
    """Transition from SETUP to first turn."""
    state = state.copy()
    state.phase = GamePhase.MAIN
    state.turn_number = 1
    _start_turn(state)
    return state


def _start_turn(state: GameState) -> None:
    """Begin a new turn (mutates state in-place)."""
    player = state.current

    # Reset per-turn flags
    player.has_attached_energy = False
    player.has_played_supporter = False
    player.has_retreated = False
    player.pokemon_played_this_turn.clear()

    # Reset per-turn pokemon flags
    for _, slot in player.all_pokemon_slots():
        slot.evolved_this_turn = False
        slot.ability_used_this_turn = False

    # Draw a card (skip if hand is at max)
    if len(player.hand) < MAX_HAND_SIZE and len(player.deck) > 0:
        player.hand.append(player.deck.pop(0))
    # No deck-out loss in PTCGP - just skip draw

    # Generate energy
    is_first_player_first_turn = (state.turn_number == 1 and state.current_player == 0) or \
                                  (state.turn_number == 1 and state.current_player == state.current_player)
    # Actually: first player's first turn = turn_number 1
    # The player who goes first does NOT get energy on turn 1
    if state.turn_number == 1:
        state.energy_available = None
    else:
        if player.energy_types:
            state.energy_available = state.rng.choice(player.energy_types)
        else:
            state.energy_available = None

    state.phase = GamePhase.MAIN


# ============================================================
# Action generation
# ============================================================

def get_legal_actions(state: GameState) -> list[ActionType]:
    """Get all legal actions for the current player."""
    if state.phase == GamePhase.GAME_OVER:
        return []

    if state.phase == GamePhase.AWAITING_TARGET:
        return _get_target_actions(state)

    if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
        return _get_promotion_actions(state)

    if state.phase != GamePhase.MAIN:
        return []

    player = state.current
    opponent = state.opponent
    actions: list[ActionType] = []

    # Always can end turn
    actions.append(ActionType.END_TURN)

    active = player.active
    active_card = active.card

    if active_card and not active.is_empty:
        # Attacks (not on first turn for first player)
        can_attack = state.turn_number > 1 or state.current_player != _first_player(state)
        if can_attack and not active.cant_attack_next_turn:
            for i, attack in enumerate(active_card.attacks[:2]):
                if active.has_energy_for(attack.cost):
                    # Check confusion - still allowed to try (resolved during attack)
                    action = ActionType.ATTACK_0 if i == 0 else ActionType.ATTACK_1
                    actions.append(action)

        # Retreat (once per turn, must have bench pokemon, can't retreat if paralyzed/asleep)
        if (not player.has_retreated
            and active.total_energy >= active_card.retreat_cost
            and StatusEffect.PARALYZED not in active.status_effects
            and StatusEffect.ASLEEP not in active.status_effects
            and any(not s.is_empty for s in player.bench)):
            for i, slot in enumerate(player.bench):
                if not slot.is_empty:
                    actions.append(ActionType(ActionType.RETREAT_BENCH_0 + i))

        # Use ability (active)
        if (active_card.ability and not active_card.ability.is_passive
            and not active.ability_used_this_turn):
            actions.append(ActionType.ABILITY_ACTIVE)

    # Bench abilities
    for i, slot in enumerate(player.bench):
        if not slot.is_empty and slot.card:
            card = slot.card
            if (card.ability and not card.ability.is_passive
                and not slot.ability_used_this_turn):
                actions.append(ActionType(ActionType.ABILITY_BENCH_0 + i))

    # Attach energy (once per turn, must have energy available)
    if not player.has_attached_energy and state.energy_available is not None:
        # Can attach to any pokemon in play
        if not active.is_empty:
            actions.append(ActionType.ENERGY_ACTIVE)
        for i, slot in enumerate(player.bench):
            if not slot.is_empty:
                actions.append(ActionType(ActionType.ENERGY_BENCH_0 + i))

    # Play cards from hand
    for hand_idx in range(min(len(player.hand), 10)):
        card_id = player.hand[hand_idx]
        card = get_card(card_id)

        if card.card_type == CardType.POKEMON:
            if card.is_basic:
                # Play Basic to bench (if there's room)
                if player.empty_bench_slots():
                    actions.append(ActionType(ActionType.PLAY_HAND_0 + hand_idx))
            else:
                # Evolution - check if valid target exists
                can_evolve = state.turn_number > 1  # Can't evolve turn 1
                if can_evolve:
                    for _, slot in player.all_pokemon_slots():
                        if not slot.is_empty and slot.card and _can_evolve(slot, card, state):
                            actions.append(ActionType(ActionType.PLAY_HAND_0 + hand_idx))
                            break

        elif card.card_type == CardType.ITEM:
            actions.append(ActionType(ActionType.PLAY_HAND_0 + hand_idx))

        elif card.card_type == CardType.SUPPORTER:
            if not player.has_played_supporter:
                actions.append(ActionType(ActionType.PLAY_HAND_0 + hand_idx))

        elif card.card_type == CardType.TOOL:
            # Can attach if any pokemon doesn't have a tool
            for _, slot in player.all_pokemon_slots():
                if not slot.is_empty and slot.tool_card_id is None:
                    actions.append(ActionType(ActionType.PLAY_HAND_0 + hand_idx))
                    break

    # Deduplicate
    return sorted(set(actions), key=lambda a: a.value)


def _first_player(state: GameState) -> int:
    """Return the index of the player who went first."""
    # The first player is whoever played turn 1
    # We track this implicitly: on turn 1, current_player is the first player
    # After that we alternate. Player who went first plays on odd turns.
    # Actually we need to store this. For now, player 0 goes first if turn 1 cp is 0.
    return 0  # Simplified - the coin flip sets current_player at start


def _can_evolve(slot: PokemonSlot, evo_card: CardData, state: GameState) -> bool:
    """Check if a Pokemon in a slot can evolve into evo_card."""
    if slot.is_empty or not slot.card:
        return False
    if slot.evolved_this_turn:
        return False
    if slot.turns_in_play < 1:
        return False
    if evo_card.evolves_from != slot.card.name:
        return False
    return True


def _get_target_actions(state: GameState) -> list[ActionType]:
    """Get valid target selection actions."""
    if not state.pending_action:
        return [ActionType.END_TURN]

    actions: list[ActionType] = []
    ctx = state.pending_action
    target_type = ctx.get("target_type", "own")

    if target_type == "own":
        player = state.current
        if not player.active.is_empty:
            actions.append(ActionType.TARGET_ACTIVE)
        for i, slot in enumerate(player.bench):
            if not slot.is_empty:
                actions.append(ActionType(ActionType.TARGET_BENCH_0 + i))
    elif target_type == "opponent":
        opp = state.opponent
        if not opp.active.is_empty:
            actions.append(ActionType.TARGET_OPP_ACTIVE)
        for i, slot in enumerate(opp.bench):
            if not slot.is_empty:
                actions.append(ActionType(ActionType.TARGET_OPP_BENCH_0 + i))
    elif target_type == "own_bench":
        player = state.current
        for i, slot in enumerate(player.bench):
            if not slot.is_empty:
                actions.append(ActionType(ActionType.TARGET_BENCH_0 + i))

    return actions


def _get_promotion_actions(state: GameState) -> list[ActionType]:
    """Get actions for choosing which bench Pokemon to promote."""
    # The player whose active was KO'd needs to choose a bench pokemon
    # Determine which player needs to promote
    for p_idx in range(2):
        player = state.players[p_idx]
        if player.active.is_empty and any(not s.is_empty for s in player.bench):
            actions = []
            for i, slot in enumerate(player.bench):
                if not slot.is_empty:
                    actions.append(ActionType(ActionType.TARGET_BENCH_0 + i))
            return actions
    return [ActionType.END_TURN]


# ============================================================
# Action application
# ============================================================

def apply_action(state: GameState, action: ActionType, copy: bool = False) -> GameState:
    """Apply an action to the game state. Mutates in-place by default.

    Args:
        state: Game state to modify
        action: Action to apply
        copy: If True, copy state first (for search/MCTS). Default False for speed.
    """
    if copy:
        state = state.copy()

    if state.phase == GamePhase.AWAITING_TARGET:
        return _apply_target_selection(state, action)

    if state.phase == GamePhase.AWAITING_BENCH_PROMOTION:
        return _apply_bench_promotion(state, action)

    if state.phase != GamePhase.MAIN:
        return state

    player = state.current
    opponent = state.opponent

    if action == ActionType.END_TURN:
        return _end_turn(state)

    elif action in (ActionType.ATTACK_0, ActionType.ATTACK_1):
        return _execute_attack(state, 0 if action == ActionType.ATTACK_0 else 1)

    elif action in (ActionType.RETREAT_BENCH_0, ActionType.RETREAT_BENCH_1, ActionType.RETREAT_BENCH_2):
        bench_idx = action - ActionType.RETREAT_BENCH_0
        return _execute_retreat(state, bench_idx)

    elif ActionType.PLAY_HAND_0 <= action <= ActionType.PLAY_HAND_9:
        hand_idx = action - ActionType.PLAY_HAND_0
        if hand_idx < len(player.hand):
            return _play_card_from_hand(state, hand_idx)

    elif action in (ActionType.ENERGY_ACTIVE, ActionType.ENERGY_BENCH_0,
                    ActionType.ENERGY_BENCH_1, ActionType.ENERGY_BENCH_2):
        return _attach_energy(state, action)

    elif action in (ActionType.ABILITY_ACTIVE, ActionType.ABILITY_BENCH_0,
                    ActionType.ABILITY_BENCH_1, ActionType.ABILITY_BENCH_2):
        return _use_ability(state, action)

    return state


def _end_turn(state: GameState) -> GameState:
    """End the current player's turn and start the next."""
    # Clear cant_attack flags from current player's active
    state.current.active.cant_attack_next_turn = False

    # Between turns: resolve status effects
    state = _resolve_between_turns(state)

    if state.phase == GamePhase.GAME_OVER:
        return state

    # Increment turns in play for current player's pokemon
    for _, slot in state.current.all_pokemon_slots():
        if not slot.is_empty:
            slot.turns_in_play += 1

    # Switch to other player
    state.current_player = 1 - state.current_player
    state.turn_number += 1

    if state.turn_number > MAX_TURNS:
        state.phase = GamePhase.GAME_OVER
        # Draw
        return state

    _start_turn(state)
    return state


def _execute_attack(state: GameState, attack_idx: int) -> GameState:
    """Execute an attack."""
    player = state.current
    opponent = state.opponent
    active = player.active
    active_card = active.card

    if not active_card or attack_idx >= len(active_card.attacks):
        return state

    attack = active_card.attacks[attack_idx]

    # Check confusion
    if StatusEffect.CONFUSED in active.status_effects:
        flip = state.rng.random() < 0.5  # heads
        if not flip:
            # Tails: attack fails, take 30 self-damage
            active.current_hp -= CONFUSION_SELF_DAMAGE
            if active.current_hp <= 0:
                _handle_ko(state, state.current_player, "active")
            return _end_turn(state)

    # Calculate damage
    damage = attack.damage

    if damage > 0:
        # Apply weakness
        defending = opponent.active
        if defending.card and defending.card.weakness == active_card.element:
            damage += WEAKNESS_BONUS

        # Apply damage to defending Pokemon
        defending.current_hp -= damage

    # Resolve attack effects
    for effect in attack.effects:
        _resolve_attack_effect(state, effect, attack)

    # Check for KO on defender
    if not opponent.active.is_empty and opponent.active.current_hp <= 0:
        _handle_ko(state, 1 - state.current_player, "active")

    if state.phase == GamePhase.GAME_OVER:
        return state

    # Check if opponent needs to promote
    if opponent.active.is_empty and any(not s.is_empty for s in opponent.bench):
        state.phase = GamePhase.AWAITING_BENCH_PROMOTION
        return state

    return _end_turn(state)


def _resolve_attack_effect(state: GameState, effect: AttackEffect, attack: Attack) -> None:
    """Resolve a single attack effect."""
    player = state.current
    opponent = state.opponent

    if effect.effect_type == EffectType.HEAL:
        amount = effect.value
        target_slot = player.active
        target_slot.current_hp = min(target_slot.current_hp + amount, target_slot.max_hp)

    elif effect.effect_type == EffectType.HEAL_ALL:
        amount = effect.value
        for _, slot in player.all_pokemon_slots():
            if not slot.is_empty:
                slot.current_hp = min(slot.current_hp + amount, slot.max_hp)

    elif effect.effect_type == EffectType.DISCARD_ENERGY:
        slot = player.active
        count = effect.value
        etype = effect.energy_type
        for _ in range(count):
            if etype and slot.attached_energy.get(etype, 0) > 0:
                slot.attached_energy[etype] -= 1
                if slot.attached_energy[etype] == 0:
                    del slot.attached_energy[etype]
            elif slot.total_energy > 0:
                # Discard any energy
                for et in list(slot.attached_energy):
                    if slot.attached_energy[et] > 0:
                        slot.attached_energy[et] -= 1
                        if slot.attached_energy[et] == 0:
                            del slot.attached_energy[et]
                        break

    elif effect.effect_type == EffectType.DRAW_CARDS:
        for _ in range(effect.value):
            if player.deck and len(player.hand) < MAX_HAND_SIZE:
                player.hand.append(player.deck.pop(0))

    elif effect.effect_type == EffectType.APPLY_STATUS:
        if effect.status and not opponent.active.is_empty:
            _apply_status(opponent.active, effect.status)

    elif effect.effect_type == EffectType.SEARCH_DECK:
        _search_deck(state, player, effect)

    elif effect.effect_type == EffectType.SWITCH_OPPONENT:
        # In real game, opponent chooses. For simulation, we'll handle via target selection
        pass  # Handled by specific card logic

    elif effect.effect_type == EffectType.ATTACH_ENERGY:
        # Attach energy from energy zone (e.g., Stoke)
        etype = effect.energy_type or (player.energy_types[0] if player.energy_types else EnergyType.COLORLESS)
        for _ in range(effect.value):
            player.active.attached_energy[etype] = player.active.attached_energy.get(etype, 0) + 1

    elif effect.effect_type == EffectType.BENCH_DAMAGE:
        for _, slot in opponent.all_pokemon_slots():
            if not slot.is_empty and slot != opponent.active:
                slot.current_hp -= effect.value

    elif effect.effect_type == EffectType.CANT_ATTACK:
        opponent.active.cant_attack_next_turn = True

    elif effect.effect_type == EffectType.COIN_FLIP:
        # Generic coin flip - handled by the attack's effect text in more specific ways
        pass


def _apply_status(slot: PokemonSlot, status: StatusEffect) -> None:
    """Apply a status effect, respecting mutual exclusivity rules."""
    mutually_exclusive = {StatusEffect.PARALYZED, StatusEffect.ASLEEP, StatusEffect.CONFUSED}
    if status in mutually_exclusive:
        slot.status_effects -= mutually_exclusive
    slot.status_effects.add(status)


def _search_deck(state: GameState, player: PlayerState, effect: AttackEffect) -> None:
    """Search deck for cards matching criteria and add to hand."""
    count = effect.value
    found = 0
    search_filter = effect.search_filter

    indices_to_remove = []
    for i, card_id in enumerate(player.deck):
        if found >= count:
            break
        card = get_card(card_id)
        if card.is_pokemon:
            if search_filter:
                if search_filter == "basic" and not card.is_basic:
                    continue
                if search_filter in ("grass", "fire", "water", "lightning", "psychic", "fighting", "darkness", "metal"):
                    if card.element and card.element.value != search_filter:
                        continue
            if len(player.hand) < MAX_HAND_SIZE:
                indices_to_remove.append(i)
                found += 1

    # Remove from deck in reverse order and add to hand
    for i in reversed(indices_to_remove):
        player.hand.append(player.deck.pop(i))


def _execute_retreat(state: GameState, bench_idx: int) -> GameState:
    """Retreat active Pokemon, swapping with a bench Pokemon."""
    player = state.current
    active = player.active
    active_card = active.card

    if not active_card or player.bench[bench_idx].is_empty:
        return state

    # Pay retreat cost (discard energy)
    cost = active_card.retreat_cost
    for _ in range(cost):
        if active.total_energy > 0:
            for et in list(active.attached_energy):
                if active.attached_energy[et] > 0:
                    active.attached_energy[et] -= 1
                    if active.attached_energy[et] == 0:
                        del active.attached_energy[et]
                    break

    # Clear status effects on retreating pokemon
    active.status_effects.clear()

    # Swap
    player.active, player.bench[bench_idx] = player.bench[bench_idx], player.active
    player.has_retreated = True

    return state


def _play_card_from_hand(state: GameState, hand_idx: int) -> GameState:
    """Play a card from hand."""
    player = state.current
    card_id = player.hand[hand_idx]
    card = get_card(card_id)

    if card.card_type == CardType.POKEMON:
        if card.is_basic:
            return _play_basic_pokemon(state, hand_idx)
        else:
            # Evolution - need target selection
            state.pending_action = {
                "type": "evolve",
                "hand_idx": hand_idx,
                "card_id": card_id,
                "target_type": "own",
            }
            state.phase = GamePhase.AWAITING_TARGET
            return state

    elif card.card_type == CardType.ITEM:
        return _play_trainer(state, hand_idx, card)

    elif card.card_type == CardType.SUPPORTER:
        return _play_trainer(state, hand_idx, card)

    elif card.card_type == CardType.TOOL:
        state.pending_action = {
            "type": "attach_tool",
            "hand_idx": hand_idx,
            "card_id": card_id,
            "target_type": "own",
        }
        state.phase = GamePhase.AWAITING_TARGET
        return state

    return state


def _play_basic_pokemon(state: GameState, hand_idx: int) -> GameState:
    """Play a Basic Pokemon from hand to bench."""
    player = state.current
    card_id = player.hand[hand_idx]
    card = get_card(card_id)

    empty = player.empty_bench_slots()
    if not empty:
        return state

    slot_idx = empty[0]
    player.hand.pop(hand_idx)
    player.bench[slot_idx] = PokemonSlot(
        card_id=card_id,
        current_hp=card.hp,
        max_hp=card.hp,
    )

    return state


def _play_trainer(state: GameState, hand_idx: int, card: CardData) -> GameState:
    """Play a trainer card."""
    player = state.current

    # Check if this trainer needs a target
    needs_target = False
    for effect in card.trainer_effects:
        if effect.effect_type in (EffectType.HEAL, EffectType.SWITCH_OPPONENT):
            needs_target = True

    if needs_target:
        target_type = "own"
        for effect in card.trainer_effects:
            if effect.effect_type == EffectType.SWITCH_OPPONENT:
                target_type = "opponent"
        state.pending_action = {
            "type": "trainer",
            "hand_idx": hand_idx,
            "card_id": card.id,
            "target_type": target_type,
        }
        state.phase = GamePhase.AWAITING_TARGET
        return state

    # Play immediately
    player.hand.pop(hand_idx)
    player.discard.append(card.id)

    if card.card_type == CardType.SUPPORTER:
        player.has_played_supporter = True

    # Resolve effects
    for effect in card.trainer_effects:
        _resolve_trainer_effect(state, effect)

    return state


def _resolve_trainer_effect(state: GameState, effect: AttackEffect) -> None:
    """Resolve a trainer card effect."""
    player = state.current

    if effect.effect_type == EffectType.DRAW_CARDS:
        for _ in range(effect.value):
            if player.deck and len(player.hand) < MAX_HAND_SIZE:
                player.hand.append(player.deck.pop(0))

    elif effect.effect_type == EffectType.HEAL:
        # Already handled via target selection
        pass

    elif effect.effect_type == EffectType.SEARCH_DECK:
        _search_deck(state, player, effect)

    elif effect.effect_type == EffectType.HP_BONUS:
        # Tool effect - handled when attached
        pass


def _apply_target_selection(state: GameState, action: ActionType) -> GameState:
    """Handle target selection for multi-step actions."""
    ctx = state.pending_action
    if not ctx:
        state.phase = GamePhase.MAIN
        return state

    action_type = ctx["type"]
    player = state.current
    opponent = state.opponent

    if action_type == "evolve":
        # Determine target slot
        slot = _get_slot_from_target_action(state, action)
        if slot and not slot.is_empty:
            card_id = ctx["card_id"]
            card = get_card(card_id)
            if _can_evolve(slot, card, state):
                hand_idx = ctx["hand_idx"]
                # Adjust hand_idx if needed
                if hand_idx < len(player.hand):
                    player.hand.pop(hand_idx)
                    old_card_id = slot.card_id
                    slot.card_id = card_id
                    slot.max_hp = card.hp + (slot.max_hp - get_card(old_card_id).hp if old_card_id else 0)
                    slot.current_hp = min(slot.current_hp + (card.hp - get_card(old_card_id).hp), slot.max_hp) if old_card_id else card.hp
                    slot.max_hp = card.hp  # Reset max HP to new card's HP
                    # Keep energy, keep damage relative
                    hp_diff = card.hp - (get_card(old_card_id).hp if old_card_id else 0)
                    slot.current_hp = min(slot.current_hp + hp_diff, card.hp)
                    slot.max_hp = card.hp
                    slot.status_effects.clear()  # Evolution clears status
                    slot.evolved_this_turn = True
                    if old_card_id:
                        player.discard.append(old_card_id)

    elif action_type == "attach_tool":
        slot = _get_slot_from_target_action(state, action)
        if slot and not slot.is_empty and slot.tool_card_id is None:
            hand_idx = ctx["hand_idx"]
            if hand_idx < len(player.hand):
                card_id = player.hand.pop(hand_idx)
                card = get_card(card_id)
                slot.tool_card_id = card_id
                # Apply tool effects (e.g., HP bonus)
                for effect in card.trainer_effects:
                    if effect.effect_type == EffectType.HP_BONUS:
                        slot.max_hp += effect.value
                        slot.current_hp += effect.value

    elif action_type == "trainer":
        hand_idx = ctx["hand_idx"]
        card_id = ctx["card_id"]
        card = get_card(card_id)
        slot = _get_slot_from_target_action(state, action)

        if hand_idx < len(player.hand):
            player.hand.pop(hand_idx)
            player.discard.append(card_id)

            if card.card_type == CardType.SUPPORTER:
                player.has_played_supporter = True

            for effect in card.trainer_effects:
                if effect.effect_type == EffectType.HEAL and slot:
                    slot.current_hp = min(slot.current_hp + effect.value, slot.max_hp)
                elif effect.effect_type == EffectType.SWITCH_OPPONENT:
                    # Opponent chooses new active (for now, pick first bench)
                    opp = opponent
                    for i, bs in enumerate(opp.bench):
                        if not bs.is_empty:
                            opp.active, opp.bench[i] = opp.bench[i], opp.active
                            break

    state.pending_action = None
    state.phase = GamePhase.MAIN
    return state


def _apply_bench_promotion(state: GameState, action: ActionType) -> GameState:
    """Handle bench promotion after a KO."""
    # Find which player needs to promote
    for p_idx in range(2):
        player = state.players[p_idx]
        if player.active.is_empty and any(not s.is_empty for s in player.bench):
            bench_idx = action - ActionType.TARGET_BENCH_0
            if 0 <= bench_idx < BENCH_SIZE and not player.bench[bench_idx].is_empty:
                player.active = player.bench[bench_idx]
                player.bench[bench_idx] = PokemonSlot()
                break

    state.phase = GamePhase.MAIN

    # Check if we should end the turn (promotion happens after attack)
    if state.pending_action and state.pending_action.get("end_turn_after"):
        state.pending_action = None
        return _end_turn(state)

    return state


def _get_slot_from_target_action(state: GameState, action: ActionType) -> Optional[PokemonSlot]:
    """Get the Pokemon slot corresponding to a target action."""
    player = state.current
    opponent = state.opponent

    if action == ActionType.TARGET_ACTIVE:
        return player.active
    elif ActionType.TARGET_BENCH_0 <= action <= ActionType.TARGET_BENCH_2:
        idx = action - ActionType.TARGET_BENCH_0
        return player.bench[idx]
    elif action == ActionType.TARGET_OPP_ACTIVE:
        return opponent.active
    elif ActionType.TARGET_OPP_BENCH_0 <= action <= ActionType.TARGET_OPP_BENCH_2:
        idx = action - ActionType.TARGET_OPP_BENCH_0
        return opponent.bench[idx]
    return None


def _attach_energy(state: GameState, action: ActionType) -> GameState:
    """Attach energy from the energy zone to a Pokemon."""
    player = state.current
    if state.energy_available is None or player.has_attached_energy:
        return state

    if action == ActionType.ENERGY_ACTIVE:
        slot = player.active
    else:
        idx = action - ActionType.ENERGY_BENCH_0
        slot = player.bench[idx]

    if slot.is_empty:
        return state

    etype = state.energy_available
    slot.attached_energy[etype] = slot.attached_energy.get(etype, 0) + 1
    player.has_attached_energy = True
    state.energy_available = None

    return state


def _use_ability(state: GameState, action: ActionType) -> GameState:
    """Use a Pokemon's ability."""
    player = state.current

    if action == ActionType.ABILITY_ACTIVE:
        slot = player.active
    else:
        idx = action - ActionType.ABILITY_BENCH_0
        slot = player.bench[idx]

    if slot.is_empty or not slot.card or not slot.card.ability:
        return state

    ability = slot.card.ability
    slot.ability_used_this_turn = True

    # Resolve ability effects
    for effect in ability.effects:
        _resolve_attack_effect(state, effect, Attack(name="", damage=0, cost={}))

    return state


# ============================================================
# Between-turns resolution
# ============================================================

def _resolve_between_turns(state: GameState) -> GameState:
    """Resolve between-turns effects (status conditions)."""
    player = state.current
    active = player.active

    if active.is_empty:
        return state

    # Poison: 10 damage
    if StatusEffect.POISONED in active.status_effects:
        active.current_hp -= POISON_DAMAGE

    # Burn: 20 damage, then flip - heads cures
    if StatusEffect.BURNED in active.status_effects:
        active.current_hp -= BURN_DAMAGE
        if state.rng.random() < 0.5:  # Heads
            active.status_effects.discard(StatusEffect.BURNED)

    # Asleep: flip coin - heads wakes up
    if StatusEffect.ASLEEP in active.status_effects:
        if state.rng.random() < 0.5:  # Heads
            active.status_effects.discard(StatusEffect.ASLEEP)

    # Paralyzed: cured at end of affected player's next turn
    if StatusEffect.PARALYZED in active.status_effects:
        active.status_effects.discard(StatusEffect.PARALYZED)

    # Check for KO from status damage
    if active.current_hp <= 0:
        _handle_ko(state, state.current_player, "active")

    return state


def _handle_ko(state: GameState, player_idx: int, slot_key: str) -> None:
    """Handle a Pokemon being knocked out."""
    player = state.players[player_idx]
    opponent = state.players[1 - player_idx]

    if slot_key == "active":
        slot = player.active
    else:
        bench_idx = int(slot_key.split("_")[1])
        slot = player.bench[bench_idx]

    if slot.is_empty:
        return

    card = slot.card
    if not card:
        return

    # Award points
    points = card.ko_points
    opponent.points += points

    # Move to discard
    player.discard.append(slot.card_id)
    if slot.tool_card_id:
        player.discard.append(slot.tool_card_id)

    # Clear slot
    if slot_key == "active":
        player.active = PokemonSlot()
    else:
        bench_idx = int(slot_key.split("_")[1])
        player.bench[bench_idx] = PokemonSlot()

    # Check win conditions
    if opponent.points >= POINTS_TO_WIN:
        state.phase = GamePhase.GAME_OVER
        state.winner = 1 - player_idx
        return

    # Check if player has no Pokemon left
    if not player.has_pokemon_in_play():
        state.phase = GamePhase.GAME_OVER
        state.winner = 1 - player_idx
        return


def get_action_mask(state: GameState) -> list[bool]:
    """Get a boolean mask of legal actions (for RL)."""
    legal = set(get_legal_actions(state))
    return [ActionType(i) in legal for i in range(NUM_ACTIONS)]
