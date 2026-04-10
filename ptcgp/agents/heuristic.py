"""HeuristicAgent — strong context-aware priority-based agent.

This agent scores every legal action and plays the highest-scoring one each
step. The scoring integrates:

  • **KO awareness** — massive bonus when an attack or energy attach enables a
    KO this turn, especially against EX Pokemon (2 pts).
  • **Turn-order sequencing** — Professor's Research is played first to expand
    the hand; evolutions score very high so we upgrade before attacking;
    tools are attached to the main attacker early.
  • **Energy routing** — energy is funnelled to the Pokemon with the best
    damage-per-remaining-energy ratio, factoring in HP, active position, and
    whether the energy type matches the attack cost.
  • **Type-advantage retreating** — swap to a bench Pokemon that has weakness
    coverage against the opponent's active.
  • **Heal economy** — Potion only fires when the heal amount prevents a
    potential one-shot; Butterfree Powder Heal fires freely but below attack
    priority.
  • **Bench building** — fill the bench aggressively in the first few turns.

All tiebreakers use ``state.rng`` for full seed-determinism.
"""
from __future__ import annotations

from typing import Optional

from ptcgp.agents.base import Agent
from ptcgp.cards.card import Card
from ptcgp.cards.database import get_card
from ptcgp.cards.types import CardKind, CostSymbol, Element, Stage
from ptcgp.effects.parser import parse_effect_text
from ptcgp.engine.actions import Action, ActionKind, SlotRef
from ptcgp.engine.attack import can_pay_cost
from ptcgp.engine.constants import WEAKNESS_BONUS
from ptcgp.engine.slot_utils import get_slot
from ptcgp.engine.state import GameState, PlayerState, PokemonSlot, StatusEffect


class HeuristicAgent(Agent):

    def __init__(self, seed: int | None = None) -> None:
        del seed

    # ------------------------------------------------------------------ #
    # Public Agent API
    # ------------------------------------------------------------------ #

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        scored = [(self._score(state, a), a) for a in legal_actions]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def choose_promotion(
        self, state: GameState, player_index: int, legal_promotions: list[Action],
    ) -> Action:
        def key(a: Action) -> float:
            if a.target is None:
                return 0.0
            slot = state.players[player_index].bench[a.target.slot]
            if slot is None:
                return 0.0
            card = get_card(slot.card_id)
            best_ready = max(
                (atk.damage for atk in card.attacks if can_pay_cost(slot, atk.cost)),
                default=0,
            )
            if best_ready > 0:
                return 5000.0 + best_ready + slot.current_hp * 0.01
            return float(slot.current_hp) + slot.max_hp * 0.01
        return max(legal_promotions, key=key)

    def choose_setup_placement(
        self, state: GameState, player_index: int, basics_in_hand: list[str],
    ) -> tuple[str, list[str]]:
        scored = sorted(
            basics_in_hand,
            key=lambda cid: _basic_setup_score(get_card(cid)),
            reverse=True,
        )
        return scored[0], scored[1:]

    # ------------------------------------------------------------------ #
    # Main scorer
    # ------------------------------------------------------------------ #

    def _score(self, state: GameState, action: Action) -> tuple[float, float]:
        kind = action.kind
        tb = state.rng.random()

        if kind == ActionKind.ATTACK:
            return (self._attack(state, action), tb)
        if kind == ActionKind.EVOLVE:
            return (self._evolve(state, action), tb)
        if kind == ActionKind.PLAY_CARD:
            return (self._play_card(state, action), tb)
        if kind == ActionKind.ATTACH_ENERGY:
            return (self._attach_energy(state, action), tb)
        if kind == ActionKind.USE_ABILITY:
            return (self._use_ability(state, action), tb)
        if kind == ActionKind.RETREAT:
            return (self._retreat(state, action), tb)
        return (1.0, tb)  # END_TURN

    # ------------------------------------------------------------------ #
    # ATTACK
    # ------------------------------------------------------------------ #

    def _attack(self, state: GameState, action: Action) -> float:
        attacker = state.current.active
        defender = state.opponent.active
        if attacker is None or defender is None or action.attack_index is None:
            return 0.0
        acard = get_card(attacker.card_id)
        if action.attack_index >= len(acard.attacks):
            return 0.0
        attack = acard.attacks[action.attack_index]
        dcard = get_card(defender.card_id)

        damage = attack.damage
        if acard.element and dcard.weakness == acard.element:
            damage += WEAKNESS_BONUS

        # Classify side effects: penalize costly ones, reward beneficial ones
        effect_names = {e.name for e in parse_effect_text(attack.effect_text)} if attack.effect_text else set()
        side_effect_mod = 0.0
        if "discard_energy_self" in effect_names:
            side_effect_mod -= 8.0
        if "discard_n_energy_self" in effect_names or "discard_all_energy_self" in effect_names:
            side_effect_mod -= 15.0
        # Reward attacks that generate tempo (energy accel, heal, poison)
        if "attach_energy_zone_self" in effect_names or "attach_energy_zone_bench" in effect_names:
            side_effect_mod += 15.0  # Leaf Supply / Stoke — attacks + accelerates
        if "heal_self" in effect_names:
            side_effect_mod += 10.0  # Giant Bloom — attacks + heals
        if "apply_poison" in effect_names or "apply_sleep" in effect_names:
            side_effect_mod += 8.0
        if "apply_paralysis" in effect_names:
            side_effect_mod += 12.0

        # KO detection — always the best move
        if damage > 0 and damage >= defender.current_hp:
            ko_points = dcard.ko_points
            return 200.0 + ko_points * 30 + side_effect_mod

        # Non-KO: score by proportion of defender's HP removed
        if defender.max_hp > 0:
            pct = damage / defender.max_hp
        else:
            pct = 0
        return 55.0 + pct * 50 + damage * 0.15 + side_effect_mod

    # ------------------------------------------------------------------ #
    # EVOLVE
    # ------------------------------------------------------------------ #

    def _evolve(self, state: GameState, action: Action) -> float:
        if action.hand_index is None or action.target is None:
            return 60.0
        player = state.current
        evo_card = get_card(player.hand[action.hand_index])

        # Stage 2 power spikes are huge — always evolve immediately
        stage_bonus = 15.0 if evo_card.stage == Stage.STAGE_2 else 5.0

        # Evolving the active is better — it's the one attacking
        pos_bonus = 8.0 if action.target.is_active() else 2.0

        # Prefer evolutions whose best attack does more damage
        max_dmg = max((a.damage for a in evo_card.attacks), default=0)

        # Check if evolving unlocks an attack the pre-evo can't use
        target_slot = get_slot(state, action.target)
        if target_slot is not None:
            old_card = get_card(target_slot.card_id)
            old_max = max((a.damage for a in old_card.attacks if can_pay_cost(target_slot, a.cost)), default=0)
            new_max = max((a.damage for a in evo_card.attacks if can_pay_cost(target_slot, a.cost)), default=0)
            if new_max > old_max:
                stage_bonus += 12.0  # unlocks better attack NOW

        return 65.0 + stage_bonus + pos_bonus + max_dmg * 0.1

    # ------------------------------------------------------------------ #
    # PLAY_CARD
    # ------------------------------------------------------------------ #

    def _play_card(self, state: GameState, action: Action) -> float:
        if action.hand_index is None:
            return 20.0
        player = state.current
        card = get_card(player.hand[action.hand_index])

        if card.kind == CardKind.POKEMON and card.stage == Stage.BASIC:
            return self._play_basic(state)
        if card.kind == CardKind.ITEM:
            return self._item(state, card, action)
        if card.kind == CardKind.SUPPORTER:
            return self._supporter(state, card)
        if card.kind == CardKind.TOOL:
            return self._tool(state, card, action.target)
        return 15.0

    def _play_basic(self, state: GameState) -> float:
        empty = sum(1 for s in state.current.bench if s is None)
        # Fill bench AGGRESSIVELY on turns 0-3; moderate after
        if state.turn_number <= 3:
            return 72.0 if empty >= 2 else 55.0
        if empty >= 2:
            return 55.0
        if empty == 1:
            return 32.0
        return 10.0

    def _item(self, state: GameState, card: Card, action: Action) -> float:
        effects = {e.name for e in parse_effect_text(card.trainer_effect_text)}

        # --- Rare Candy: treat like an evolve, but even higher priority ---
        if "rare_candy_evolve" in effects:
            if action.extra_hand_index is not None:
                evo_card = get_card(state.current.hand[action.extra_hand_index])
                max_dmg = max((a.damage for a in evo_card.attacks), default=0)
                pos = 10.0 if (action.target and action.target.is_active()) else 3.0
                return 90.0 + max_dmg * 0.1 + pos

        # --- Heal ---
        if "heal_target" in effects or "heal_grass_target" in effects:
            target = action.target
            if target is None:
                return 0.0
            slot = get_slot(state, target)
            if slot is None:
                return 0.0
            missing = slot.max_hp - slot.current_hp
            if missing <= 0:
                return 0.0
            # Saving a Pokemon from KO is very valuable
            opp_active = state.opponent.active
            if opp_active is not None and target.is_active():
                opp_card = get_card(opp_active.card_id)
                opp_dmg = max((a.damage for a in opp_card.attacks if can_pay_cost(opp_active, a.cost)), default=0)
                our_card = get_card(slot.card_id)
                if our_card.weakness and opp_card.element and our_card.weakness == opp_card.element:
                    opp_dmg += WEAKNESS_BONUS
                if opp_dmg >= slot.current_hp and opp_dmg < slot.current_hp + 20:
                    return 85.0  # Potion saves us from a KO!
            return 28.0 + min(20, missing) * 0.6

        # --- Poké Ball ---
        if "draw_basic_pokemon" in effects:
            empty = sum(1 for s in state.current.bench if s is None)
            return 28.0 + empty * 8.0

        # --- X Speed ---
        if "reduce_retreat_cost" in effects:
            return 15.0  # play only if we're about to retreat

        # --- Red Card ---
        if "opponent_shuffle_hand_draw" in effects:
            opp_hand = len(state.opponent.hand)
            if opp_hand >= 5:
                return 45.0  # disrupts a big hand
            return 18.0

        return 22.0

    def _supporter(self, state: GameState, card: Card) -> float:
        effects = {e.name for e in parse_effect_text(card.trainer_effect_text)}

        # --- Professor's Research: ALWAYS play first in the turn ---
        if "draw_cards" in effects:
            hand = len(state.current.hand)
            if hand <= 2:
                return 95.0  # nearly top priority
            if hand <= 4:
                return 78.0
            return 58.0

        # --- Erika: heal 50 from a Grass Pokemon ---
        if "heal_grass_target" in effects:
            damaged = _team_damage(state.current)
            if damaged >= 40:
                return 55.0
            if damaged > 0:
                return 35.0
            return 5.0

        # --- Sabrina: force switch ---
        if "switch_opponent_active" in effects:
            opp = state.opponent
            if opp.active is None:
                return 5.0
            opp_card = get_card(opp.active.card_id)
            # Great when opponent's active is fully powered
            opp_energy = opp.active.total_energy()
            if opp_energy >= 3:
                return 65.0
            if opp_card.is_ex:
                return 50.0
            return 25.0

        # --- Dawn: move energy to active ---
        if "move_bench_energy_to_active" in effects:
            active = state.current.active
            if active is None:
                return 5.0
            acard = get_card(active.card_id)
            # Great when it would unlock an attack
            for atk in acard.attacks:
                if not can_pay_cost(active, atk.cost):
                    # Simulate: would moving one energy help?
                    return 55.0
            return 15.0

        # --- Giovanni / Blaine damage boost ---
        if "supporter_damage_aura" in effects:
            active = state.current.active
            if active and any(can_pay_cost(active, a.cost) for a in get_card(active.card_id).attacks):
                return 70.0  # we can attack this turn with the boost!
            return 20.0

        return 35.0

    def _tool(self, state: GameState, card: Card, target: Optional[SlotRef]) -> float:
        if target is None:
            return 15.0
        slot = get_slot(state, target)
        if slot is None:
            return 0.0
        scard = get_card(slot.card_id)
        hp_score = slot.max_hp / 30.0
        ex_bonus = 15.0 if scard.is_ex else 0.0
        active_bonus = 8.0 if target.is_active() else 0.0
        return 38.0 + hp_score + ex_bonus + active_bonus

    # ------------------------------------------------------------------ #
    # ATTACH_ENERGY
    # ------------------------------------------------------------------ #

    def _attach_energy(self, state: GameState, action: Action) -> float:
        if action.target is None or state.current.energy_available is None:
            return 20.0
        target_slot = get_slot(state, action.target)
        if target_slot is None:
            return 0.0
        card = get_card(target_slot.card_id)
        if not card.attacks:
            return 5.0

        energy_type = state.current.energy_available
        defender = state.opponent.active

        # Check if this attach enables a KO this turn
        ko_bonus = 0.0
        if defender is not None and action.target.is_active():
            dcard = get_card(defender.card_id)
            for atk in card.attacks:
                if can_pay_cost(target_slot, atk.cost):
                    continue  # already payable
                missing = _missing_energy(target_slot, atk.cost, energy_type)
                if missing == 0:
                    dmg = atk.damage
                    if card.element and dcard.weakness == card.element:
                        dmg += WEAKNESS_BONUS
                    if dmg >= defender.current_hp:
                        ko_bonus = 80.0 + dcard.ko_points * 20
                        break

        if ko_bonus > 0:
            return 130.0 + ko_bonus  # almost as good as a KO itself

        progress = _attach_progress_value(target_slot, card, energy_type)
        if progress is None:
            return 8.0

        base = 22.0
        if action.target.is_active():
            base += 12.0
        base += target_slot.max_hp * 0.05
        return base + progress * 0.6

    # ------------------------------------------------------------------ #
    # USE_ABILITY
    # ------------------------------------------------------------------ #

    def _use_ability(self, state: GameState, action: Action) -> float:
        if action.target is None:
            return 15.0
        slot = get_slot(state, action.target)
        if slot is None:
            return 0.0
        card = get_card(slot.card_id)
        if card.ability is None:
            return 10.0

        effects = {e.name for e in parse_effect_text(card.ability.effect_text)}

        if "heal_all_own" in effects:
            per_mon = 20
            total = 0
            for s in state.players[action.target.player].all_pokemon():
                total += min(per_mon, s.max_hp - s.current_hp)
            if total == 0:
                return 3.0
            return 30.0 + min(total, 80) * 0.25  # max ~50

        if "apply_poison" in effects:
            opp = state.opponent.active
            if opp and StatusEffect.POISONED not in opp.status_effects:
                return 48.0  # free poison is great
            return 3.0

        if "switch_opponent_active" in effects:
            opp = state.opponent
            if opp.active and opp.active.total_energy() >= 2:
                return 45.0
            return 20.0

        if "bench_hit_opponent" in effects:
            return 42.0  # free 20 damage to any target

        if "attach_energy_zone_self" in effects:
            return 52.0  # free energy acceleration

        if "draw_cards" in effects or "draw_basic_pokemon" in effects:
            return 50.0

        if "look_top_of_deck" in effects:
            return 12.0

        return 25.0

    # ------------------------------------------------------------------ #
    # RETREAT
    # ------------------------------------------------------------------ #

    def _retreat(self, state: GameState, action: Action) -> float:
        if action.target is None:
            return 2.0
        active = state.current.active
        bench_slot = state.current.bench[action.target.slot]
        if active is None or bench_slot is None:
            return 2.0

        acard = get_card(active.card_id)
        bcard = get_card(bench_slot.card_id)
        defender = state.opponent.active

        active_can_attack = any(can_pay_cost(active, a.cost) for a in acard.attacks)
        bench_ready_dmg = max(
            (a.damage for a in bcard.attacks if can_pay_cost(bench_slot, a.cost)),
            default=0,
        )

        bad = {StatusEffect.CONFUSED, StatusEffect.ASLEEP, StatusEffect.PARALYZED}
        has_bad = bool(active.status_effects & bad)

        # Escape bad status with a ready bench attacker
        if has_bad and bench_ready_dmg > 0:
            return 75.0

        # Swap out a useless active for a ready bench attacker
        if not active_can_attack and bench_ready_dmg > 0:
            return 65.0

        # Save a wounded active from next KO
        if active.current_hp < 30 and bench_ready_dmg > 0:
            return 40.0

        # Swap to type advantage
        if defender is not None and bench_ready_dmg > 0:
            dcard = get_card(defender.card_id)
            if bcard.element and dcard.weakness == bcard.element:
                bench_dmg_with_weakness = bench_ready_dmg + WEAKNESS_BONUS
                active_best = max(
                    (a.damage for a in acard.attacks if can_pay_cost(active, a.cost)),
                    default=0,
                )
                if bench_dmg_with_weakness > active_best + 20:
                    return 58.0  # clear type advantage

        return 3.0


# ===================================================================== #
# Module-level helpers (shared or class-static)
# ===================================================================== #

def _team_damage(player: PlayerState) -> int:
    return sum(max(0, s.max_hp - s.current_hp) for s in player.all_pokemon())


def _basic_setup_score(card: Card) -> float:
    max_dmg = max((a.damage for a in card.attacks), default=0)
    return card.hp + max_dmg * 2 + (30 if card.is_ex else 0)


def _attach_progress_value(
    slot: PokemonSlot, card: Card, energy_type: Element,
) -> Optional[float]:
    best: Optional[float] = None
    for atk in card.attacks:
        if not atk.cost:
            continue
        if can_pay_cost(slot, atk.cost):
            continue
        missing = _missing_energy(slot, atk.cost, energy_type)
        if missing is None:
            continue
        value = atk.damage * max(0.0, 1.0 - missing * 0.3)
        if best is None or value > best:
            best = value
    return best


def _missing_energy(
    slot: PokemonSlot, cost: tuple, adding_type: Element,
) -> Optional[int]:
    energy: dict = {}
    for el, n in slot.attached_energy.items():
        energy[el] = n
    energy[adding_type] = energy.get(adding_type, 0) + 1

    typed_needed: dict[Element, int] = {}
    colorless_needed = 0
    for sym in cost:
        if sym == CostSymbol.COLORLESS:
            colorless_needed += 1
        else:
            el = sym.to_element()
            typed_needed[el] = typed_needed.get(el, 0) + 1

    missing_typed = 0
    for el, need in typed_needed.items():
        have = energy.get(el, 0)
        pay = min(have, need)
        energy[el] = have - pay
        missing_typed += need - pay

    remaining = sum(energy.values())
    missing_colorless = max(0, colorless_needed - remaining)
    missing_total = missing_typed + missing_colorless

    energy[adding_type] -= 1
    if energy[adding_type] == 0:
        del energy[adding_type]
    mt2 = 0
    for el, need in typed_needed.items():
        have = energy.get(el, 0)
        pay = min(have, need)
        energy[el] = have - pay
        mt2 += need - pay
    r2 = sum(energy.values())
    mc2 = max(0, colorless_needed - r2)
    if mt2 + mc2 == missing_total:
        return None
    return missing_total
