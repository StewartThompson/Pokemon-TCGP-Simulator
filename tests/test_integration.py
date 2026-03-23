"""Integration tests - full games, simulation, and system tests."""

import pytest
from ptcgp.engine.types import EnergyType, GamePhase, DECK_SIZE, POINTS_TO_WIN
from ptcgp.engine.cards import (
    CardData, CardType, PokemonStage, Attack, register_card, clear_card_db,
    load_cards_from_json, get_all_cards, get_card,
)
from ptcgp.engine.game import GameState
from ptcgp.engine.runner import run_game
from ptcgp.agents.random_agent import RandomAgent
from ptcgp.agents.heuristic import HeuristicAgent
from ptcgp.simulation.simulator import simulate


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def setup_test_cards():
    """Set up a comprehensive test card set."""
    clear_card_db()

    # Create a rich set of test cards
    basics = [
        ("t-bulb", "Bulbasaur", EnergyType.GRASS, 70, EnergyType.FIRE, 1,
         [("Vine Whip", 40, {EnergyType.GRASS: 1, EnergyType.COLORLESS: 1})]),
        ("t-charm", "Charmander", EnergyType.FIRE, 60, EnergyType.WATER, 1,
         [("Ember", 30, {EnergyType.FIRE: 1})]),
        ("t-squirt", "Squirtle", EnergyType.WATER, 60, EnergyType.LIGHTNING, 1,
         [("Water Gun", 20, {EnergyType.WATER: 1})]),
        ("t-pika", "Pikachu", EnergyType.LIGHTNING, 60, EnergyType.FIGHTING, 1,
         [("Thunder Shock", 30, {EnergyType.LIGHTNING: 1})]),
        ("t-pidgey", "Pidgey", EnergyType.COLORLESS, 50, EnergyType.LIGHTNING, 1,
         [("Gust", 20, {EnergyType.COLORLESS: 1})]),
        ("t-eevee", "Eevee", EnergyType.COLORLESS, 50, EnergyType.FIGHTING, 1,
         [("Tackle", 20, {EnergyType.COLORLESS: 1})]),
        ("t-geodude", "Geodude", EnergyType.FIGHTING, 70, EnergyType.GRASS, 2,
         [("Rock Throw", 40, {EnergyType.FIGHTING: 1, EnergyType.COLORLESS: 1})]),
        ("t-gastly", "Gastly", EnergyType.PSYCHIC, 50, EnergyType.DARKNESS, 1,
         [("Lick", 20, {EnergyType.PSYCHIC: 1})]),
    ]

    for cid, name, elem, hp, weak, rc, attacks_data in basics:
        attacks = tuple(
            Attack(name=n, damage=d, cost=c) for n, d, c in attacks_data
        )
        register_card(CardData(
            id=cid, name=name, card_type=CardType.POKEMON,
            stage=PokemonStage.BASIC, element=elem,
            hp=hp, weakness=weak, retreat_cost=rc,
            attacks=attacks,
        ))

    # Stage 1
    register_card(CardData(
        id="t-ivy", name="Ivysaur", card_type=CardType.POKEMON,
        stage=PokemonStage.STAGE1, element=EnergyType.GRASS,
        hp=90, weakness=EnergyType.FIRE, retreat_cost=2,
        evolves_from="Bulbasaur",
        attacks=(Attack(name="Razor Leaf", damage=60, cost={EnergyType.GRASS: 1, EnergyType.COLORLESS: 2}),),
    ))
    register_card(CardData(
        id="t-charmeleon", name="Charmeleon", card_type=CardType.POKEMON,
        stage=PokemonStage.STAGE1, element=EnergyType.FIRE,
        hp=80, weakness=EnergyType.WATER, retreat_cost=1,
        evolves_from="Charmander",
        attacks=(Attack(name="Flamethrower", damage=70, cost={EnergyType.FIRE: 2}),),
    ))

    # EX
    register_card(CardData(
        id="t-mewtwo-ex", name="Mewtwo ex", card_type=CardType.POKEMON,
        stage=PokemonStage.BASIC, element=EnergyType.PSYCHIC,
        hp=150, weakness=EnergyType.DARKNESS, retreat_cost=2, is_ex=True,
        attacks=(
            Attack(name="Psychic", damage=50, cost={EnergyType.PSYCHIC: 1, EnergyType.COLORLESS: 1}),
            Attack(name="Psydrive", damage=150, cost={EnergyType.PSYCHIC: 2, EnergyType.COLORLESS: 2}),
        ),
    ))

    # Trainers
    from ptcgp.engine.cards import AttackEffect
    from ptcgp.engine.types import EffectType
    register_card(CardData(
        id="t-potion", name="Potion", card_type=CardType.ITEM,
        trainer_effects=(AttackEffect(EffectType.HEAL, value=20),),
    ))
    register_card(CardData(
        id="t-research", name="Professor's Research", card_type=CardType.SUPPORTER,
        trainer_effects=(AttackEffect(EffectType.DRAW_CARDS, value=2),),
    ))
    register_card(CardData(
        id="t-pokeball", name="Poke Ball", card_type=CardType.ITEM,
        trainer_effects=(AttackEffect(EffectType.SEARCH_DECK, value=1, search_filter="basic"),),
    ))

    yield
    clear_card_db()


def _make_deck(*card_ids: str) -> list[str]:
    """Build a 20-card deck, padding with basics if needed."""
    deck = list(card_ids)
    fillers = ["t-pidgey", "t-eevee", "t-geodude", "t-gastly", "t-bulb", "t-charm"]
    i = 0
    while len(deck) < DECK_SIZE:
        deck.append(fillers[i % len(fillers)])
        i += 1
    return deck[:DECK_SIZE]


def _grass_deck() -> list[str]:
    return _make_deck(
        "t-bulb", "t-bulb", "t-ivy", "t-ivy",
        "t-pidgey", "t-pidgey", "t-eevee", "t-eevee",
        "t-potion", "t-potion", "t-research", "t-research",
        "t-pokeball", "t-pokeball",
    )


def _fire_deck() -> list[str]:
    return _make_deck(
        "t-charm", "t-charm", "t-charmeleon", "t-charmeleon",
        "t-pidgey", "t-pidgey", "t-eevee", "t-eevee",
        "t-potion", "t-potion", "t-research", "t-research",
        "t-pokeball", "t-pokeball",
    )


# ============================================================
# Integration Tests
# ============================================================

class TestFullGame:
    """Test complete game flows from start to finish."""

    def test_random_vs_random_completes(self):
        """Two random agents should always finish a game."""
        agent1 = RandomAgent(seed=42)
        agent2 = RandomAgent(seed=43)

        state, winner = run_game(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            agent1, agent2, seed=42,
        )

        assert state.phase == GamePhase.GAME_OVER
        # Winner is 0, 1, or None
        assert winner in (0, 1, None)

    def test_heuristic_vs_heuristic_completes(self):
        """Two heuristic agents should finish a game."""
        agent1 = HeuristicAgent(seed=42)
        agent2 = HeuristicAgent(seed=43)

        state, winner = run_game(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            agent1, agent2, seed=42,
        )

        assert state.phase == GamePhase.GAME_OVER

    def test_heuristic_vs_random(self):
        """Heuristic should generally beat random."""
        agent1 = HeuristicAgent(seed=42)
        agent2 = RandomAgent(seed=43)

        state, winner = run_game(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            agent1, agent2, seed=42,
        )

        assert state.phase == GamePhase.GAME_OVER

    def test_many_games_no_crashes(self):
        """Run many games with different seeds to stress test."""
        for seed in range(50):
            agent1 = RandomAgent(seed=seed)
            agent2 = RandomAgent(seed=seed + 100)

            state, winner = run_game(
                _grass_deck(), _fire_deck(),
                [EnergyType.GRASS], [EnergyType.FIRE],
                agent1, agent2, seed=seed,
            )

            assert state.phase == GamePhase.GAME_OVER
            # Points should be valid
            for p in state.players:
                assert 0 <= p.points <= POINTS_TO_WIN + 2  # +2 for ex KO on winning blow

    def test_game_respects_points_to_win(self):
        """Games end when a player reaches the point threshold."""
        for seed in range(20):
            agent1 = HeuristicAgent(seed=seed)
            agent2 = HeuristicAgent(seed=seed + 100)

            state, winner = run_game(
                _grass_deck(), _fire_deck(),
                [EnergyType.GRASS], [EnergyType.FIRE],
                agent1, agent2, seed=seed,
            )

            if winner is not None:
                # Winner should have enough points OR opponent has no pokemon
                wp = state.players[winner]
                lp = state.players[1 - winner]
                assert wp.points >= POINTS_TO_WIN or not lp.has_pokemon_in_play()

    def test_deterministic_with_seed(self):
        """Same seed should produce same result."""
        results = []
        for _ in range(3):
            agent1 = RandomAgent(seed=42)
            agent2 = RandomAgent(seed=43)
            state, winner = run_game(
                _grass_deck(), _fire_deck(),
                [EnergyType.GRASS], [EnergyType.FIRE],
                agent1, agent2, seed=42,
            )
            results.append((winner, state.turn_number, state.players[0].points, state.players[1].points))

        assert results[0] == results[1] == results[2]


class TestSimulation:
    """Test the simulation framework."""

    def test_basic_simulation(self):
        """Run a small simulation."""
        results = simulate(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            agent1="heuristic", agent2="heuristic",
            n_games=20, base_seed=42,
        )

        assert results.n_games == 20
        assert results.wins[0] + results.wins[1] + results.draws == 20
        assert results.avg_turns > 0
        assert results.elapsed_seconds > 0

    def test_simulation_win_rates(self):
        """Win rates should sum to ~1."""
        results = simulate(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            agent1="heuristic", agent2="heuristic",
            n_games=50, base_seed=42,
        )

        total_rate = results.win_rate_0 + results.win_rate_1 + results.draw_rate
        assert abs(total_rate - 1.0) < 0.001

    def test_heuristic_beats_random(self):
        """Heuristic should have higher win rate than random over many games."""
        results = simulate(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            agent1="heuristic", agent2="random",
            n_games=100, base_seed=42,
        )

        # Heuristic (player 1) should win more than random (player 2)
        assert results.win_rate_0 > results.win_rate_1, \
            f"Heuristic ({results.win_rate_0:.1%}) should beat random ({results.win_rate_1:.1%})"

    def test_simulation_summary(self):
        """Summary should be well-formatted."""
        results = simulate(
            _grass_deck(), _fire_deck(),
            [EnergyType.GRASS], [EnergyType.FIRE],
            n_games=10, base_seed=42,
        )

        summary = results.summary()
        assert "Simulation Results" in summary
        assert "Player 1 wins" in summary


class TestGymnasiumEnv:
    """Test the Gymnasium environment."""

    def test_env_creation(self):
        from ptcgp.training.env import PTCGPEnv, TOTAL_OBS_SIZE
        from ptcgp.engine.types import NUM_ACTIONS

        env = PTCGPEnv(
            deck1=_grass_deck(), deck2=_fire_deck(),
            energy_types1=[EnergyType.GRASS], energy_types2=[EnergyType.FIRE],
        )

        assert env.observation_space.shape == (TOTAL_OBS_SIZE,)
        assert env.action_space.n == NUM_ACTIONS

    def test_env_reset(self):
        from ptcgp.training.env import PTCGPEnv, TOTAL_OBS_SIZE

        env = PTCGPEnv(
            deck1=_grass_deck(), deck2=_fire_deck(),
            energy_types1=[EnergyType.GRASS], energy_types2=[EnergyType.FIRE],
        )

        obs, info = env.reset(seed=42)
        assert obs.shape == (TOTAL_OBS_SIZE,)
        assert "action_mask" in info
        assert info["action_mask"].shape[0] > 0

    def test_env_step(self):
        from ptcgp.training.env import PTCGPEnv
        import numpy as np

        env = PTCGPEnv(
            deck1=_grass_deck(), deck2=_fire_deck(),
            energy_types1=[EnergyType.GRASS], energy_types2=[EnergyType.FIRE],
        )

        obs, info = env.reset(seed=42)
        mask = info["action_mask"]

        # Pick a legal action
        legal_actions = np.where(mask)[0]
        if len(legal_actions) > 0:
            action = legal_actions[0]
            obs2, reward, terminated, truncated, info2 = env.step(int(action))
            assert obs2.shape == obs.shape
            assert isinstance(reward, float)
            assert isinstance(terminated, bool)

    def test_env_full_episode(self):
        """Play a full episode using random legal actions."""
        from ptcgp.training.env import PTCGPEnv
        import numpy as np

        env = PTCGPEnv(
            deck1=_grass_deck(), deck2=_fire_deck(),
            energy_types1=[EnergyType.GRASS], energy_types2=[EnergyType.FIRE],
            opponent="random",
        )

        obs, info = env.reset(seed=42)
        done = False
        steps = 0
        total_reward = 0

        while not done and steps < 500:
            mask = info["action_mask"]
            legal = np.where(mask)[0]
            if len(legal) == 0:
                break
            action = np.random.choice(legal)
            obs, reward, terminated, truncated, info = env.step(int(action))
            total_reward += reward
            done = terminated or truncated
            steps += 1

        assert done, f"Episode should complete within 500 steps (got {steps})"
        assert abs(total_reward) <= 5, f"Total reward should be bounded (got {total_reward})"


class TestCardLoading:
    """Test loading real card data from JSON."""

    def test_load_a1_cards(self):
        """Load the A1 Genetic Apex card set."""
        import os
        clear_card_db()

        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ptcgp", "data", "cards", "a1-genetic-apex.json"
        )

        if os.path.exists(json_path):
            count = load_cards_from_json(json_path)
            assert count > 0, "Should load at least some cards"

            # Verify some known cards
            cards = get_all_cards()
            card_names = [c.name for c in cards.values()]
            assert "Bulbasaur" in card_names
