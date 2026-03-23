"""Tests for the PTCGP game engine."""

import pytest
from ptcgp.engine import (
    EnergyType, PokemonStage, CardType, StatusEffect, GamePhase,
    ActionType, CardData, Attack, Ability, AttackEffect, EffectType,
    PokemonSlot, PlayerState, GameState,
    register_card, clear_card_db, get_card,
    DECK_SIZE, BENCH_SIZE, MAX_HAND_SIZE, POINTS_TO_WIN,
)
from ptcgp.engine.game import (
    create_game, setup_active_pokemon, setup_bench_pokemon, start_game,
    get_legal_actions, apply_action, get_action_mask,
    _apply_status, _resolve_between_turns,
)


# ============================================================
# Test Fixtures - Create minimal card set for testing
# ============================================================

@pytest.fixture(autouse=True)
def setup_test_cards():
    """Set up test cards before each test."""
    clear_card_db()

    # Basic Pokemon
    register_card(CardData(
        id="test-bulbasaur", name="Bulbasaur", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.GRASS,
        hp=70, weakness=EnergyType.FIRE, retreat_cost=1,
        attacks=(Attack(name="Vine Whip", damage=40, cost={EnergyType.GRASS: 1, EnergyType.COLORLESS: 1}),),
    ))
    register_card(CardData(
        id="test-charmander", name="Charmander", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.FIRE,
        hp=60, weakness=EnergyType.WATER, retreat_cost=1,
        attacks=(Attack(name="Ember", damage=30, cost={EnergyType.FIRE: 1},
                        effects=(AttackEffect(EffectType.DISCARD_ENERGY, value=1, energy_type=EnergyType.FIRE),),
                        effect_text="Discard a Fire Energy from this Pokemon."),),
    ))
    register_card(CardData(
        id="test-squirtle", name="Squirtle", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.WATER,
        hp=60, weakness=EnergyType.LIGHTNING, retreat_cost=1,
        attacks=(Attack(name="Water Gun", damage=20, cost={EnergyType.WATER: 1}),),
    ))
    register_card(CardData(
        id="test-pikachu", name="Pikachu", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.LIGHTNING,
        hp=60, weakness=EnergyType.FIGHTING, retreat_cost=1,
        attacks=(Attack(name="Thunder Shock", damage=30, cost={EnergyType.LIGHTNING: 1}),),
    ))
    register_card(CardData(
        id="test-pidgey", name="Pidgey", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.COLORLESS,
        hp=50, weakness=EnergyType.LIGHTNING, retreat_cost=1,
        attacks=(Attack(name="Gust", damage=20, cost={EnergyType.COLORLESS: 1}),),
    ))
    register_card(CardData(
        id="test-mewtwo-ex", name="Mewtwo ex", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.PSYCHIC,
        hp=150, weakness=EnergyType.DARKNESS, retreat_cost=2, is_ex=True,
        attacks=(
            Attack(name="Psychic", damage=50, cost={EnergyType.PSYCHIC: 1, EnergyType.COLORLESS: 1}),
            Attack(name="Psydrive", damage=150, cost={EnergyType.PSYCHIC: 2, EnergyType.COLORLESS: 2}),
        ),
    ))

    # Stage 1
    register_card(CardData(
        id="test-ivysaur", name="Ivysaur", card_type=CardType.POKEMON,
        stage=PokemonStage.STAGE1, element=EnergyType.GRASS,
        hp=90, weakness=EnergyType.FIRE, retreat_cost=2,
        evolves_from="Bulbasaur",
        attacks=(Attack(name="Razor Leaf", damage=60, cost={EnergyType.GRASS: 1, EnergyType.COLORLESS: 2}),),
    ))

    # Trainer cards
    register_card(CardData(
        id="test-potion", name="Potion", card_type=CardType.ITEM,
        trainer_effects=(AttackEffect(EffectType.HEAL, value=20),),
        trainer_effect_text="Heal 20 damage from 1 of your Pokemon.",
    ))
    register_card(CardData(
        id="test-professors-research", name="Professor's Research", card_type=CardType.SUPPORTER,
        trainer_effects=(AttackEffect(EffectType.DRAW_CARDS, value=2),),
        trainer_effect_text="Draw 2 cards.",
    ))
    register_card(CardData(
        id="test-pokeball", name="Poke Ball", card_type=CardType.ITEM,
        trainer_effects=(AttackEffect(EffectType.SEARCH_DECK, value=1, search_filter="basic"),),
        trainer_effect_text="Put 1 random Basic Pokemon from your deck into your hand.",
    ))

    yield
    clear_card_db()


def _make_deck(card_ids: list[str]) -> list[str]:
    """Create a deck from card IDs, padding with basics to reach 20."""
    deck = list(card_ids)
    basics = ["test-bulbasaur", "test-charmander", "test-squirtle", "test-pikachu", "test-pidgey"]
    while len(deck) < DECK_SIZE:
        deck.append(basics[len(deck) % len(basics)])
    return deck[:DECK_SIZE]


def _make_grass_deck() -> list[str]:
    return _make_deck([
        "test-bulbasaur", "test-bulbasaur",
        "test-ivysaur", "test-ivysaur",
        "test-pidgey", "test-pidgey",
        "test-potion", "test-potion",
        "test-professors-research", "test-professors-research",
        "test-pokeball", "test-pokeball",
    ])


def _make_fire_deck() -> list[str]:
    return _make_deck([
        "test-charmander", "test-charmander",
        "test-pikachu", "test-pikachu",
        "test-pidgey", "test-pidgey",
        "test-potion", "test-potion",
        "test-professors-research", "test-professors-research",
    ])


# ============================================================
# Tests
# ============================================================

class TestCardDatabase:
    def test_register_and_get_card(self):
        card = get_card("test-bulbasaur")
        assert card.name == "Bulbasaur"
        assert card.hp == 70
        assert card.element == EnergyType.GRASS
        assert card.is_basic
        assert not card.is_ex

    def test_ex_card(self):
        card = get_card("test-mewtwo-ex")
        assert card.is_ex
        assert card.ko_points == 2
        assert card.hp == 150

    def test_evolution_card(self):
        card = get_card("test-ivysaur")
        assert card.stage == PokemonStage.STAGE1
        assert card.evolves_from == "Bulbasaur"

    def test_trainer_card(self):
        card = get_card("test-potion")
        assert card.card_type == CardType.ITEM
        assert len(card.trainer_effects) == 1
        assert card.trainer_effects[0].effect_type == EffectType.HEAL

    def test_attack_with_effect(self):
        card = get_card("test-charmander")
        assert len(card.attacks) == 1
        attack = card.attacks[0]
        assert attack.damage == 30
        assert len(attack.effects) == 1
        assert attack.effects[0].effect_type == EffectType.DISCARD_ENERGY


class TestPokemonSlot:
    def test_empty_slot(self):
        slot = PokemonSlot()
        assert slot.is_empty
        assert slot.total_energy == 0

    def test_slot_with_pokemon(self):
        slot = PokemonSlot(card_id="test-bulbasaur", current_hp=70, max_hp=70)
        assert not slot.is_empty
        assert not slot.is_knocked_out

    def test_knocked_out(self):
        slot = PokemonSlot(card_id="test-bulbasaur", current_hp=0, max_hp=70)
        assert slot.is_knocked_out

    def test_energy_check(self):
        slot = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 1, EnergyType.FIRE: 1}
        )
        # Vine Whip costs {GRASS: 1, COLORLESS: 1}
        cost = {EnergyType.GRASS: 1, EnergyType.COLORLESS: 1}
        assert slot.has_energy_for(cost)

    def test_energy_check_insufficient(self):
        slot = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.FIRE: 1}
        )
        cost = {EnergyType.GRASS: 1, EnergyType.COLORLESS: 1}
        assert not slot.has_energy_for(cost)

    def test_copy(self):
        slot = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2},
            status_effects={StatusEffect.POISONED},
        )
        copy = slot.copy()
        assert copy.card_id == slot.card_id
        assert copy.attached_energy == slot.attached_energy
        # Ensure deep copy
        copy.attached_energy[EnergyType.FIRE] = 1
        assert EnergyType.FIRE not in slot.attached_energy


class TestGameCreation:
    def test_create_game(self):
        deck1 = _make_grass_deck()
        deck2 = _make_fire_deck()
        state = create_game(deck1, deck2, [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        assert state.phase == GamePhase.SETUP
        assert len(state.players[0].hand) == 5
        assert len(state.players[1].hand) == 5
        assert state.players[0].points == 0
        assert state.players[1].points == 0

    def test_initial_hand_has_basic(self):
        deck1 = _make_grass_deck()
        deck2 = _make_fire_deck()
        state = create_game(deck1, deck2, [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        for p in state.players:
            has_basic = any(get_card(cid).is_basic for cid in p.hand if get_card(cid).is_pokemon)
            assert has_basic, "Initial hand must contain at least one Basic Pokemon"

    def test_deck_size_after_draw(self):
        deck1 = _make_grass_deck()
        deck2 = _make_fire_deck()
        state = create_game(deck1, deck2, [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        for p in state.players:
            assert len(p.hand) + len(p.deck) == DECK_SIZE


class TestSetup:
    def test_setup_active_pokemon(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        # Find a basic pokemon in hand
        p = state.players[0]
        basic_idx = None
        for i, cid in enumerate(p.hand):
            if get_card(cid).is_basic:
                basic_idx = i
                break

        assert basic_idx is not None
        state = setup_active_pokemon(state, 0, basic_idx)
        assert not state.players[0].active.is_empty

    def test_setup_bench_pokemon(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        # Setup active first
        p = state.players[0]
        basics = [i for i, cid in enumerate(p.hand) if get_card(cid).is_basic]
        assert len(basics) >= 1

        state = setup_active_pokemon(state, 0, basics[0])

        # Now check if there are more basics to bench
        p = state.players[0]
        basics = [i for i, cid in enumerate(p.hand) if get_card(cid).is_basic]
        if basics:
            state = setup_bench_pokemon(state, 0, basics[0])
            assert any(not s.is_empty for s in state.players[0].bench)


class TestTurnMechanics:
    def _setup_basic_game(self, seed=42) -> GameState:
        """Create a game ready to play (both players have active Pokemon)."""
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=seed)

        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break

        state = start_game(state)
        return state

    def test_start_game(self):
        state = self._setup_basic_game()
        assert state.phase == GamePhase.MAIN
        assert state.turn_number == 1

    def test_first_turn_no_energy(self):
        state = self._setup_basic_game()
        # First turn: no energy available
        assert state.energy_available is None

    def test_end_turn(self):
        state = self._setup_basic_game()
        initial_player = state.current_player
        state = apply_action(state, ActionType.END_TURN)
        assert state.current_player != initial_player
        assert state.turn_number == 2

    def test_second_turn_has_energy(self):
        state = self._setup_basic_game()
        state = apply_action(state, ActionType.END_TURN)
        # Second turn should have energy
        assert state.energy_available is not None

    def test_attach_energy(self):
        state = self._setup_basic_game()
        # Skip to turn 2 for energy
        state = apply_action(state, ActionType.END_TURN)

        # Should have energy available
        assert state.energy_available is not None
        assert not state.current.has_attached_energy

        state = apply_action(state, ActionType.ENERGY_ACTIVE)
        assert state.current.has_attached_energy
        assert state.current.active.total_energy == 1

    def test_end_turn_increments_turns_in_play(self):
        state = self._setup_basic_game()
        assert state.current.active.turns_in_play == 0
        state = apply_action(state, ActionType.END_TURN)
        # After ending turn, the previous player's pokemon get turns_in_play incremented
        # The OTHER player is now current
        assert state.players[1 - state.current_player].active.turns_in_play == 1

    def test_legal_actions_first_turn(self):
        state = self._setup_basic_game()
        actions = get_legal_actions(state)

        # First turn: should be able to end turn, play cards, but NOT attack or attach energy
        assert ActionType.END_TURN in actions
        # No attack on first turn (for first player)
        assert ActionType.ATTACK_0 not in actions
        # No energy on first turn
        assert ActionType.ENERGY_ACTIVE not in actions

    def test_action_mask(self):
        state = self._setup_basic_game()
        mask = get_action_mask(state)
        assert len(mask) == 32  # NUM_ACTIONS
        assert mask[ActionType.END_TURN]  # End turn always legal
        assert not mask[ActionType.ATTACK_0]  # Can't attack first turn


class TestCombat:
    def _setup_combat_game(self) -> GameState:
        """Set up a game where both players can attack."""
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break

        state = start_game(state)

        # Give both active Pokemon enough energy to attack
        for p_idx in range(2):
            active = state.players[p_idx].active
            card = active.card
            if card and card.attacks:
                for etype, count in card.attacks[0].cost.items():
                    if etype != EnergyType.COLORLESS:
                        active.attached_energy[etype] = active.attached_energy.get(etype, 0) + count
                    else:
                        # Use first energy type
                        et = state.players[p_idx].energy_types[0] if state.players[p_idx].energy_types else EnergyType.COLORLESS
                        active.attached_energy[et] = active.attached_energy.get(et, 0) + count

        # Advance past first turn
        state.turn_number = 2
        return state

    def test_attack_deals_damage(self):
        state = self._setup_combat_game()
        opp_hp_before = state.opponent.active.current_hp

        actions = get_legal_actions(state)
        assert ActionType.ATTACK_0 in actions

        state = apply_action(state, ActionType.ATTACK_0)
        # Damage was dealt (turn ended so players swapped)
        # The opponent from before is now current
        opp_hp_after = state.players[1 - state.current_player].active.current_hp
        # Should have taken some damage (exact amount depends on cards)
        assert opp_hp_after <= opp_hp_before

    def test_weakness_bonus(self):
        state = self._setup_combat_game()

        # Set up a fire pokemon attacking a grass pokemon
        state.current_player = 0
        state.players[0].active = PokemonSlot(
            card_id="test-charmander", current_hp=60, max_hp=60,
            attached_energy={EnergyType.FIRE: 2}
        )
        state.players[1].active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
        )

        state = apply_action(state, ActionType.ATTACK_0)
        # Charmander's Ember does 30 + 20 weakness = 50
        # But it also discards a Fire energy
        bulbasaur = state.players[1].active
        assert bulbasaur.current_hp == 70 - 50  # 30 damage + 20 weakness

    def test_ko_awards_points(self):
        state = self._setup_combat_game()
        state.current_player = 0

        # Set up a one-hit KO scenario
        state.players[0].active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2}
        )
        state.players[1].active = PokemonSlot(
            card_id="test-charmander", current_hp=10, max_hp=60,
        )
        # Put a bench pokemon so game doesn't end immediately
        state.players[1].bench[0] = PokemonSlot(
            card_id="test-pikachu", current_hp=60, max_hp=60,
        )

        state = apply_action(state, ActionType.ATTACK_0)
        # Player 0 should get 1 point for KOing Charmander
        assert state.players[0].points >= 1

    def test_ex_ko_awards_2_points(self):
        state = self._setup_combat_game()
        state.current_player = 0

        state.players[0].active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2}
        )
        state.players[1].active = PokemonSlot(
            card_id="test-mewtwo-ex", current_hp=10, max_hp=150,
        )
        state.players[1].bench[0] = PokemonSlot(
            card_id="test-pikachu", current_hp=60, max_hp=60,
        )

        state = apply_action(state, ActionType.ATTACK_0)
        assert state.players[0].points >= 2


class TestRetreat:
    def test_retreat(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)

        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break

        state = start_game(state)
        state.turn_number = 2  # Skip past first turn

        # Set up: active with energy, bench with pokemon
        player = state.current
        player.active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2},
            status_effects={StatusEffect.POISONED},
        )
        player.bench[0] = PokemonSlot(
            card_id="test-pikachu", current_hp=60, max_hp=60,
        )

        actions = get_legal_actions(state)
        assert ActionType.RETREAT_BENCH_0 in actions

        old_active_id = player.active.card_id
        state = apply_action(state, ActionType.RETREAT_BENCH_0)

        # Active should have swapped
        assert state.current.active.card_id != old_active_id
        assert state.current.has_retreated
        # Status should be cleared from retreated pokemon
        bench_slot = None
        for s in state.current.bench:
            if s.card_id == old_active_id:
                bench_slot = s
                break
        if bench_slot:
            assert StatusEffect.POISONED not in bench_slot.status_effects

    def test_cant_retreat_when_paralyzed(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)
        state.turn_number = 2

        player = state.current
        player.active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2},
            status_effects={StatusEffect.PARALYZED},
        )
        player.bench[0] = PokemonSlot(card_id="test-pikachu", current_hp=60, max_hp=60)

        actions = get_legal_actions(state)
        assert ActionType.RETREAT_BENCH_0 not in actions


class TestStatusEffects:
    def test_mutual_exclusivity(self):
        slot = PokemonSlot(card_id="test-bulbasaur", current_hp=70, max_hp=70)
        _apply_status(slot, StatusEffect.PARALYZED)
        assert StatusEffect.PARALYZED in slot.status_effects

        _apply_status(slot, StatusEffect.ASLEEP)
        assert StatusEffect.ASLEEP in slot.status_effects
        assert StatusEffect.PARALYZED not in slot.status_effects

    def test_poison_and_sleep_can_coexist(self):
        slot = PokemonSlot(card_id="test-bulbasaur", current_hp=70, max_hp=70)
        _apply_status(slot, StatusEffect.POISONED)
        _apply_status(slot, StatusEffect.ASLEEP)
        assert StatusEffect.POISONED in slot.status_effects
        assert StatusEffect.ASLEEP in slot.status_effects

    def test_poison_damage_between_turns(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)

        # Poison the current player's active pokemon
        state.current.active.status_effects.add(StatusEffect.POISONED)
        hp_before = state.current.active.current_hp

        state = _resolve_between_turns(state)
        assert state.current.active.current_hp == hp_before - 10

    def test_paralysis_cured_after_turn(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)

        state.current.active.status_effects.add(StatusEffect.PARALYZED)
        state = _resolve_between_turns(state)
        assert StatusEffect.PARALYZED not in state.current.active.status_effects


class TestEvolution:
    def _setup_evolution_game(self) -> GameState:
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)
        return state

    def test_cant_evolve_turn_one(self):
        state = self._setup_evolution_game()
        # Put Bulbasaur as active and Ivysaur in hand
        state.current.active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            turns_in_play=1,
        )
        state.current.hand = ["test-ivysaur"]

        # Turn 1 - can't evolve
        state.turn_number = 1
        actions = get_legal_actions(state)
        assert ActionType.PLAY_HAND_0 not in actions

    def test_can_evolve_turn_two(self):
        state = self._setup_evolution_game()
        state.current.active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            turns_in_play=1,
        )
        state.current.hand = ["test-ivysaur"]
        state.turn_number = 2

        actions = get_legal_actions(state)
        assert ActionType.PLAY_HAND_0 in actions

    def test_cant_evolve_if_just_played(self):
        state = self._setup_evolution_game()
        state.current.active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            turns_in_play=0,  # Just placed
        )
        state.current.hand = ["test-ivysaur"]
        state.turn_number = 2

        actions = get_legal_actions(state)
        assert ActionType.PLAY_HAND_0 not in actions


class TestWinConditions:
    def test_win_by_points(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)
        state.turn_number = 2

        # Give player 0 enough points to win
        state.players[0].points = 2
        state.current_player = 0

        # Set up KO scenario
        state.players[0].active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2}
        )
        state.players[1].active = PokemonSlot(
            card_id="test-charmander", current_hp=10, max_hp=60,
        )
        state.players[1].bench[0] = PokemonSlot(
            card_id="test-pikachu", current_hp=60, max_hp=60,
        )

        state = apply_action(state, ActionType.ATTACK_0)
        assert state.players[0].points >= POINTS_TO_WIN
        assert state.phase == GamePhase.GAME_OVER
        assert state.winner == 0

    def test_win_by_no_pokemon(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)
        state.turn_number = 2

        state.current_player = 0
        state.players[0].active = PokemonSlot(
            card_id="test-bulbasaur", current_hp=70, max_hp=70,
            attached_energy={EnergyType.GRASS: 2}
        )
        # Opponent has only active, no bench
        state.players[1].active = PokemonSlot(
            card_id="test-charmander", current_hp=10, max_hp=60,
        )

        state = apply_action(state, ActionType.ATTACK_0)
        assert state.phase == GamePhase.GAME_OVER
        assert state.winner == 0


class TestTrainerCards:
    def test_play_supporter_draw(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)

        # Put Professor's Research in hand
        state.current.hand = ["test-professors-research", "test-bulbasaur"]
        deck_before = len(state.current.deck)
        hand_before = len(state.current.hand)

        state = apply_action(state, ActionType.PLAY_HAND_0)
        # Should have drawn 2 cards and discarded the supporter
        # hand_before - 1 (played) + 2 (drawn) = hand_before + 1
        assert len(state.current.hand) == hand_before - 1 + 2
        assert state.current.has_played_supporter

    def test_one_supporter_per_turn(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        for p_idx in range(2):
            p = state.players[p_idx]
            for i, cid in enumerate(p.hand):
                if get_card(cid).is_basic:
                    state = setup_active_pokemon(state, p_idx, i)
                    break
        state = start_game(state)

        state.current.hand = ["test-professors-research", "test-professors-research"]
        state = apply_action(state, ActionType.PLAY_HAND_0)

        actions = get_legal_actions(state)
        # Second supporter should not be playable
        assert ActionType.PLAY_HAND_0 not in actions or not any(
            get_card(state.current.hand[a - ActionType.PLAY_HAND_0]).card_type == CardType.SUPPORTER
            for a in actions if ActionType.PLAY_HAND_0 <= a <= ActionType.PLAY_HAND_9
            and a - ActionType.PLAY_HAND_0 < len(state.current.hand)
        )


class TestGameCopy:
    def test_copy_independence(self):
        state = create_game(_make_grass_deck(), _make_fire_deck(),
                          [EnergyType.GRASS], [EnergyType.FIRE], seed=42)
        copy = state.copy()

        copy.players[0].points = 5
        assert state.players[0].points == 0

        copy.players[0].hand.append("test-bulbasaur")
        assert len(copy.players[0].hand) != len(state.players[0].hand)
