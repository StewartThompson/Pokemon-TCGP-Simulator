"""Command-line interface for the Pokemon TCG Pocket Battle Simulator."""
import click


@click.group()
def cli():
    """Pokemon TCG Pocket Battle Simulator."""
    pass


@cli.command()
@click.option("--deck", default="grass", help="Your deck: grass or fire")
@click.option("--opponent", default="fire", help="Opponent deck: grass or fire")
@click.option("--seed", default=None, type=int,
              help="Random seed (default: random; printed so you can reproduce)")
def play(deck, opponent, seed):
    """Play an interactive game against the heuristic AI."""
    import ptcgp.effects  # register all effect handlers
    from ptcgp.cards.database import load_defaults
    from ptcgp.decks.sample_decks import get_sample_deck
    from ptcgp.agents.human import HumanAgent
    from ptcgp.agents.heuristic import HeuristicAgent
    from ptcgp.runner.game_runner import run_game
    from ptcgp.ui.theme import console

    load_defaults()

    try:
        deck1_ids, energy1 = get_sample_deck(deck)
        deck2_ids, energy2 = get_sample_deck(opponent)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    human_agent = HumanAgent(player_index=0)
    ai_agent = HeuristicAgent()

    import random as _random
    if seed is None:
        seed = _random.SystemRandom().randrange(2**31)

    console.print(f"[bold]Starting game: {deck.title()} deck vs {opponent.title()} deck (AI)[/bold]")
    console.print(f"[dim]seed={seed} (re-run with --seed {seed} to replay this exact game)[/dim]")
    console.print("[dim]Press Ctrl+C at any time to quit.[/dim]\n")

    try:
        final_state, winner = run_game(
            human_agent, ai_agent,
            deck1_ids, deck2_ids,
            energy1, energy2,
            seed=seed,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Game aborted.[/yellow]")
        return
    except Exception:
        console.print("\n[bold red]==== GAME CRASHED ====[/bold red]")
        console.print_exception(show_locals=False)
        console.print(
            "[dim]Re-run with --seed to reproduce, and report the traceback above.[/dim]"
        )
        raise click.Abort()

    # Final board
    from ptcgp.ui.renderer import render_state
    render_state(final_state, 0)

    console.rule("[bold]GAME OVER[/bold]")
    p1_pts = final_state.players[0].points
    p2_pts = final_state.players[1].points
    console.print(
        f"Final score: [bold]YOU {p1_pts}[/bold]  |  [bold]OPPONENT {p2_pts}[/bold]",
        justify="center",
    )
    if winner == 0:
        console.print("[bold green]*** YOU WIN! ***[/bold green]", justify="center")
    elif winner == 1:
        console.print("[bold red]*** YOU LOSE ***[/bold red]", justify="center")
    elif winner == -1:
        console.print("[bold yellow]*** DRAW ***[/bold yellow]", justify="center")
    else:
        console.print("[yellow]Game ended (unknown result)[/yellow]", justify="center")


@cli.command()
@click.option("--games", default=50, type=int, help="Number of games to profile (default: 50)")
@click.option("--deck1", default="grass", help="Deck for player 1")
@click.option("--deck2", default="fire", help="Deck for player 2")
@click.option("--agent1", default="heuristic", type=click.Choice(["random", "heuristic"]))
@click.option("--agent2", default="heuristic", type=click.Choice(["random", "heuristic"]))
@click.option("--seed", default=42, type=int, help="Base random seed")
@click.option("--top", default=30, type=int, help="Number of top functions to show (default: 30)")
@click.option("--sort", default="cumulative",
              type=click.Choice(["cumulative", "tottime", "calls"]),
              help="Sort column (default: cumulative)")
@click.option("--output", default=None, type=str,
              help="Save raw .prof file to this path (open with snakeviz or py-spy)")
def profile(games, deck1, deck2, agent1, agent2, seed, top, sort, output):
    """Profile N single-process games and show the top hottest functions.

    Runs in a single worker (no multiprocessing) so cProfile sees the full
    call stack. Use this before and after optimizations to measure impact.

    Examples:
        ptcgp profile --games 50
        ptcgp profile --games 100 --sort tottime --top 20
        ptcgp profile --games 50 --output profile.prof  # then: snakeviz profile.prof
    """
    import cProfile
    import io
    import pstats
    import time
    import ptcgp.effects  # noqa: F401 — registers all effect handlers
    from ptcgp.cards.database import load_defaults
    from ptcgp.ui.theme import console

    load_defaults()

    from ptcgp.agents.heuristic import HeuristicAgent
    from ptcgp.agents.random_agent import RandomAgent
    from ptcgp.decks.sample_decks import get_sample_deck
    from ptcgp.runner.game_runner import run_game

    deck1_ids, energy1 = get_sample_deck(deck1)
    deck2_ids, energy2 = get_sample_deck(deck2)

    def _make_agent(agent_type: str):
        return HeuristicAgent() if agent_type == "heuristic" else RandomAgent()

    console.print(
        f"[bold]Profiling {games} games[/bold] "
        f"({deck1}/{agent1} vs {deck2}/{agent2}) "
        f"[dim]seed={seed}, in-process (no multiprocessing)[/dim]"
    )

    # Run games directly in-process so cProfile captures the full call stack.
    wins = [0, 0]
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()

    for i in range(games):
        a1 = _make_agent(agent1)
        a2 = _make_agent(agent2)
        _, winner = run_game(
            a1, a2,
            list(deck1_ids), list(deck2_ids),
            list(energy1), list(energy2),
            seed=seed + i,
        )
        if winner == 0:
            wins[0] += 1
        elif winner == 1:
            wins[1] += 1

    pr.disable()
    elapsed = time.perf_counter() - t0

    games_per_sec = games / elapsed if elapsed > 0 else 0
    ms_per_game = elapsed * 1000 / games if games > 0 else 0

    completed = wins[0] + wins[1]
    p1_rate = wins[0] / completed if completed else 0.0
    p2_rate = wins[1] / completed if completed else 0.0
    console.print(
        f"\n[bold]Results:[/bold] "
        f"P1 {wins[0]} wins ({p1_rate * 100:.1f}%)  |  "
        f"P2 {wins[1]} wins ({p2_rate * 100:.1f}%)"
    )
    console.print(
        f"[bold]Timing:[/bold] {elapsed:.2f}s total  |  "
        f"[bold]{games_per_sec:.1f} games/sec[/bold]  |  "
        f"{ms_per_game:.1f} ms/game"
    )

    if output:
        pr.dump_stats(output)
        console.print(f"[dim]Raw profile saved to {output!r} — open with: snakeviz {output}[/dim]")

    # Print top-N functions using pstats
    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf)
    ps.strip_dirs()
    ps.sort_stats(sort)
    ps.print_stats(top)

    raw = buf.getvalue()

    # Pretty-print via Rich — highlight the table lines
    console.print(f"\n[bold]Top {top} functions by [cyan]{sort}[/cyan] time:[/bold]")
    for line in raw.splitlines():
        if not line.strip():
            continue
        # Header line (ncalls / tottime / ...)
        if "ncalls" in line:
            console.print(f"[bold dim]{line}[/bold dim]")
        # Function lines — highlight our own code in yellow
        elif "ptcgp" in line:
            console.print(f"[yellow]{line}[/yellow]")
        elif line.startswith("   "):
            console.print(f"[dim]{line}[/dim]")
        else:
            console.print(line)


@cli.command()
@click.option("--games", default=100, type=int, help="Number of games to simulate")
@click.option("--deck1", default="grass", help="Deck for player 1")
@click.option("--deck2", default="fire", help="Deck for player 2")
@click.option("--agent1", default="heuristic", type=click.Choice(["random", "heuristic"]), help="Agent for player 1")
@click.option("--agent2", default="heuristic", type=click.Choice(["random", "heuristic"]), help="Agent for player 2")
@click.option("--seed", default=None, type=int,
              help="Base random seed (default: random; printed so you can reproduce)")
@click.option("--workers", default=None, type=int, help="Number of parallel workers (default: CPU count)")
def simulate(games, deck1, deck2, agent1, agent2, seed, workers):
    """Simulate N bot-vs-bot games in parallel and print win rates."""
    import random as _random
    import ptcgp.effects  # noqa: F401 — registers all effect handlers
    from ptcgp.cards.database import load_defaults
    from ptcgp.runner.batch_runner import run_batch_simple
    from ptcgp.ui.theme import console

    load_defaults()

    n_workers = workers  # None means use cpu_count in run_batch

    if seed is None:
        seed = _random.SystemRandom().randrange(2**31)

    console.print(f"[bold]Simulating {games} games[/bold] "
                  f"({deck1}/{agent1} vs {deck2}/{agent2}) "
                  f"[dim]seed={seed}, workers={n_workers or 'auto'}[/dim]")

    result = run_batch_simple(
        deck1_name=deck1,
        deck2_name=deck2,
        agent1_type=agent1,
        agent2_type=agent2,
        n_games=games,
        base_seed=seed,
        n_workers=n_workers,
    )

    p1_rate, p2_rate = result.win_rate
    console.print(f"\n[bold]Results after {games} games:[/bold]")
    console.print(f"  Player 1 ({deck1}/{agent1}): {result.wins[0]} wins ({p1_rate * 100:.1f}%)")
    console.print(f"  Player 2 ({deck2}/{agent2}): {result.wins[1]} wins ({p2_rate * 100:.1f}%)")
    console.print(f"  Ties: {result.ties} ({result.tie_rate * 100:.1f}%)")
    if result.errors:
        console.print(f"  [red]Errors: {result.errors}[/red]")
