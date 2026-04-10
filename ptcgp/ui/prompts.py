"""Interactive action selection prompts for the terminal UI."""
from __future__ import annotations

from rich.prompt import IntPrompt

from ptcgp.cards.database import get_card
from ptcgp.engine.actions import Action, ActionKind
from ptcgp.engine.state import GameState
from ptcgp.ui.theme import ELEMENT_SYMBOLS, console


def choose_action_prompt(
    state: GameState, legal_actions: list[Action], human_player: int
) -> Action:
    """Show a numbered menu of legal actions; return the chosen Action."""
    console.print("\n[bold]Choose an action:[/bold]")
    for i, action in enumerate(legal_actions):
        console.print(f"  {i + 1}. {_describe_action(state, action, human_player)}")

    while True:
        try:
            choice = IntPrompt.ask("Enter number", default=len(legal_actions))
            if 1 <= choice <= len(legal_actions):
                return legal_actions[choice - 1]
            console.print(f"[red]Please enter 1-{len(legal_actions)}[/red]")
        except KeyboardInterrupt:
            raise
        except ValueError:
            console.print("[red]Invalid input[/red]")


def _describe_target(state: GameState, target) -> str:
    """Return a short human-readable label for a SlotRef target."""
    player = state.players[target.player]
    if target.is_active():
        slot = player.active
        label = "active"
    else:
        slot = player.bench[target.slot] if 0 <= target.slot < len(player.bench) else None
        label = f"bench[{target.slot}]"
    if slot is None:
        return label
    card = get_card(slot.card_id)
    return f"{card.name} ({label})"


def _describe_action(state: GameState, action: Action, human_player: int) -> str:
    player = state.players[human_player]

    if action.kind == ActionKind.END_TURN:
        return "End Turn"

    if action.kind == ActionKind.ATTACK:
        if player.active is not None and action.attack_index is not None:
            card = get_card(player.active.card_id)
            if action.attack_index < len(card.attacks):
                atk = card.attacks[action.attack_index]
                suffix = ""
                if action.target is not None:
                    suffix = f" (energy → {_describe_target(state, action.target)})"
                return f"Attack: {atk.name} ({atk.damage} damage){suffix}"
        return "Attack"

    if action.kind == ActionKind.PLAY_CARD:
        if action.hand_index is not None and action.hand_index < len(player.hand):
            card = get_card(player.hand[action.hand_index])
            target_str = ""
            if action.target is not None:
                target_str = f" -> {_describe_target(state, action.target)}"
            evo_str = ""
            if action.extra_hand_index is not None and action.extra_hand_index < len(player.hand):
                evo_card = get_card(player.hand[action.extra_hand_index])
                evo_str = f" (evolve into {evo_card.name})"
            return f"Play: {card.name}{target_str}{evo_str}"
        return "Play Card"

    if action.kind == ActionKind.ATTACH_ENERGY:
        sym = ELEMENT_SYMBOLS.get(player.energy_available, "?")
        if action.target is not None:
            target_str = "active" if action.target.is_active() else f"bench[{action.target.slot}]"
        else:
            target_str = "?"
        return f"Attach Energy {sym} -> {target_str}"

    if action.kind == ActionKind.EVOLVE:
        if action.hand_index is not None and action.hand_index < len(player.hand):
            card = get_card(player.hand[action.hand_index])
            if action.target is not None:
                target_str = "active" if action.target.is_active() else f"bench[{action.target.slot}]"
            else:
                target_str = "?"
            return f"Evolve: {card.name} -> {target_str}"
        return "Evolve"

    if action.kind == ActionKind.RETREAT:
        if action.target is not None:
            slot_index = action.target.slot
            if 0 <= slot_index < len(player.bench) and player.bench[slot_index] is not None:
                bench_card = get_card(player.bench[slot_index].card_id)
                return f"Retreat -> {bench_card.name}"
        return "Retreat"

    if action.kind == ActionKind.USE_ABILITY:
        if action.target is not None:
            target_player = state.players[action.target.player]
            if action.target.is_active():
                slot = target_player.active
            else:
                idx = action.target.slot
                slot = target_player.bench[idx] if 0 <= idx < len(target_player.bench) else None
            if slot is not None:
                card = get_card(slot.card_id)
                ability_name = card.ability.name if card.ability else "?"
                return f"Ability: {ability_name}"
        return "Use Ability"

    if action.kind == ActionKind.PROMOTE:
        if action.target is not None:
            target_player = state.players[action.target.player]
            slot_idx = action.target.slot
            if 0 <= slot_idx < len(target_player.bench) and target_player.bench[slot_idx] is not None:
                bench_card = get_card(target_player.bench[slot_idx].card_id)
                return f"Promote: {bench_card.name}"
        return "Promote"

    return str(action)


def choose_setup_placement_prompt(
    state: GameState,
    player_index: int,
    basics_in_hand: list[str],
) -> tuple[str, list[str]]:
    """Prompt the human to choose their Active and bench during setup."""
    from ptcgp.engine.constants import BENCH_SIZE

    console.print("\n[bold cyan]== SETUP PHASE ==[/bold cyan]")

    # Show full hand for context
    console.print("\n[dim]Your opening hand:[/dim]")
    player = state.players[player_index]
    for cid in player.hand:
        card = get_card(cid)
        tag = " [bold cyan](Basic)[/bold cyan]" if cid in basics_in_hand else ""
        console.print(f"  • {card.name}{tag}")

    # Choose Active
    console.print("\n[bold]Choose your Active Pokemon:[/bold]")
    for i, cid in enumerate(basics_in_hand):
        card = get_card(cid)
        console.print(f"  {i + 1}. {card.name}  ({card.hp} HP)")

    while True:
        try:
            choice = IntPrompt.ask("Enter number")
            if 1 <= choice <= len(basics_in_hand):
                active_id = basics_in_hand[choice - 1]
                break
            console.print(f"[red]Enter 1-{len(basics_in_hand)}[/red]")
        except KeyboardInterrupt:
            raise
        except ValueError:
            console.print("[red]Invalid input[/red]")

    active_card = get_card(active_id)
    console.print(f"[green]{active_card.name} will be your Active Pokemon.[/green]")

    # Choose bench (optional)
    remaining = [cid for cid in basics_in_hand if cid != active_id]
    bench_ids: list[str] = []

    if remaining:
        console.print(f"\n[bold]Place Pokemon on your Bench? (up to {BENCH_SIZE}, enter 0 to stop)[/bold]")
        for _slot in range(min(BENCH_SIZE, len(remaining))):
            available = [cid for cid in remaining if cid not in bench_ids]
            if not available:
                break
            console.print("\n  Available for bench:")
            for i, cid in enumerate(available):
                card = get_card(cid)
                console.print(f"    {i + 1}. {card.name}  ({card.hp} HP)")
            console.print("    0. Done — no more bench")
            bench_done = False
            while True:
                try:
                    choice = IntPrompt.ask("Enter number", default=0)
                    if choice == 0:
                        bench_done = True
                        break
                    if 1 <= choice <= len(available):
                        bench_ids.append(available[choice - 1])
                        chosen_card = get_card(available[choice - 1])
                        console.print(f"[green]{chosen_card.name} added to bench.[/green]")
                        break
                    console.print(f"[red]Enter 0-{len(available)}[/red]")
                except KeyboardInterrupt:
                    raise
                except ValueError:
                    console.print("[red]Invalid input[/red]")
                    bench_done = True
                    break
            if bench_done:
                break

    return active_id, bench_ids


def choose_promotion_prompt(
    state: GameState, player_index: int, legal_promotions: list[Action]
) -> Action:
    """Prompt the player to choose which bench Pokemon to promote."""
    console.print("\n[bold red]Your Active Pokemon was knocked out! Choose a new Active:[/bold red]")
    for i, action in enumerate(legal_promotions):
        if action.target is not None:
            slot_idx = action.target.slot
            slot = state.players[player_index].bench[slot_idx]
            if slot is not None:
                card = get_card(slot.card_id)
                console.print(f"  {i + 1}. {card.name} ({slot.current_hp}/{slot.max_hp} HP)")
                continue
        console.print(f"  {i + 1}. (unknown)")

    while True:
        try:
            choice = IntPrompt.ask("Enter number")
            if 1 <= choice <= len(legal_promotions):
                return legal_promotions[choice - 1]
            console.print(f"[red]Please enter 1-{len(legal_promotions)}[/red]")
        except KeyboardInterrupt:
            raise
        except ValueError:
            console.print("[red]Invalid input[/red]")
