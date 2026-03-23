"""Human agent - rich terminal UI for playing PTCGP interactively."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

from ptcgp.engine.game import GameState, get_card
from ptcgp.engine.types import (
    ActionType, EnergyType, StatusEffect, GamePhase,
    CardType, POINTS_TO_WIN,
)
from .base import Agent

console = Console()

# Energy type symbols
ENERGY_SYMBOLS = {
    EnergyType.GRASS: "[green]G[/green]",
    EnergyType.FIRE: "[red]F[/red]",
    EnergyType.WATER: "[blue]W[/blue]",
    EnergyType.LIGHTNING: "[yellow]L[/yellow]",
    EnergyType.PSYCHIC: "[magenta]P[/magenta]",
    EnergyType.FIGHTING: "[dark_orange]T[/dark_orange]",
    EnergyType.DARKNESS: "[dim]D[/dim]",
    EnergyType.METAL: "[bright_white]M[/bright_white]",
    EnergyType.COLORLESS: "[white]C[/white]",
}

STATUS_SYMBOLS = {
    StatusEffect.POISONED: "[green]PSN[/green]",
    StatusEffect.BURNED: "[red]BRN[/red]",
    StatusEffect.PARALYZED: "[yellow]PAR[/yellow]",
    StatusEffect.ASLEEP: "[blue]SLP[/blue]",
    StatusEffect.CONFUSED: "[magenta]CNF[/magenta]",
}


def _format_energy(energy: dict[EnergyType, int]) -> str:
    parts = []
    for etype, count in sorted(energy.items(), key=lambda x: x[0].value):
        symbol = ENERGY_SYMBOLS.get(etype, "?")
        parts.append(f"{symbol}x{count}")
    return " ".join(parts) if parts else "[dim]none[/dim]"


def _format_status(effects: set[StatusEffect]) -> str:
    if not effects:
        return ""
    return " ".join(STATUS_SYMBOLS.get(s, str(s)) for s in effects)


def _format_pokemon_slot(slot, show_details: bool = True) -> str:
    if slot.is_empty:
        return "[dim]--- Empty ---[/dim]"

    card = slot.card
    if not card:
        return "[dim]??? Unknown[/dim]"

    name = card.name
    if card.is_ex:
        name = f"[bold]{name}[/bold]"

    hp_pct = slot.current_hp / slot.max_hp if slot.max_hp > 0 else 0
    if hp_pct > 0.6:
        hp_color = "green"
    elif hp_pct > 0.3:
        hp_color = "yellow"
    else:
        hp_color = "red"

    lines = [f"{name}"]
    lines.append(f"  HP: [{hp_color}]{slot.current_hp}/{slot.max_hp}[/{hp_color}]")

    if show_details:
        lines.append(f"  Energy: {_format_energy(slot.attached_energy)}")
        status = _format_status(slot.status_effects)
        if status:
            lines.append(f"  Status: {status}")
        if slot.tool_card_id:
            tool = get_card(slot.tool_card_id)
            lines.append(f"  Tool: {tool.name}" if tool else "  Tool: ???")

    return "\n".join(lines)


def _render_board(state: GameState, player_idx: int) -> None:
    """Render the full game board from player_idx's perspective."""
    console.clear()
    me = state.players[player_idx]
    opp = state.players[1 - player_idx]

    # Header
    console.print(Panel(
        f"[bold]Pokemon TCG Pocket[/bold]  |  Turn {state.turn_number}  |  "
        f"{'[green]Your turn[/green]' if state.current_player == player_idx else '[red]Opponent turn[/red]'}",
        box=box.DOUBLE,
    ))

    # Opponent side
    console.print(f"\n[bold red]Opponent[/bold red]  Points: {'*' * opp.points}{'.' * (POINTS_TO_WIN - opp.points)}  "
                  f"Deck: {len(opp.deck)}  Hand: {len(opp.hand)}")

    # Opponent bench
    bench_panels = []
    for i, slot in enumerate(opp.bench):
        bench_panels.append(Panel(
            _format_pokemon_slot(slot, show_details=False),
            title=f"Bench {i+1}",
            width=22,
            border_style="red",
        ))
    if bench_panels:
        console.print(Columns(bench_panels, padding=(0, 1)))

    # Opponent active
    console.print(Panel(
        _format_pokemon_slot(opp.active),
        title="[bold red]Opponent Active[/bold red]",
        width=40,
        border_style="bold red",
    ))

    console.print("[dim]" + "─" * 60 + "[/dim]")

    # My active
    console.print(Panel(
        _format_pokemon_slot(me.active),
        title="[bold green]Your Active[/bold green]",
        width=40,
        border_style="bold green",
    ))

    # My bench
    bench_panels = []
    for i, slot in enumerate(me.bench):
        bench_panels.append(Panel(
            _format_pokemon_slot(slot),
            title=f"Bench {i+1}",
            width=22,
            border_style="green",
        ))
    if bench_panels:
        console.print(Columns(bench_panels, padding=(0, 1)))

    # My info
    console.print(f"\n[bold green]You[/bold green]  Points: {'*' * me.points}{'.' * (POINTS_TO_WIN - me.points)}  "
                  f"Deck: {len(me.deck)}")

    # Energy zone
    if state.energy_available:
        console.print(f"Energy Zone: {ENERGY_SYMBOLS.get(state.energy_available, '?')} "
                      f"{'[dim](already attached)[/dim]' if me.has_attached_energy else '[green](available)[/green]'}")
    else:
        console.print("Energy Zone: [dim]none[/dim]")

    # Hand
    console.print("\n[bold]Hand:[/bold]")
    for i, card_id in enumerate(me.hand):
        card = get_card(card_id)
        type_color = {
            CardType.POKEMON: "cyan",
            CardType.ITEM: "blue",
            CardType.SUPPORTER: "yellow",
            CardType.TOOL: "magenta",
        }.get(card.card_type, "white")
        extra = ""
        if card.is_pokemon:
            extra = f" [{card.element.value if card.element else '?'}] {card.hp}HP"
            if card.evolves_from:
                extra += f" (evolves from {card.evolves_from})"
        console.print(f"  [{type_color}][{i+1}] {card.name}{extra}[/{type_color}]")


def _describe_action(action: ActionType, state: GameState) -> str:
    """Get a human-readable description of an action."""
    player = state.current

    if action == ActionType.END_TURN:
        return "End Turn"

    if action in (ActionType.ATTACK_0, ActionType.ATTACK_1):
        idx = 0 if action == ActionType.ATTACK_0 else 1
        card = player.active.card
        if card and idx < len(card.attacks):
            atk = card.attacks[idx]
            cost_str = ", ".join(f"{e.value}x{c}" for e, c in atk.cost.items())
            effect = f" - {atk.effect_text}" if atk.effect_text else ""
            return f"Attack: {atk.name} ({atk.damage} dmg, cost: {cost_str}){effect}"
        return f"Attack {idx}"

    if ActionType.RETREAT_BENCH_0 <= action <= ActionType.RETREAT_BENCH_2:
        idx = action - ActionType.RETREAT_BENCH_0
        slot = player.bench[idx]
        name = slot.card.name if slot.card else "???"
        return f"Retreat to {name} (bench {idx+1})"

    if ActionType.PLAY_HAND_0 <= action <= ActionType.PLAY_HAND_9:
        idx = action - ActionType.PLAY_HAND_0
        if idx < len(player.hand):
            card = get_card(player.hand[idx])
            return f"Play: {card.name} ({card.card_type.value})"
        return f"Play hand [{idx+1}]"

    if action in (ActionType.ENERGY_ACTIVE, ActionType.ENERGY_BENCH_0,
                  ActionType.ENERGY_BENCH_1, ActionType.ENERGY_BENCH_2):
        if action == ActionType.ENERGY_ACTIVE:
            target = "Active"
        else:
            idx = action - ActionType.ENERGY_BENCH_0
            slot = player.bench[idx]
            target = f"Bench {idx+1} ({slot.card.name})" if slot.card else f"Bench {idx+1}"
        etype = state.energy_available.value if state.energy_available else "?"
        return f"Attach {etype} energy to {target}"

    if ActionType.ABILITY_ACTIVE <= action <= ActionType.ABILITY_BENCH_2:
        if action == ActionType.ABILITY_ACTIVE:
            slot = player.active
        else:
            idx = action - ActionType.ABILITY_BENCH_0
            slot = player.bench[idx]
        ability_name = slot.card.ability.name if slot.card and slot.card.ability else "?"
        return f"Use Ability: {ability_name}"

    if ActionType.TARGET_ACTIVE <= action <= ActionType.TARGET_OPP_BENCH_2:
        if action == ActionType.TARGET_ACTIVE:
            return "Target: Your Active"
        elif ActionType.TARGET_BENCH_0 <= action <= ActionType.TARGET_BENCH_2:
            idx = action - ActionType.TARGET_BENCH_0
            return f"Target: Your Bench {idx+1}"
        elif action == ActionType.TARGET_OPP_ACTIVE:
            return "Target: Opponent Active"
        else:
            idx = action - ActionType.TARGET_OPP_BENCH_0
            return f"Target: Opponent Bench {idx+1}"

    return f"Action {action.name}"


class HumanAgent(Agent):
    """Interactive human agent with rich terminal UI."""

    def choose_action(self, state: GameState, legal_actions: list[ActionType]) -> ActionType:
        _render_board(state, self.player_idx)

        console.print("\n[bold]Available Actions:[/bold]")
        for i, action in enumerate(legal_actions):
            desc = _describe_action(action, state)
            console.print(f"  [cyan][{i+1}][/cyan] {desc}")

        while True:
            try:
                choice = console.input("\n[bold]Choose action: [/bold]")
                idx = int(choice) - 1
                if 0 <= idx < len(legal_actions):
                    return legal_actions[idx]
                console.print("[red]Invalid choice. Try again.[/red]")
            except (ValueError, KeyboardInterrupt):
                console.print("[red]Enter a number.[/red]")

    def on_game_start(self, state: GameState, player_idx: int) -> None:
        super().on_game_start(state, player_idx)
        console.print(f"\n[bold green]Game started! You are Player {player_idx + 1}.[/bold green]")

    def on_game_end(self, state: GameState, winner: int | None) -> None:
        _render_board(state, self.player_idx)
        if winner is None:
            console.print("\n[bold yellow]Game ended in a draw![/bold yellow]")
        elif winner == self.player_idx:
            console.print("\n[bold green]You win![/bold green]")
        else:
            console.print("\n[bold red]You lose![/bold red]")
