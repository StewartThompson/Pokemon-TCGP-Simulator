"""Genetic algorithm deck optimizer for PTCGP."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from ptcgp.engine.types import EnergyType, DECK_SIZE, MAX_COPIES_PER_CARD
from ptcgp.engine.cards import get_all_cards, CardData, CardType
from ptcgp.simulation.simulator import simulate


@dataclass
class DeckCandidate:
    """A deck candidate in the evolutionary population."""
    cards: list[str]  # Card IDs
    energy_types: list[EnergyType]
    fitness: float = 0.0

    def is_valid(self) -> bool:
        """Check if this deck meets all PTCGP rules."""
        if len(self.cards) != DECK_SIZE:
            return False

        # Max 2 copies per card name
        from collections import Counter
        from ptcgp.engine.cards import get_card
        name_counts = Counter(get_card(cid).name for cid in self.cards)
        if any(c > MAX_COPIES_PER_CARD for c in name_counts.values()):
            return False

        # At least 1 Basic Pokemon
        if not any(get_card(cid).is_basic for cid in self.cards if get_card(cid).is_pokemon):
            return False

        # 1-3 energy types
        if not (1 <= len(self.energy_types) <= 3):
            return False

        return True


def _get_compatible_cards(energy_types: list[EnergyType]) -> list[CardData]:
    """Get cards that work with the given energy types."""
    all_cards = get_all_cards()
    compatible = []
    for card in all_cards.values():
        if card.card_type != CardType.POKEMON:
            compatible.append(card)
            continue
        # Pokemon should match energy types or be colorless
        if card.element in energy_types or card.element == EnergyType.COLORLESS:
            compatible.append(card)
        # Also include pokemon that only need colorless energy
        elif card.attacks:
            all_colorless = all(
                all(e == EnergyType.COLORLESS for e in atk.cost)
                for atk in card.attacks
            )
            if all_colorless:
                compatible.append(card)
    return compatible


def generate_random_deck(
    energy_types: list[EnergyType] | None = None,
    rng: random.Random | None = None,
) -> DeckCandidate:
    """Generate a random valid deck."""
    rng = rng or random.Random()

    if energy_types is None:
        all_types = [e for e in EnergyType if e != EnergyType.COLORLESS]
        n_types = rng.randint(1, 2)
        energy_types = rng.sample(all_types, n_types)

    compatible = _get_compatible_cards(energy_types)
    if not compatible:
        # Fallback to all cards
        compatible = list(get_all_cards().values())

    # Build deck
    deck: list[str] = []
    name_counts: dict[str, int] = {}

    # Ensure at least 4 Basic Pokemon
    basics = [c for c in compatible if c.is_pokemon and c.is_basic]
    evolutions = [c for c in compatible if c.is_pokemon and not c.is_basic]
    trainers = [c for c in compatible if not c.is_pokemon]

    # Add basics (4-8)
    n_basics = rng.randint(4, min(8, len(basics) * 2))
    for _ in range(n_basics):
        if not basics:
            break
        card = rng.choice(basics)
        if name_counts.get(card.name, 0) < MAX_COPIES_PER_CARD:
            deck.append(card.id)
            name_counts[card.name] = name_counts.get(card.name, 0) + 1

    # Add evolutions (0-6)
    n_evos = rng.randint(0, min(6, DECK_SIZE - len(deck)))
    for _ in range(n_evos):
        if not evolutions:
            break
        card = rng.choice(evolutions)
        # Check that we have the pre-evolution
        if card.evolves_from:
            from ptcgp.engine.cards import get_card
            has_preevo = any(
                get_card(cid).name == card.evolves_from
                for cid in deck
            )
            if not has_preevo:
                continue
        if name_counts.get(card.name, 0) < MAX_COPIES_PER_CARD:
            deck.append(card.id)
            name_counts[card.name] = name_counts.get(card.name, 0) + 1

    # Fill with trainers
    while len(deck) < DECK_SIZE and trainers:
        card = rng.choice(trainers)
        if name_counts.get(card.name, 0) < MAX_COPIES_PER_CARD:
            deck.append(card.id)
            name_counts[card.name] = name_counts.get(card.name, 0) + 1

    # If still not full, add more basics
    while len(deck) < DECK_SIZE and basics:
        card = rng.choice(basics)
        if name_counts.get(card.name, 0) < MAX_COPIES_PER_CARD:
            deck.append(card.id)
            name_counts[card.name] = name_counts.get(card.name, 0) + 1

    # Trim if over
    deck = deck[:DECK_SIZE]

    candidate = DeckCandidate(cards=deck, energy_types=energy_types)
    return candidate


def mutate_deck(deck: DeckCandidate, rng: random.Random | None = None) -> DeckCandidate:
    """Create a mutated version of a deck."""
    rng = rng or random.Random()
    new_cards = list(deck.cards)
    new_energy = list(deck.energy_types)

    compatible = _get_compatible_cards(new_energy)
    if not compatible:
        return deck

    # 1-3 card swaps
    n_swaps = rng.randint(1, 3)
    for _ in range(n_swaps):
        if len(new_cards) == 0 or len(compatible) == 0:
            break

        # Remove a random card
        idx = rng.randint(0, len(new_cards) - 1)
        new_cards.pop(idx)

        # Add a random compatible card (respecting copy limits)
        from ptcgp.engine.cards import get_card
        from collections import Counter
        name_counts = Counter(get_card(cid).name for cid in new_cards)

        candidates = [c for c in compatible if name_counts.get(c.name, 0) < MAX_COPIES_PER_CARD]
        if candidates:
            card = rng.choice(candidates)
            new_cards.append(card.id)

    # Ensure deck is valid size
    while len(new_cards) < DECK_SIZE:
        basics = [c for c in compatible if c.is_basic]
        if basics:
            card = rng.choice(basics)
            new_cards.append(card.id)
        else:
            break
    new_cards = new_cards[:DECK_SIZE]

    # Occasionally mutate energy types
    if rng.random() < 0.1:
        all_types = [e for e in EnergyType if e != EnergyType.COLORLESS]
        if rng.random() < 0.5 and len(new_energy) < 3:
            new_energy.append(rng.choice(all_types))
        elif len(new_energy) > 1:
            new_energy.pop(rng.randint(0, len(new_energy) - 1))

    result = DeckCandidate(cards=new_cards, energy_types=new_energy)
    return result


def crossover(parent1: DeckCandidate, parent2: DeckCandidate, rng: random.Random | None = None) -> DeckCandidate:
    """Create a child deck by crossing over two parents."""
    rng = rng or random.Random()

    # Pick energy types from one parent
    energy_types = list(rng.choice([parent1, parent2]).energy_types)

    # Mix cards from both parents
    from collections import Counter
    from ptcgp.engine.cards import get_card

    all_cards = list(parent1.cards) + list(parent2.cards)
    rng.shuffle(all_cards)

    new_cards: list[str] = []
    name_counts: dict[str, int] = {}

    for card_id in all_cards:
        if len(new_cards) >= DECK_SIZE:
            break
        card = get_card(card_id)
        if name_counts.get(card.name, 0) < MAX_COPIES_PER_CARD:
            new_cards.append(card_id)
            name_counts[card.name] = name_counts.get(card.name, 0) + 1

    # Fill if needed
    compatible = _get_compatible_cards(energy_types)
    while len(new_cards) < DECK_SIZE and compatible:
        card = rng.choice(compatible)
        if name_counts.get(card.name, 0) < MAX_COPIES_PER_CARD:
            new_cards.append(card.id)
            name_counts[card.name] = name_counts.get(card.name, 0) + 1

    return DeckCandidate(cards=new_cards[:DECK_SIZE], energy_types=energy_types)


def evaluate_deck(
    candidate: DeckCandidate,
    opponent_deck: list[str],
    opponent_energy: list[EnergyType],
    n_games: int = 50,
    base_seed: int = 0,
) -> float:
    """Evaluate a deck's fitness by playing against an opponent."""
    results = simulate(
        deck1=candidate.cards,
        deck2=opponent_deck,
        energy_types1=candidate.energy_types,
        energy_types2=opponent_energy,
        agent1="heuristic",
        agent2="heuristic",
        n_games=n_games,
        base_seed=base_seed,
    )
    return results.win_rate_0


def optimize_deck(
    opponent_deck: list[str],
    opponent_energy: list[EnergyType],
    population_size: int = 50,
    generations: int = 20,
    games_per_eval: int = 30,
    mutation_rate: float = 0.3,
    crossover_rate: float = 0.3,
    elite_size: int = 5,
    energy_types: list[EnergyType] | None = None,
    seed: int = 0,
    verbose: bool = True,
) -> DeckCandidate:
    """Run genetic algorithm to find optimal deck against an opponent.

    Args:
        opponent_deck: The deck to optimize against
        opponent_energy: Opponent's energy types
        population_size: Number of decks in each generation
        generations: Number of generations to evolve
        games_per_eval: Games to play per fitness evaluation
        mutation_rate: Probability of mutation vs crossover
        crossover_rate: Probability of crossover
        elite_size: Number of top decks to keep unchanged
        energy_types: Fixed energy types (None = evolve them too)
        seed: Random seed
        verbose: Print progress

    Returns:
        Best deck found
    """
    rng = random.Random(seed)

    # Generate initial population
    population: list[DeckCandidate] = []
    for i in range(population_size):
        candidate = generate_random_deck(energy_types=energy_types, rng=random.Random(seed + i))
        population.append(candidate)

    best_ever: DeckCandidate | None = None
    best_fitness: float = 0.0

    for gen in range(generations):
        # Evaluate fitness
        for i, candidate in enumerate(population):
            if not candidate.is_valid():
                candidate.fitness = 0.0
                continue
            candidate.fitness = evaluate_deck(
                candidate, opponent_deck, opponent_energy,
                n_games=games_per_eval,
                base_seed=seed + gen * 10000 + i * 100,
            )

        # Sort by fitness
        population.sort(key=lambda d: d.fitness, reverse=True)

        if population[0].fitness > best_fitness:
            best_fitness = population[0].fitness
            best_ever = DeckCandidate(
                cards=list(population[0].cards),
                energy_types=list(population[0].energy_types),
                fitness=best_fitness,
            )

        if verbose:
            from ptcgp.engine.cards import get_card
            top_cards = ", ".join(get_card(cid).name for cid in population[0].cards[:5])
            print(f"Gen {gen+1}/{generations}: Best={population[0].fitness:.1%}, "
                  f"Avg={sum(d.fitness for d in population) / len(population):.1%}, "
                  f"Cards: {top_cards}...")

        # Create next generation
        new_population: list[DeckCandidate] = []

        # Keep elite
        for i in range(min(elite_size, len(population))):
            new_population.append(DeckCandidate(
                cards=list(population[i].cards),
                energy_types=list(population[i].energy_types),
            ))

        # Fill rest with mutations and crossovers
        while len(new_population) < population_size:
            r = rng.random()
            if r < mutation_rate:
                parent = rng.choice(population[:population_size // 2])
                child = mutate_deck(parent, rng)
            elif r < mutation_rate + crossover_rate:
                p1 = rng.choice(population[:population_size // 2])
                p2 = rng.choice(population[:population_size // 2])
                child = crossover(p1, p2, rng)
            else:
                child = generate_random_deck(energy_types=energy_types, rng=rng)

            new_population.append(child)

        population = new_population

    return best_ever or population[0]
