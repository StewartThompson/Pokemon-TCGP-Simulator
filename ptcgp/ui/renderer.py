"""Render the game state to the terminal using rich. Read-only — never mutates state."""
from __future__ import annotations

from rich.panel import Panel

from ptcgp.cards.database import get_card
from ptcgp.cards.types import CostSymbol
from ptcgp.engine.state import GameState, PokemonSlot
from ptcgp.ui.theme import ELEMENT_SYMBOLS, STATUS_SYMBOLS, console


def render_state(state: GameState, human_player: int) -> None:
    """Print the current game state to the terminal."""
    console.clear()
    console.rule("[bold]Pokemon TCG Pocket[/bold]")

    opponent_idx = 1 - human_player
    _render_player_section(state, opponent_idx, label="OPPONENT", show_hand_contents=False)
    console.print()

    if state.current_player == human_player:
        console.print("[bold green]>>> YOUR TURN <<<[/bold green]", justify="center")
    else:
        console.print("[bold red]>>> OPPONENT'S TURN <<<[/bold red]", justify="center")
    console.print()

    _render_player_section(state, human_player, label="YOU", show_hand_contents=True)


def _render_player_section(
    state: GameState, player_idx: int, label: str, show_hand_contents: bool
) -> None:
    player = state.players[player_idx]

    turn_display = max(0, (state.turn_number + 1) // 2)  # human-friendly: round number
    lines: list[str] = [
        f"Points: {player.points}/3  |  Deck: {len(player.deck)}  |  Hand: {len(player.hand)}  |  Turn: {turn_display}",
    ]

    if player.energy_available is not None and player_idx == state.current_player:
        sym = ELEMENT_SYMBOLS.get(player.energy_available, "?")
        lines.append(f"Energy Available: {sym}")

    if player.active is not None:
        lines.append("")
        lines.append("ACTIVE: " + _format_slot(player.active))
        tool_line = _format_tool_line(player.active)
        if tool_line:
            lines.append(tool_line)
        card = get_card(player.active.card_id)
        for i, atk in enumerate(card.attacks):
            lines.append(f"  ATK{i + 1}: {atk.name} ({atk.damage}) {_format_cost(atk.cost)}")
    else:
        lines.append("ACTIVE: [empty]")

    bench_parts: list[str] = []
    for slot in player.bench:
        if slot is not None:
            bench_parts.append(_format_slot(slot, short=True))
        else:
            bench_parts.append("[dim]---[/dim]")
    lines.append("")
    lines.append("BENCH:  " + "  ".join(bench_parts))

    if show_hand_contents and player.hand:
        lines.append("")
        hand_names = [get_card(cid).name for cid in player.hand]
        lines.append("HAND:   " + ", ".join(hand_names))

    title_color = "green" if player_idx == state.current_player else "white"
    console.print(Panel("\n".join(lines), title=f"[{title_color}]{label}[/{title_color}]"))


_DIGIT_EMOJI: dict[int, str] = {
    0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣",
    5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟",
}


def _format_attached_energy(slot: PokemonSlot) -> str:
    """Return a comma-separated ``count emoji`` string, or '' if no energy."""
    pieces: list[str] = []
    for element, count in slot.attached_energy.items():
        if count <= 0:
            continue
        digit = _DIGIT_EMOJI.get(count, str(count))
        pieces.append(f"{digit}{ELEMENT_SYMBOLS.get(element, '?')}")
    return ", ".join(pieces)


def _format_slot(slot: PokemonSlot, short: bool = False) -> str:
    card = get_card(slot.card_id)
    ex_tag = " ★EX" if card.is_ex else ""
    hp_str = f"{slot.current_hp}/{slot.max_hp}"
    status_icons = " ".join(STATUS_SYMBOLS.get(s.name, "") for s in slot.status_effects)
    status_str = f" [{status_icons}]" if status_icons else ""
    energy_str = _format_attached_energy(slot)

    if short:
        # Bench entries stay compact; tools are shown as a small 🎒 marker.
        energy_tag = f" {energy_str}" if energy_str else ""
        tool_tag = " 🎒" if slot.tool_card_id else ""
        return f"[{card.name} {hp_str}{ex_tag}{energy_tag}{tool_tag}]"

    energy_tag = f"  (Energy: {energy_str})" if energy_str else ""
    return f"{card.name}{ex_tag} {hp_str}{energy_tag}{status_str}"


def _format_tool_line(slot: PokemonSlot) -> str:
    """Return a 'TOOL: {name}' line, or empty string if no tool is attached."""
    if not slot.tool_card_id:
        return ""
    try:
        tool_card = get_card(slot.tool_card_id)
        return f"  TOOL: {tool_card.name}"
    except KeyError:
        return f"  TOOL: {slot.tool_card_id}"


def _format_cost(cost: tuple[CostSymbol, ...]) -> str:
    parts: list[str] = []
    for c in cost:
        if c == CostSymbol.COLORLESS:
            parts.append("⚪")
            continue
        try:
            parts.append(ELEMENT_SYMBOLS.get(c.to_element(), "?"))
        except ValueError:
            parts.append("?")
    return "".join(parts)
