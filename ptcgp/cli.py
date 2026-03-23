"""CLI entry point for PTCGP Battle Simulator."""

from __future__ import annotations

import click
from rich.console import Console

console = Console()


def _ensure_cards_loaded():
    """Load card database if not already loaded."""
    from ptcgp.engine.cards import get_all_cards, load_all_cards, load_cards_from_json
    import os
    if not get_all_cards():
        # Try new data dir first, then v3 assets
        data_dir = os.path.join(os.path.dirname(__file__), "data", "cards")
        v3_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "v3", "assets")

        loaded = load_all_cards()
        if loaded == 0 and os.path.exists(v3_dir):
            for fname in os.listdir(v3_dir):
                if fname.endswith(".json"):
                    loaded += load_cards_from_json(os.path.join(v3_dir, fname))

        console.print(f"[dim]Loaded {loaded} cards[/dim]")


@click.group()
def main():
    """Pokemon TCG Pocket Battle Simulator."""
    pass


@main.command()
@click.option("--deck1", default="grass", help="Deck for player 1 (grass, fire)")
@click.option("--deck2", default="fire", help="Deck for player 2")
@click.option("--human/--no-human", default=True, help="Play as human (player 1)")
@click.option("--opponent", default="heuristic", help="Opponent type: random, heuristic")
@click.option("--seed", default=None, type=int, help="Random seed")
@click.option("--debug/--no-debug", default=False)
def play(deck1: str, deck2: str, human: bool, opponent: str, seed: int | None, debug: bool):
    """Play a game of Pokemon TCG Pocket."""
    _ensure_cards_loaded()

    from ptcgp.data.decks.sample_decks import get_deck
    from ptcgp.engine.runner import run_game
    from ptcgp.agents.human import HumanAgent
    from ptcgp.agents.random_agent import RandomAgent
    from ptcgp.agents.heuristic import HeuristicAgent

    d1 = get_deck(deck1)
    d2 = get_deck(deck2)

    if human:
        agent1 = HumanAgent()
    else:
        agent1 = HeuristicAgent()

    if opponent == "random":
        agent2 = RandomAgent()
    else:
        agent2 = HeuristicAgent()

    console.print(f"\n[bold]Game: {d1['name']} vs {d2['name']}[/bold]")
    console.print(f"Player 1: {'Human' if human else 'Heuristic'}")
    console.print(f"Player 2: {opponent.capitalize()}")
    console.print()

    state, winner = run_game(
        d1["cards"], d2["cards"],
        d1["energy_types"], d2["energy_types"],
        agent1, agent2,
        seed=seed, debug=debug,
    )

    if not human:
        if winner is None:
            console.print("[yellow]Draw![/yellow]")
        else:
            console.print(f"[bold]Player {winner + 1} wins![/bold] "
                         f"(Points: {state.players[0].points}-{state.players[1].points}, "
                         f"Turn {state.turn_number})")


@main.command()
@click.option("--deck1", default="grass", help="Deck for player 1")
@click.option("--deck2", default="fire", help="Deck for player 2")
@click.option("--n-games", default=100, type=int, help="Number of games to simulate")
@click.option("--agent1", default="heuristic", help="Agent type for player 1")
@click.option("--agent2", default="heuristic", help="Agent type for player 2")
@click.option("--parallel/--no-parallel", default=False, help="Use multiprocessing")
@click.option("--seed", default=42, type=int, help="Base random seed")
def simulate(deck1: str, deck2: str, n_games: int, agent1: str, agent2: str,
             parallel: bool, seed: int):
    """Simulate many games between two decks."""
    _ensure_cards_loaded()

    from ptcgp.data.decks.sample_decks import get_deck
    from ptcgp.simulation.simulator import simulate as run_simulation

    d1 = get_deck(deck1)
    d2 = get_deck(deck2)

    console.print(f"\n[bold]Simulating {n_games} games: {d1['name']} vs {d2['name']}[/bold]")
    console.print(f"Agents: {agent1} vs {agent2}")
    console.print()

    results = run_simulation(
        d1["cards"], d2["cards"],
        d1["energy_types"], d2["energy_types"],
        agent1=agent1, agent2=agent2,
        n_games=n_games,
        parallel=parallel,
        base_seed=seed,
    )

    console.print(results.summary())


@main.command()
@click.option("--deck", default="grass", help="Deck to train with")
@click.option("--opponent-deck", default="fire", help="Opponent deck")
@click.option("--steps", default=50000, type=int, help="Training timesteps")
@click.option("--opponent", default="heuristic", help="Opponent type")
@click.option("--save-path", default="models/ppo_ptcgp", help="Model save path")
def train(deck: str, opponent_deck: str, steps: int, opponent: str, save_path: str):
    """Train an RL agent to play PTCGP."""
    _ensure_cards_loaded()

    from ptcgp.data.decks.sample_decks import get_deck
    from ptcgp.training.train import train_agent

    d1 = get_deck(deck)
    d2 = get_deck(opponent_deck)

    console.print(f"\n[bold]Training RL agent ({steps} steps)[/bold]")
    console.print(f"Deck: {d1['name']} vs {d2['name']}")
    console.print()

    model = train_agent(
        d1["cards"], d2["cards"],
        d1["energy_types"], d2["energy_types"],
        total_timesteps=steps,
        opponent=opponent,
        save_path=save_path,
    )

    console.print(f"\n[bold green]Training complete! Model saved to {save_path}[/bold green]")


@main.command(name="optimize-deck")
@click.option("--opponent-deck", default="fire", help="Deck to optimize against")
@click.option("--energy", default="grass", help="Energy type(s), comma-separated")
@click.option("--population", default=30, type=int, help="Population size")
@click.option("--generations", default=10, type=int, help="Number of generations")
@click.option("--games-per-eval", default=20, type=int, help="Games per fitness eval")
@click.option("--seed", default=42, type=int)
def optimize_deck(opponent_deck: str, energy: str, population: int,
                  generations: int, games_per_eval: int, seed: int):
    """Find the optimal deck using genetic algorithm."""
    _ensure_cards_loaded()

    from ptcgp.data.decks.sample_decks import get_deck
    from ptcgp.training.deck_optimizer import optimize_deck as run_optimizer
    from ptcgp.engine.types import EnergyType
    from ptcgp.engine.cards import get_card

    d2 = get_deck(opponent_deck)

    energy_map = {
        "grass": EnergyType.GRASS, "fire": EnergyType.FIRE,
        "water": EnergyType.WATER, "lightning": EnergyType.LIGHTNING,
        "psychic": EnergyType.PSYCHIC, "fighting": EnergyType.FIGHTING,
        "darkness": EnergyType.DARKNESS, "metal": EnergyType.METAL,
    }
    etypes = [energy_map[e.strip().lower()] for e in energy.split(",")]

    console.print(f"\n[bold]Optimizing deck against {d2['name']}[/bold]")
    console.print(f"Energy types: {[e.value for e in etypes]}")
    console.print(f"Population: {population}, Generations: {generations}")
    console.print()

    best = run_optimizer(
        opponent_deck=d2["cards"],
        opponent_energy=d2["energy_types"],
        energy_types=etypes,
        population_size=population,
        generations=generations,
        games_per_eval=games_per_eval,
        seed=seed,
    )

    console.print(f"\n[bold green]Best deck (fitness: {best.fitness:.1%}):[/bold green]")
    from collections import Counter
    card_counts = Counter(get_card(cid).name for cid in best.cards)
    for name, count in sorted(card_counts.items()):
        card = next(c for c in [get_card(cid) for cid in best.cards] if c.name == name)
        console.print(f"  {count}x {name} ({card.card_type.value})")


if __name__ == "__main__":
    main()
