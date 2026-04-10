"""HumanAgent — prompts a human player via the terminal."""
from __future__ import annotations

from ptcgp.agents.base import Agent
from ptcgp.engine.state import GameState
from ptcgp.engine.actions import Action


class HumanAgent(Agent):
    """Agent that prompts a human via the terminal."""

    def __init__(self, player_index: int = 0):
        self.player_index = player_index

    def on_game_start(self, state: GameState, player_index: int) -> None:
        from ptcgp.ui.theme import console
        self.player_index = player_index
        console.print(f"\n[bold]You are Player {player_index + 1}[/bold]")
        if state.first_player == player_index:
            console.print("[bold green]Coin flip: YOU go first![/bold green]")
        else:
            console.print("[bold yellow]Coin flip: Opponent goes first.[/bold yellow]")

    def choose_setup_placement(
        self,
        state: GameState,
        player_index: int,
        basics_in_hand: list[str],
    ) -> tuple[str, list[str]]:
        from ptcgp.ui.prompts import choose_setup_placement_prompt
        return choose_setup_placement_prompt(state, player_index, basics_in_hand)

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        from ptcgp.ui.renderer import render_state
        from ptcgp.ui.prompts import choose_action_prompt
        render_state(state, self.player_index)
        return choose_action_prompt(state, legal_actions, self.player_index)

    def choose_promotion(self, state: GameState, player_index: int, legal_promotions: list[Action]) -> Action:
        from ptcgp.ui.renderer import render_state
        from ptcgp.ui.prompts import choose_promotion_prompt
        render_state(state, self.player_index)
        return choose_promotion_prompt(state, player_index, legal_promotions)
