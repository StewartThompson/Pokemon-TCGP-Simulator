/// Legal action generation for the battle engine.
///
/// Ports `ptcgp/engine/legal_actions.py` to Rust.
use crate::actions::{Action, SlotRef};
use crate::card::{Card, CardDb};
use crate::effects::EffectKind;
use crate::state::{GameState, PokemonSlot};
use crate::types::{CardKind, CostSymbol, Element, GamePhase, Stage, StatusEffect};

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //

/// Check whether a slot's attached energy can pay the given cost.
///
/// CostSymbol::Colorless = any one energy.
/// Typed symbols must first be satisfied by that specific element; any
/// remaining typed requirement is a hard failure.
/// Colorless requirements are satisfied by whatever energy is left.
fn can_pay_cost(slot: &PokemonSlot, cost: &[CostSymbol]) -> bool {
    let mut remaining = slot.energy; // EnergyArray = [u8; 8]
    let mut colorless_needed: u8 = 0;
    for sym in cost {
        match sym.to_element() {
            None => colorless_needed += 1, // Colorless
            Some(el) => {
                let idx = el as usize;
                if remaining[idx] > 0 {
                    remaining[idx] -= 1;
                } else {
                    return false;
                }
            }
        }
    }
    let total: u8 = remaining.iter().sum();
    total >= colorless_needed
}

/// Check if the opponent's Active Pokemon has a passive ability whose text
/// blocks supporter cards (e.g. "can't use any supporter cards … active spot").
fn opponent_blocks_supporters(state: &GameState, db: &CardDb) -> bool {
    const BLOCK_TEXT: &str = "can't use any supporter cards";
    let opp = state.opponent();
    let slot = match opp.active.as_ref() {
        Some(s) => s,
        None => return false,
    };
    let card = db.get_by_idx(slot.card_idx);
    let ab = match card.ability.as_ref() {
        Some(a) => a,
        None => return false,
    };
    if ab.effect_text.is_empty() {
        return false;
    }
    let low = ab.effect_text.to_lowercase();
    low.contains(BLOCK_TEXT) && low.contains("active spot")
}

/// Enumerate legal Rare Candy plays for the current player.
///
/// For each Basic Pokemon in play that has been in play at least one turn
/// and hasn't evolved this turn, find every Stage 2 card in hand whose
/// evolution chain's Basic name matches.
fn rare_candy_actions(
    state: &GameState,
    db: &CardDb,
    rare_candy_hand_idx: usize,
) -> Vec<Action> {
    let cp = state.current_player;
    let player = state.current();
    let mut actions: Vec<Action> = Vec::new();

    // Turn restriction: same as regular evolve — no evolving on turn 0/1.
    if state.turn_number < 2 {
        return actions;
    }

    // Helper closure: check a single slot and append matching actions.
    let mut check_slot = |slot_ref: SlotRef| {
        let slot = match crate::state::get_slot(state, slot_ref) {
            Some(s) => s,
            None => return,
        };
        if slot.turns_in_play < 1 || slot.evolved_this_turn {
            return;
        }
        let basic_card = db.get_by_idx(slot.card_idx);
        if basic_card.stage != Some(Stage::Basic) {
            return;
        }
        let reachable = match db.basic_to_stage2.get(&basic_card.name) {
            Some(r) if !r.is_empty() => r,
            _ => return,
        };

        for (hidx, &card_idx) in player.hand.iter().enumerate() {
            if hidx == rare_candy_hand_idx {
                continue;
            }
            let hand_card = db.get_by_idx(card_idx);
            if hand_card.stage != Some(Stage::Stage2) {
                continue;
            }
            if reachable.contains(&hand_card.name) {
                actions.push(Action::play_rare_candy(rare_candy_hand_idx, slot_ref, hidx));
            }
        }
    };

    if player.active.is_some() {
        check_slot(SlotRef::active(cp));
    }
    for j in 0..3 {
        if player.bench[j].is_some() {
            check_slot(SlotRef::bench(cp, j));
        }
    }

    actions
}

// ------------------------------------------------------------------ //
// Supporter action generation
// ------------------------------------------------------------------ //

/// Build legal actions for a single supporter card.
///
/// Returns an empty Vec if the card has no usable effect given the current state.
/// Returns targeted actions (one per valid slot) for heal-type effects.
fn collect_supporter_actions(
    state: &GameState,
    db: &CardDb,
    cp: usize,
    hand_index: usize,
    card: &Card,
) -> Vec<Action> {
    if card.trainer_effects.is_empty() {
        return vec![];
    }

    let opp = 1 - cp;

    for effect in &card.trainer_effects {
        match effect {
            // --- Move energy from bench to active (Dawn) ---
            EffectKind::MoveBenchEnergyToActive => {
                // Only playable if active exists and at least one benched Pokemon
                // has energy to move.
                let active_exists = state.players[cp].active.is_some();
                let bench_has_energy = state.players[cp].bench.iter().flatten()
                    .any(|s| s.energy.iter().sum::<u8>() > 0);
                if !active_exists || !bench_has_energy {
                    return vec![];
                }
                return vec![Action::play_item(hand_index, None)];
            }

            // --- Switch opponent's active with bench ---
            EffectKind::SwitchOpponentActive
            | EffectKind::SwitchOpponentBasicToActive
            | EffectKind::CoinFlipBounceOpponent => {
                if !state.players[opp].bench.iter().any(|s| s.is_some()) {
                    return vec![];
                }
                return vec![Action::play_item(hand_index, None)];
            }

            EffectKind::SwitchOpponentDamagedToActive => {
                // Cyrus: emit one PlayCard per damaged opponent bench slot so
                // the agent (player) chooses which Pokemon to drag up.
                let mut out = Vec::new();
                for j in 0..3 {
                    if let Some(slot) = state.players[opp].bench[j].as_ref() {
                        if slot.current_hp < slot.max_hp {
                            out.push(Action::play_item(
                                hand_index,
                                Some(SlotRef::bench(opp, j)),
                            ));
                        }
                    }
                }
                return out;
            }

            // --- Misty: choose 1 of your Water Pokemon, then flip ---
            EffectKind::CoinFlipUntilTailsAttachEnergy => {
                let mut out = Vec::new();
                let is_water = |slot: &PokemonSlot| -> bool {
                    db.try_get_by_idx(slot.card_idx)
                        .map(|c| c.element == Some(Element::Water))
                        .unwrap_or(false)
                };
                if let Some(slot) = state.players[cp].active.as_ref() {
                    if is_water(slot) {
                        out.push(Action::play_item(hand_index, Some(SlotRef::active(cp))));
                    }
                }
                for j in 0..3 {
                    if let Some(slot) = state.players[cp].bench[j].as_ref() {
                        if is_water(slot) {
                            out.push(Action::play_item(hand_index, Some(SlotRef::bench(cp, j))));
                        }
                    }
                }
                return out;
            }

            // --- Heal target (any of own Pokemon) ---
            EffectKind::HealTarget { .. } | EffectKind::HealAndCureStatus { .. } => {
                return heal_target_actions(state, db, cp, hand_index, None, None);
            }

            // --- Heal own Grass Pokemon ---
            EffectKind::HealGrassTarget { .. } => {
                return heal_target_actions(state, db, cp, hand_index, Some(Element::Grass), None);
            }

            // --- Heal own Water Pokemon ---
            EffectKind::HealWaterPokemon { .. } => {
                return heal_target_actions(state, db, cp, hand_index, Some(Element::Water), None);
            }

            // --- Heal own Stage 2 Pokemon ---
            EffectKind::HealStage2Target { .. } => {
                return heal_target_actions(state, db, cp, hand_index, None, Some(Stage::Stage2));
            }

            // --- Heal all own Pokemon (Irida etc.) ---
            EffectKind::HealAllOwn { .. } => {
                let any_damaged = has_any_damaged(state, cp);
                if !any_damaged {
                    return vec![];
                }
                return vec![Action::play_item(hand_index, None)];
            }

            // --- Heal own active only ---
            EffectKind::HealActive { .. } | EffectKind::HealSelf { .. } => {
                if let Some(ref active) = state.players[cp].active {
                    if active.current_hp < active.max_hp {
                        return vec![Action::play_item(hand_index, None)];
                    }
                }
                return vec![];
            }

            _ => {} // Non-blocking effect; continue scanning
        }
    }

    // No blocking condition found — always playable.
    vec![Action::play_item(hand_index, None)]
}

/// Generate one play_item action per damaged own Pokémon that optionally matches
/// a required `element` type and/or `stage`.  Returns empty if no valid target.
fn heal_target_actions(
    state: &GameState,
    db: &CardDb,
    cp: usize,
    hand_index: usize,
    required_element: Option<Element>,
    required_stage: Option<Stage>,
) -> Vec<Action> {
    let player = &state.players[cp];
    let mut out = Vec::new();

    let slot_matches = |slot: &PokemonSlot| -> bool {
        if slot.current_hp >= slot.max_hp { return false; }
        let card = db.get_by_idx(slot.card_idx);
        if let Some(el) = required_element {
            if card.element != Some(el) { return false; }
        }
        if let Some(st) = required_stage {
            if card.stage != Some(st) { return false; }
        }
        true
    };

    if let Some(ref active) = player.active {
        if slot_matches(active) {
            out.push(Action::play_item(hand_index, Some(SlotRef::active(cp))));
        }
    }
    for j in 0..3 {
        if let Some(ref slot) = player.bench[j] {
            if slot_matches(slot) {
                out.push(Action::play_item(hand_index, Some(SlotRef::bench(cp, j))));
            }
        }
    }
    out
}

/// Returns true if any of the acting player's Pokemon has less than max HP.
fn has_any_damaged(state: &GameState, player_idx: usize) -> bool {
    let p = &state.players[player_idx];
    p.active.as_ref().map(|s| s.current_hp < s.max_hp).unwrap_or(false)
        || p.bench.iter().flatten().any(|s| s.current_hp < s.max_hp)
}

// ------------------------------------------------------------------ //
// Public API
// ------------------------------------------------------------------ //

/// Return all legal actions for the current player when phase == Main.
pub fn get_legal_actions(state: &GameState, db: &CardDb) -> Vec<Action> {
    if state.phase != GamePhase::Main || state.winner.is_some() {
        return vec![];
    }

    let mut actions: Vec<Action> = Vec::new();
    let cp = state.current_player;
    let player = state.current();

    // ------------------------------------------------------------------ //
    // PLAY_CARD
    // ------------------------------------------------------------------ //
    for (i, &card_idx) in player.hand.iter().enumerate() {
        let card = db.get_by_idx(card_idx);

        match card.kind {
            CardKind::Pokemon if card.stage == Some(Stage::Basic) => {
                // Play basic to each empty bench slot.
                for j in 0..3 {
                    if player.bench[j].is_none() {
                        actions.push(Action::play_basic(i, SlotRef::bench(cp, j)));
                    }
                }
            }

            CardKind::Item => {
                if player.cant_play_items_this_turn {
                    continue;
                }
                if card.name == "Rare Candy" {
                    for rc in rare_candy_actions(state, db, i) {
                        actions.push(rc);
                    }
                    // Skip the generic play_item path for Rare Candy.
                    continue;
                }

                // Heal-target items: generate one action per damaged own Pokemon.
                let needs_heal_target = card.trainer_effects.iter().any(|e| {
                    matches!(e, EffectKind::HealTarget { .. } | EffectKind::HealAndCureStatus { .. })
                });
                let needs_heal_active = !needs_heal_target && card.trainer_effects.iter().any(|e| {
                    matches!(e, EffectKind::HealActive { .. })
                });

                if needs_heal_target {
                    // Emit one play_item per damaged own Pokemon (active + bench).
                    if let Some(ref active) = player.active {
                        if active.current_hp < active.max_hp {
                            actions.push(Action::play_item(i, Some(SlotRef::active(cp))));
                        }
                    }
                    for j in 0..3 {
                        if let Some(ref slot) = player.bench[j] {
                            if slot.current_hp < slot.max_hp {
                                actions.push(Action::play_item(i, Some(SlotRef::bench(cp, j))));
                            }
                        }
                    }
                    // (no fallback action — can't use Potion if no Pokemon has damage)
                } else if needs_heal_active {
                    // Only usable if active is damaged.
                    if let Some(ref active) = player.active {
                        if active.current_hp < active.max_hp {
                            actions.push(Action::play_item(i, None));
                        }
                    }
                } else {
                    // Generic item with no targeting restriction.
                    actions.push(Action::play_item(i, None));
                }
            }

            CardKind::Supporter => {
                if player.has_played_supporter {
                    continue;
                }
                if player.cant_play_supporter_this_turn {
                    continue;
                }
                if opponent_blocks_supporters(state, db) {
                    continue;
                }
                // Generate targeted/validated actions for this supporter.
                let supporter_actions = collect_supporter_actions(state, db, cp, i, card);
                actions.extend(supporter_actions);
            }

            CardKind::Tool => {
                // Attach to active if it has no tool.
                if let Some(ref active) = player.active {
                    if active.tool_idx.is_none() {
                        actions.push(Action {
                            kind: crate::types::ActionKind::PlayCard,
                            hand_index: Some(i),
                            target: Some(SlotRef::active(cp)),
                            attack_index: None,
                            extra_hand_index: None,
                            extra_target: None,
                        });
                    }
                }
                // Attach to each bench Pokemon that has no tool.
                for j in 0..3 {
                    if let Some(ref slot) = player.bench[j] {
                        if slot.tool_idx.is_none() {
                            actions.push(Action {
                                kind: crate::types::ActionKind::PlayCard,
                                hand_index: Some(i),
                                target: Some(SlotRef::bench(cp, j)),
                                attack_index: None,
                                extra_hand_index: None,
                                extra_target: None,
                            });
                        }
                    }
                }
            }

            _ => {} // Stage 1 / Stage 2 Pokemon played via EVOLVE, not PLAY_CARD
        }
    }

    // ------------------------------------------------------------------ //
    // ATTACH_ENERGY
    // ------------------------------------------------------------------ //
    if player.energy_available.is_some() && !player.has_attached_energy
        && !player.cant_attach_energy_this_turn {
        if player.active.is_some() {
            actions.push(Action::attach_energy(SlotRef::active(cp)));
        }
        for j in 0..3 {
            if player.bench[j].is_some() {
                actions.push(Action::attach_energy(SlotRef::bench(cp, j)));
            }
        }
    }

    // ------------------------------------------------------------------ //
    // EVOLVE  (not on turn 0 or 1)
    // ------------------------------------------------------------------ //
    if state.turn_number >= 2 {
        // Snapshot hand to avoid re-borrow issues.
        let hand_snapshot: Vec<u16> = state.current().hand.clone();
        for (i, &card_idx) in hand_snapshot.iter().enumerate() {
            let evo_card = db.get_by_idx(card_idx);
            if evo_card.kind != CardKind::Pokemon {
                continue;
            }
            match evo_card.stage {
                Some(Stage::Stage1) | Some(Stage::Stage2) => {}
                _ => continue,
            }
            let evolves_from = match evo_card.evolves_from.as_deref() {
                Some(s) => s,
                None => continue,
            };

            let player = state.current();

            // Check active slot.
            if let Some(ref active) = player.active {
                let active_card = db.get_by_idx(active.card_idx);
                if active_card.name == evolves_from
                    && active.turns_in_play >= 1
                    && !active.evolved_this_turn
                {
                    actions.push(Action::evolve(i, SlotRef::active(cp)));
                }
            }

            // Check bench slots.
            for j in 0..3 {
                if let Some(ref slot) = player.bench[j] {
                    let slot_card = db.get_by_idx(slot.card_idx);
                    if slot_card.name == evolves_from
                        && slot.turns_in_play >= 1
                        && !slot.evolved_this_turn
                    {
                        actions.push(Action::evolve(i, SlotRef::bench(cp, j)));
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // USE_ABILITY
    // ------------------------------------------------------------------ //
    let player = state.current();
    if let Some(ref active) = player.active {
        let card = db.get_by_idx(active.card_idx);
        if let Some(ref ab) = card.ability {
            if !ab.is_passive && !active.ability_used_this_turn {
                actions.push(Action::use_ability(SlotRef::active(cp)));
            }
        }
    }
    for j in 0..3 {
        if let Some(ref slot) = player.bench[j] {
            let card = db.get_by_idx(slot.card_idx);
            if let Some(ref ab) = card.ability {
                if !ab.is_passive && !slot.ability_used_this_turn {
                    actions.push(Action::use_ability(SlotRef::bench(cp, j)));
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // RETREAT
    // ------------------------------------------------------------------ //
    let player = state.current();
    if !player.has_retreated {
        if let Some(ref active) = player.active {
            if !active.has_status(StatusEffect::Paralyzed)
                && !active.has_status(StatusEffect::Asleep)
                && !active.cant_retreat_next_turn
            {
                let active_card = db.get_by_idx(active.card_idx);
                // Sentinel: card.rs sets retreat_cost = u8::MAX for "can't retreat"
                // Pokémon (e.g. those with retreat cost > 4 in source data).
                if active_card.retreat_cost == u8::MAX {
                    // Skip emitting any retreat actions.
                } else {
                let base_cost = active_card.retreat_cost as i16;
                // Tool passive: check for retreat cost reduction (e.g. Inflatable Boat).
                let tool_reduction: i16 = active.tool_idx
                    .and_then(|tidx| db.try_get_by_idx(tidx))
                    .map(|tool| {
                        tool.trainer_effects.iter().find_map(|e| {
                            if let EffectKind::PassiveBenchRetreatReduction { amount } = e {
                                Some(*amount)
                            } else {
                                None
                            }
                        }).unwrap_or(0)
                    })
                    .unwrap_or(0);
                let effective_cost =
                    (base_cost + player.retreat_cost_modifier as i16 - tool_reduction).max(0) as u8;
                if active.total_energy() >= effective_cost {
                    // Must have at least one bench Pokemon to swap in.
                    for j in 0..3 {
                        if player.bench[j].is_some() {
                            actions.push(Action::retreat(SlotRef::bench(cp, j)));
                        }
                    }
                }
                } // end else (retreat_cost != u8::MAX)
            }
        }
    }

    // ------------------------------------------------------------------ //
    // ATTACK  (RULES.md §4: NEITHER player can attack on their first turn.
    // P1's first turn is turn_number == 0; P2's first turn is turn_number == 1.
    // Attacks are legal from turn 2 onward.)
    // ------------------------------------------------------------------ //
    if state.turn_number >= 2 {
        let player = state.current();
        if let Some(ref active) = player.active {
            if !active.cant_attack_next_turn
                && !active.has_status(StatusEffect::Paralyzed)
                && !active.has_status(StatusEffect::Asleep)
            {
                // Check if opponent's active has PassiveOpponentAttackCostIncrease
                // (e.g. Goomy's Sticky Membrane: opponent attacks cost +1 Colorless).
                let extra_colorless: u8 = {
                    let opp_idx = (1 - cp) as usize;
                    state.players[opp_idx].active.as_ref()
                        .and_then(|s| {
                            let card = db.get_by_idx(s.card_idx);
                            card.ability.as_ref().and_then(|ab| {
                                ab.effects.iter().find_map(|e| {
                                    if let EffectKind::PassiveOpponentAttackCostIncrease { amount } = e {
                                        Some(*amount as u8)
                                    } else {
                                        None
                                    }
                                })
                            })
                        })
                        .unwrap_or(0)
                };

                let active_card = db.get_by_idx(active.card_idx);
                for (i, attack) in active_card.attacks.iter().enumerate() {
                    let can_pay = if extra_colorless > 0 {
                        // Build augmented cost with extra Colorless symbols.
                        let mut augmented = attack.cost.clone();
                        for _ in 0..extra_colorless {
                            augmented.push(CostSymbol::Colorless);
                        }
                        can_pay_cost(active, &augmented)
                    } else {
                        can_pay_cost(active, &attack.cost)
                    };
                    if can_pay {
                        // Emit attack actions with player-choice targeting for
                        // effects that require the attacker to pick multiple
                        // own slots. Currently: Manaphy `attach_water_two_bench`.
                        let needs_two_bench = attack.effects.iter()
                            .any(|e| matches!(e, EffectKind::AttachWaterTwoBench));

                        if needs_two_bench {
                            // Emit one action per unordered pair of own bench slots.
                            let bench_indices: Vec<usize> = (0..3)
                                .filter(|&j| state.players[cp].bench[j].is_some())
                                .collect();
                            if bench_indices.len() >= 2 {
                                for a in 0..bench_indices.len() {
                                    for b in (a + 1)..bench_indices.len() {
                                        let sa = SlotRef::bench(cp, bench_indices[a]);
                                        let sb = SlotRef::bench(cp, bench_indices[b]);
                                        actions.push(Action::attack_two_targets(i, sa, sb));
                                    }
                                }
                            } else if bench_indices.len() == 1 {
                                // Fewer than 2 benched — emit one action with a single target;
                                // handler will only attach once.
                                let sa = SlotRef::bench(cp, bench_indices[0]);
                                actions.push(Action::attack(i, Some(sa)));
                            } else {
                                // No bench — still legal per PTCGP rules (attack fizzles).
                                actions.push(Action::attack(i, None));
                            }
                        } else {
                            // Default: single-target (or no-target) attack.
                            actions.push(Action::attack(i, None));
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ //
    // END_TURN — always available
    // ------------------------------------------------------------------ //
    actions.push(Action::end_turn());

    actions
}

/// Return PROMOTE actions for the given player during AwaitingBenchPromotion.
/// Returns one action per Basic Pokemon in the player's hand during setup.
///
/// Called during `GamePhase::Setup` so the agent can choose which Basic to place as active.
/// Each action's `hand_index` is the card's index in the player's hand.
pub fn get_legal_setup_placements(state: &GameState, db: &CardDb, player_index: usize) -> Vec<Action> {
    let player = &state.players[player_index];
    player
        .hand
        .iter()
        .enumerate()
        .filter_map(|(i, &card_idx)| {
            let card = db.get_by_idx(card_idx);
            if card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic) {
                // Use play_item constructor: PlayCard with a hand_index, no target
                Some(Action::play_item(i, None))
            } else {
                None
            }
        })
        .collect()
}

/// Return legal bench-placement actions during the Setup phase bench step.
///
/// Called after the player has already placed their Active Pokemon.
/// Returns one `play_basic` per (Basic in hand) × (empty bench slot), plus
/// `end_turn` as a "done / skip" option.  If no valid placements exist,
/// returns only `[end_turn]` so the runner can detect and break immediately.
pub fn get_legal_setup_bench_placements(state: &GameState, db: &CardDb, player_index: usize) -> Vec<Action> {
    let player = &state.players[player_index];
    let mut actions: Vec<Action> = Vec::new();

    for j in 0..3 {
        if player.bench[j].is_some() {
            continue; // slot occupied
        }
        for (i, &card_idx) in player.hand.iter().enumerate() {
            let card = db.get_by_idx(card_idx);
            if card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic) {
                actions.push(Action::play_basic(i, SlotRef::bench(player_index, j)));
            }
        }
    }

    // Always include "done" so the agent/runner can finish early.
    actions.push(Action::end_turn());
    actions
}

pub fn get_legal_promotions(state: &GameState, player_index: usize) -> Vec<Action> {
    if state.phase != GamePhase::AwaitingBenchPromotion {
        return vec![];
    }

    let player = &state.players[player_index];
    let mut actions: Vec<Action> = Vec::new();
    for j in 0..3 {
        if player.bench[j].is_some() {
            actions.push(Action::promote(SlotRef::bench(player_index, j)));
        }
    }
    actions
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, PokemonSlot};
    use crate::types::{ActionKind, GamePhase};

    fn minimal_state_main() -> GameState {
        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 3; // past the first-turn restriction
        // Give player 0 an active Pokemon (card_idx 0 -> no attacks in empty db,
        // but the slot is present so retreat / ability / attack paths are visited).
        state.players[0].active = Some(PokemonSlot::new(0, 100));
        state
    }

    #[test]
    fn end_turn_always_available() {
        // Build a minimal GameState with phase=Main and verify END_TURN is present.
        let state = minimal_state_main();
        let db = CardDb {
            cards: vec![crate::card::Card {
                id: "test-001".to_string(),
                idx: 0,
                name: "TestMon".to_string(),
                kind: CardKind::Pokemon,
                stage: Some(Stage::Basic),
                element: None,
                hp: 100,
                weakness: None,
                retreat_cost: 1,
                is_ex: false,
                is_mega_ex: false,
                evolves_from: None,
                attacks: vec![],
                ability: None,
                trainer_effect_text: String::new(),
                trainer_handler: String::new(),
                trainer_effects: vec![],
                ko_points: 1,
            }],
            id_to_idx: {
                let mut m = std::collections::HashMap::new();
                m.insert("test-001".to_string(), 0u16);
                m
            },
            name_to_indices: {
                let mut m = std::collections::HashMap::new();
                m.insert("TestMon".to_string(), vec![0u16]);
                m
            },
            basic_to_stage2: std::collections::HashMap::new(),
        };

        let actions = get_legal_actions(&state, &db);
        assert!(
            actions.iter().any(|a| a.kind == ActionKind::EndTurn),
            "END_TURN must always be in legal actions"
        );
    }

    #[test]
    fn no_actions_when_game_over() {
        let mut state = minimal_state_main();
        state.winner = Some(0);
        let db = CardDb {
            cards: vec![],
            id_to_idx: std::collections::HashMap::new(),
            name_to_indices: std::collections::HashMap::new(),
            basic_to_stage2: std::collections::HashMap::new(),
        };
        let actions = get_legal_actions(&state, &db);
        assert!(actions.is_empty(), "No actions when game is over");
    }

    #[test]
    fn no_actions_wrong_phase() {
        let mut state = minimal_state_main();
        state.phase = GamePhase::Setup;
        let db = CardDb {
            cards: vec![],
            id_to_idx: std::collections::HashMap::new(),
            name_to_indices: std::collections::HashMap::new(),
            basic_to_stage2: std::collections::HashMap::new(),
        };
        let actions = get_legal_actions(&state, &db);
        assert!(actions.is_empty(), "No actions outside Main phase");
    }

    #[test]
    fn promotions_returned_during_awaiting_promotion() {
        let mut state = GameState::new(0);
        state.phase = GamePhase::AwaitingBenchPromotion;
        state.players[0].bench[0] = Some(PokemonSlot::new(0, 80));
        state.players[0].bench[2] = Some(PokemonSlot::new(1, 60));

        let promotions = get_legal_promotions(&state, 0);
        assert_eq!(promotions.len(), 2);
        assert!(promotions.iter().all(|a| a.kind == ActionKind::Promote));
    }

    #[test]
    fn attach_energy_action_emitted() {
        let mut state = minimal_state_main();
        state.players[0].energy_available = Some(crate::types::Element::Fire);
        state.players[0].has_attached_energy = false;

        let db = CardDb {
            cards: vec![crate::card::Card {
                id: "test-001".to_string(),
                idx: 0,
                name: "TestMon".to_string(),
                kind: CardKind::Pokemon,
                stage: Some(Stage::Basic),
                element: None,
                hp: 100,
                weakness: None,
                retreat_cost: 0,
                is_ex: false,
                is_mega_ex: false,
                evolves_from: None,
                attacks: vec![],
                ability: None,
                trainer_effect_text: String::new(),
                trainer_handler: String::new(),
                trainer_effects: vec![],
                ko_points: 1,
            }],
            id_to_idx: {
                let mut m = std::collections::HashMap::new();
                m.insert("test-001".to_string(), 0u16);
                m
            },
            name_to_indices: {
                let mut m = std::collections::HashMap::new();
                m.insert("TestMon".to_string(), vec![0u16]);
                m
            },
            basic_to_stage2: std::collections::HashMap::new(),
        };

        let actions = get_legal_actions(&state, &db);
        let attach_count = actions
            .iter()
            .filter(|a| a.kind == ActionKind::AttachEnergy)
            .count();
        assert_eq!(attach_count, 1, "One ATTACH_ENERGY action for active slot");
    }

    // -------------------------- Player-choice plumbing --------------------------

    fn assets_dir() -> std::path::PathBuf {
        let mut d = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    #[test]
    fn cyrus_emits_one_action_per_damaged_opponent_bench() {
        let db = CardDb::load_from_dir(&assets_dir());
        let cyrus = db.get_by_id("a2-150").or_else(|| db.get_by_id("a2-185"))
            .expect("Cyrus card not found");
        let manaphy = db.get_by_id("a2-050").expect("Manaphy not found");

        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 3;
        state.current_player = 0;

        // P0 active to satisfy basic invariants.
        let mp_card = manaphy.clone();
        state.players[0].active = Some(PokemonSlot::new(mp_card.idx, mp_card.hp));
        state.players[0].hand.push(cyrus.idx);

        // Opponent: active + 2 bench, only one damaged.
        let opp_active = manaphy.clone();
        state.players[1].active = Some(PokemonSlot::new(opp_active.idx, opp_active.hp));
        let healthy = PokemonSlot::new(opp_active.idx, opp_active.hp);
        let mut damaged = PokemonSlot::new(opp_active.idx, opp_active.hp);
        damaged.current_hp = 30; // < max → damaged
        state.players[1].bench[0] = Some(healthy);
        state.players[1].bench[1] = Some(damaged);

        let actions = get_legal_actions(&state, &db);
        let cyrus_actions: Vec<&Action> = actions.iter()
            .filter(|a| a.kind == ActionKind::PlayCard
                     && a.hand_index == Some(0))
            .collect();
        assert_eq!(cyrus_actions.len(), 1,
            "Cyrus should emit exactly one PlayCard for the single damaged bench slot");
        let chosen = cyrus_actions[0].target.expect("Cyrus action must carry a target");
        assert!(chosen.is_bench(), "Cyrus target must be a bench slot");
        assert_eq!(chosen.player, 1, "Cyrus targets opponent");
        assert_eq!(chosen.bench_index(), 1, "Cyrus targets the damaged bench[1]");
    }

    #[test]
    fn misty_emits_one_action_per_water_pokemon() {
        let db = CardDb::load_from_dir(&assets_dir());
        let misty = db.get_by_id("a1-220").expect("Misty (a1-220) not found");
        let squirtle = db.get_by_id("a1-053").expect("Squirtle (a1-053) not found");
        let bulb = db.get_by_id("a1-001").expect("Bulbasaur (a1-001) not found");

        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 3;
        state.current_player = 0;

        // Active = Squirtle (Water); bench[0] = Bulbasaur (Grass); bench[1] = Squirtle (Water)
        state.players[0].active = Some(PokemonSlot::new(squirtle.idx, squirtle.hp));
        state.players[0].bench[0] = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].bench[1] = Some(PokemonSlot::new(squirtle.idx, squirtle.hp));
        state.players[0].hand.push(misty.idx);

        // Need an opponent active so the game state is valid.
        state.players[1].active = Some(PokemonSlot::new(bulb.idx, bulb.hp));

        let actions = get_legal_actions(&state, &db);
        let misty_targets: Vec<crate::actions::SlotRef> = actions.iter()
            .filter(|a| a.kind == ActionKind::PlayCard && a.hand_index == Some(0))
            .filter_map(|a| a.target)
            .collect();

        // Should emit 2 actions: one for active Squirtle, one for bench[1] Squirtle.
        // Bulbasaur on bench[0] should be excluded.
        assert_eq!(misty_targets.len(), 2,
            "Misty should emit one PlayCard per own Water Pokémon (got {:?})", misty_targets);
        assert!(misty_targets.iter().any(|t| t.is_active()),
            "Misty should include the active Water target");
        assert!(misty_targets.iter().any(|t| t.is_bench() && t.bench_index() == 1),
            "Misty should include bench[1] Water target");
        assert!(!misty_targets.iter().any(|t| t.is_bench() && t.bench_index() == 0),
            "Misty must NOT include bench[0] (Grass)");
    }

    #[test]
    fn manaphy_attack_emits_one_action_per_bench_pair() {
        let db = CardDb::load_from_dir(&assets_dir());
        let manaphy = db.get_by_id("a2-050").expect("Manaphy not found");
        let bulb = db.get_by_id("a1-001").expect("Bulbasaur not found");

        let mut state = GameState::new(0);
        state.phase = GamePhase::Main;
        state.turn_number = 3;
        state.current_player = 0;

        // Active is Manaphy with paid energy cost.
        let mut active = PokemonSlot::new(manaphy.idx, manaphy.hp);
        active.add_energy(Element::Water, 1);
        state.players[0].active = Some(active);

        // Three bench slots occupied → C(3,2) = 3 unordered pairs.
        state.players[0].bench[0] = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].bench[1] = Some(PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].bench[2] = Some(PokemonSlot::new(bulb.idx, bulb.hp));

        // Need an opponent active.
        state.players[1].active = Some(PokemonSlot::new(bulb.idx, bulb.hp));

        let actions = get_legal_actions(&state, &db);
        let manaphy_attacks: Vec<&Action> = actions.iter()
            .filter(|a| a.kind == ActionKind::Attack
                     && a.target.map(|t| t.is_bench()).unwrap_or(false)
                     && a.extra_target.is_some())
            .collect();
        assert_eq!(manaphy_attacks.len(), 3,
            "Should emit C(3,2)=3 unordered pairs (got {})", manaphy_attacks.len());
        // Verify the three unique pairs are {0,1}, {0,2}, {1,2}.
        let mut pairs: Vec<(usize, usize)> = manaphy_attacks.iter()
            .map(|a| {
                let a0 = a.target.unwrap().bench_index();
                let a1 = a.extra_target.unwrap().bench_index();
                if a0 < a1 { (a0, a1) } else { (a1, a0) }
            })
            .collect();
        pairs.sort();
        assert_eq!(pairs, vec![(0,1), (0,2), (1,2)]);
    }

    #[test]
    fn can_pay_cost_typed_and_colorless() {
        let mut slot = PokemonSlot::new(0, 100);
        // 2 Fire attached
        slot.add_energy(crate::types::Element::Fire, 2);

        // Cost: [Fire, Colorless] — should pass (2 fire satisfies both)
        assert!(can_pay_cost(&slot, &[CostSymbol::Fire, CostSymbol::Colorless]));

        // Cost: [Fire, Fire, Colorless] — fail (only 2 fire, 2 typed + 1 colorless needs 3)
        assert!(!can_pay_cost(
            &slot,
            &[CostSymbol::Fire, CostSymbol::Fire, CostSymbol::Colorless]
        ));

        // Cost: [Water] — fail (no water)
        assert!(!can_pay_cost(&slot, &[CostSymbol::Water]));
    }
}
