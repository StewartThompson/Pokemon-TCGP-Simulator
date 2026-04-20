// Agent trait, RandomAgent, HeuristicAgent, HumanAgent
// Implemented in Wave 8 (T22), HumanAgent added in Rust migration

pub mod human;

use crate::card::CardDb;
use crate::state::GameState;
use crate::actions::Action;
use crate::types::{ActionKind, GamePhase};
use crate::engine::legal_actions::{get_legal_actions, get_legal_promotions, get_legal_setup_placements, get_legal_setup_bench_placements};
use crate::effects::EffectKind;

// ------------------------------------------------------------------ //
// Agent trait
// ------------------------------------------------------------------ //

/// Trait that all battle agents implement.
pub trait Agent: Send + Sync {
    /// Select an action given the current game state.
    /// `player_idx` is the agent's player index (0 or 1).
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action;
}

// ------------------------------------------------------------------ //
// RandomAgent
// ------------------------------------------------------------------ //

/// Selects a uniformly random legal action.
pub struct RandomAgent;

impl Agent for RandomAgent {
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action {
        use rand::Rng;
        use rand::SeedableRng;
        use rand::rngs::SmallRng;

        let actions = match state.phase {
            GamePhase::Setup => {
                // If active is already placed, we're in bench-placement sub-phase.
                if state.players[player_idx].active.is_some() {
                    get_legal_setup_bench_placements(state, db, player_idx)
                } else {
                    get_legal_setup_placements(state, db, player_idx)
                }
            }
            GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
            _ => get_legal_actions(state, db),
        };

        if actions.is_empty() {
            return Action::end_turn();
        }

        // The Agent trait gives us &GameState, so we can't mutate state.rng.
        // Build a per-decision seed that incorporates as much state as possible
        // so the agent doesn't pick the same action repeatedly within a turn —
        // notably hand/deck/discard sizes change with each card play, so the
        // seed shifts as the agent acts.
        //
        // Limitation: this is still deterministic given identical state, and
        // distinct decision points that happen to share the same hand/deck/
        // discard sizes will see the same "random" choice. For unbiased play
        // the trait needs &mut GameState (or an &mut Rng parameter) so we can
        // pull from state.rng directly.
        let p0 = &state.players[0];
        let p1 = &state.players[1];
        let seed = (state.turn_number as u64)
            ^ ((player_idx as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15))
            ^ ((state.current_player as u64) << 1)
            ^ ((p0.hand.len() as u64) << 8)
            ^ ((p1.hand.len() as u64) << 16)
            ^ ((p0.deck.len() as u64) << 24)
            ^ ((p1.deck.len() as u64) << 32)
            ^ ((p0.discard.len() as u64) << 40)
            ^ ((p1.discard.len() as u64) << 48)
            ^ ((actions.len() as u64) << 56);
        let mut rng = SmallRng::seed_from_u64(seed);
        let idx = rng.gen_range(0..actions.len());
        actions.into_iter().nth(idx).unwrap_or_else(Action::end_turn)
    }
}

// ------------------------------------------------------------------ //
// HeuristicAgent
// ------------------------------------------------------------------ //

/// Selects actions using a priority-based scoring heuristic.
///
/// Priority order (highest → lowest):
///   1. Attack that KOs the opponent
///   2. Attack for maximum damage
///   3. Evolve an active/bench Pokemon
///   4. Play Basic Pokemon to bench
///   5. Attach energy
///   6. Use ability
///   7. Play item / supporter
///   8. Retreat (only if beneficial)
///   9. END_TURN
pub struct HeuristicAgent;

impl Agent for HeuristicAgent {
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action {
        let actions = match state.phase {
            GamePhase::Setup => {
                // Bench-placement sub-phase: always place if possible.
                if state.players[player_idx].active.is_some() {
                    let opts = get_legal_setup_bench_placements(state, db, player_idx);
                    // If only EndTurn remains, pass immediately.
                    if opts.len() <= 1 { return Action::end_turn(); }
                    // Otherwise always place (skip EndTurn at end of list).
                    let non_pass: Vec<Action> = opts.into_iter()
                        .filter(|a| a.kind != crate::types::ActionKind::EndTurn)
                        .collect();
                    if non_pass.is_empty() { return Action::end_turn(); }
                    return non_pass[0].clone();
                }
                get_legal_setup_placements(state, db, player_idx)
            }
            GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
            _ => get_legal_actions(state, db),
        };

        if actions.is_empty() {
            return Action::end_turn();
        }

        select_heuristic_action(state, db, player_idx, &actions)
    }
}

// ------------------------------------------------------------------ //
// Heuristic helpers
// ------------------------------------------------------------------ //

/// Count the acting player's Basic Pokémon currently in play (active + bench).
/// Used to gate Starting Plains-style board-wide HP buffs.
fn count_basics_in_play(state: &GameState, db: &CardDb, player_idx: usize) -> usize {
    let p = &state.players[player_idx];
    let is_basic = |idx: u16| {
        db.try_get_by_idx(idx)
            .map(|c| c.stage == Some(crate::types::Stage::Basic))
            .unwrap_or(false)
    };
    let mut n = 0;
    if let Some(a) = p.active.as_ref() {
        if is_basic(a.card_idx) { n += 1; }
    }
    for b in &p.bench {
        if let Some(s) = b.as_ref() {
            if is_basic(s.card_idx) { n += 1; }
        }
    }
    n
}

/// Returns true when the current active is in a bad spot (likely KO'd next
/// turn OR stuck with no energy and the bench has a better ready attacker).
/// Used to score X Speed, which is only worth playing when we actually
/// want to retreat this turn.
fn should_retreat_now(state: &GameState, db: &CardDb, player_idx: usize) -> bool {
    let player = &state.players[player_idx];
    let active = match player.active.as_ref() { Some(s) => s, None => return false };
    let active_card = db.get_by_idx(active.card_idx);
    let opp_idx = 1 - player_idx;

    // Threatened by opponent's best attack (counting weakness)
    let threatened = state.players[opp_idx].active.as_ref().map(|opp| {
        let opp_card = db.get_by_idx(opp.card_idx);
        let opp_dmg = opp_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
        let with_weak = if crate::constants::is_weak_to(active_card.weakness, opp_card.element) {
            opp_dmg + crate::constants::WEAKNESS_BONUS
        } else {
            opp_dmg
        };
        active.current_hp <= with_weak
    }).unwrap_or(false);

    // Bench has a ready attacker
    let bench_ready = player.bench.iter().any(|bs| {
        bs.as_ref().map(|b| {
            let c = db.get_by_idx(b.card_idx);
            let cost = c.attacks.iter()
                .max_by_key(|a| a.damage)
                .map(|a| a.cost.len() as u8)
                .unwrap_or(0);
            cost > 0 && b.total_energy() >= cost
        }).unwrap_or(false)
    });

    threatened && bench_ready
}

/// Estimate the opponent's best damage to the given slot next turn.
/// Factors weakness and the defender's incoming_damage_reduction.  Used by
/// `heal_benefit_score` to decide whether a heal will actually extend the
/// Pokémon's life by an extra turn.
fn opponent_expected_damage_to(
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
    slot: &crate::state::PokemonSlot,
) -> i16 {
    let opp_idx = 1 - player_idx;
    let opp_active = match state.players[opp_idx].active.as_ref() {
        Some(s) => s,
        None => return 0,
    };
    let opp_card = db.get_by_idx(opp_active.card_idx);
    let slot_card = db.get_by_idx(slot.card_idx);
    let raw = opp_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
    let with_weak = if crate::constants::is_weak_to(slot_card.weakness, opp_card.element) {
        raw + crate::constants::WEAKNESS_BONUS
    } else {
        raw
    };
    (with_weak - slot.incoming_damage_reduction as i16).max(0)
}

/// Score the value of healing `heal_amount` HP on `slot`.
/// Factors:
///   - How much of the heal is actually used (damage-capped; heal on a
///     Pokémon with 10 damage wastes 40/50 if heal is 50).
///   - Whether the heal lets the Pokémon survive an extra turn of opponent
///     pressure (the biggest payoff — a KO'd ally is a wasted heal).
///   - Survival futility: if opponent can KO even after the heal, the heal
///     is mostly wasted (we score it low).
fn heal_benefit_score(
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
    slot: &crate::state::PokemonSlot,
    heal_amount: i16,
) -> f32 {
    let damage_taken = slot.max_hp - slot.current_hp;
    if damage_taken <= 0 { return 0.0; } // already full — useless
    let actual_heal = heal_amount.min(damage_taken) as f32;
    // Base value proportional to actual healing.
    let mut score = actual_heal * 0.6;

    let opp_dmg = opponent_expected_damage_to(state, db, player_idx, slot);
    let current_hp = slot.current_hp;
    let hp_after_heal = (current_hp + heal_amount).min(slot.max_hp);

    let dies_without_heal = opp_dmg >= current_hp;
    let survives_with_heal = opp_dmg < hp_after_heal;

    if dies_without_heal && survives_with_heal {
        // Huge payoff: heal saves the Pokémon from KO next turn.
        score += 55.0;
    } else if dies_without_heal && !survives_with_heal {
        // Futile heal — opponent KOs anyway.  Lightly penalise so we don't
        // waste the card on a doomed Pokémon.
        score -= 15.0;
    } else if !dies_without_heal && survives_with_heal {
        // Over-provisioning: the Pokémon was going to survive anyway.
        // Small bonus (more durability for future turns) but not huge.
        score += 4.0;
    }
    score
}

/// Score an action numerically. Higher is better.
fn score_action(state: &GameState, db: &CardDb, player_idx: usize, action: &Action) -> f32 {
    let opp_idx = 1 - player_idx;
    let player = &state.players[player_idx];

    match action.kind {
        ActionKind::Attack => {
            let attack_idx = match action.attack_index {
                Some(i) => i,
                None => return 0.0,
            };
            let dmg = estimate_damage(state, db, player_idx, attack_idx);
            let opp_active = match state.players[opp_idx].active.as_ref() {
                Some(s) => s,
                None => return 0.0,
            };
            let opp_card = db.get_by_idx(opp_active.card_idx);

            // Check if this attack has a bench-only damage component (e.g. Decidueye ex Pierce the Pain)
            let active_card = db.get_by_idx(player.active.as_ref().map(|s| s.card_idx).unwrap_or(0));
            let is_bench_only_attack = attack_idx < active_card.attacks.len() && {
                let atk = &active_card.attacks[attack_idx];
                atk.damage == 0 && atk.effects.iter().any(|e| matches!(e, EffectKind::BenchHitOpponent { .. }))
            };

            // Dialga ex "Metallic Turbo" style: attack that also attaches
            // N energy to a chosen bench Pokémon.  Score the bench choice
            // so we attach to the slot that most benefits.
            let attach_n_bench_info = attack_idx < active_card.attacks.len() && {
                active_card.attacks[attack_idx].effects.iter()
                    .any(|e| matches!(e, EffectKind::AttachNEnergyZoneBench { .. }))
            };
            if attach_n_bench_info {
                // Extract attach count from the effect (default 1)
                let attach_count: u8 = active_card.attacks[attack_idx].effects.iter()
                    .find_map(|e| match e {
                        EffectKind::AttachNEnergyZoneBench { count, .. } => Some(*count),
                        _ => None,
                    }).unwrap_or(1);
                let score_bench = |t: Option<crate::actions::SlotRef>| -> f32 {
                    let t = match t { Some(x) => x, None => return 0.0 };
                    let slot = match crate::state::get_slot(state, t) { Some(s) => s, None => return 0.0 };
                    let c = db.get_by_idx(slot.card_idx);
                    let max_cost = c.attacks.iter().map(|a| a.cost.len()).max().unwrap_or(0) as i16;
                    let have = slot.total_energy() as i16;
                    let missing = (max_cost - have).max(0);
                    // Bigger payoff when this attach moves the slot to attack-ready.
                    match (missing, attach_count) {
                        (0, _) => 0.0,                    // already fully paid
                        (m, n) if (n as i16) >= m => 35.0, // makes it attack-ready
                        (m, n) => 14.0 + ((n as i16).min(m)) as f32 * 4.0,
                    }
                };
                // Base = regular attack scoring (damage/KO) + the bench pay-off.
                let base_attack_score = {
                    let remaining_after = opp_active.current_hp.saturating_sub(dmg);
                    if dmg > 0 && dmg >= opp_active.current_hp {
                        200.0 + opp_card.ko_points as f32 * 30.0
                    } else if remaining_after <= 30 {
                        175.0
                    } else {
                        85.0 + dmg as f32 * 0.15
                    }
                };
                return base_attack_score + score_bench(action.target);
            }

            // Manaphy-style "attach 1 Water energy to 2 chosen own bench slots."
            // The agent picks a pair via (action.target, action.extra_target).
            // Score by how much each chosen slot benefits from the attach.
            let is_two_bench_attach = attack_idx < active_card.attacks.len() && {
                active_card.attacks[attack_idx].effects.iter()
                    .any(|e| matches!(e, EffectKind::AttachWaterTwoBench))
            };
            if is_two_bench_attach {
                let score_target = |t: Option<crate::actions::SlotRef>| -> f32 {
                    let t = match t { Some(x) => x, None => return 0.0 };
                    let slot = match crate::state::get_slot(state, t) { Some(s) => s, None => return 0.0 };
                    let c = db.get_by_idx(slot.card_idx);
                    let max_cost = c.attacks.iter().map(|a| a.cost.len()).max().unwrap_or(0) as i16;
                    let have = slot.total_energy() as i16;
                    let missing = (max_cost - have).max(0);
                    match missing {
                        0 => 5.0,    // already paid up — wasted attach
                        1 => 30.0,   // moves bench Pokemon to attack-ready
                        2 => 22.0,
                        _ => 14.0,
                    }
                };
                let s_a = score_target(action.target);
                let s_b = score_target(action.extra_target);
                // Base 60 (modest because no damage) plus per-attached-slot value.
                return 60.0 + s_a + s_b;
            }

            if is_bench_only_attack {
                // For bench-targeting attacks, evaluate against the weakest bench target
                let bench_ko = state.players[opp_idx].bench.iter().any(|bs| {
                    bs.as_ref().map(|s| s.current_hp <= dmg).unwrap_or(false)
                });
                let weakest_bench_hp = state.players[opp_idx].bench.iter()
                    .filter_map(|bs| bs.as_ref().map(|s| s.current_hp))
                    .min()
                    .unwrap_or(999);
                if bench_ko {
                    // KOs a bench target — very strong
                    return 195.0;
                }
                if weakest_bench_hp < 999 {
                    // Damages a bench target — score by how close to KO
                    let remaining = (weakest_bench_hp - dmg).max(0);
                    if remaining <= 30 { return 170.0; }
                    return 90.0 + dmg as f32 * 0.15;
                }
                // No bench targets — worthless
                return 5.0;
            }

            // Instant KO
            if dmg > 0 && dmg >= opp_active.current_hp {
                return 200.0 + opp_card.ko_points as f32 * 30.0;
            }

            // Near-KO (setup for next turn KO)
            let remaining_after = opp_active.current_hp.saturating_sub(dmg);
            if remaining_after <= 30 {
                return 175.0;
            }

            // Normal attack: base 85 + damage fraction + absolute damage
            let pct = if opp_active.max_hp > 0 {
                dmg as f32 / opp_active.max_hp as f32
            } else {
                0.0
            };
            85.0 + pct * 40.0 + dmg as f32 * 0.12
        }

        ActionKind::Evolve => {
            // Evolving is high priority (65+) so it happens before attacking
            if let (Some(hidx), Some(target)) = (action.hand_index, action.target) {
                let evo_card = db.get_by_idx(player.hand[hidx]);
                let stage_bonus = match evo_card.stage {
                    Some(crate::types::Stage::Stage2) => 15.0,
                    _ => 5.0,
                };
                let pos_bonus = if target.is_active() { 8.0 } else { 2.0 };
                let max_dmg = evo_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                // Readiness bonus: how close is the evolved form to attacking?
                let best_cost = evo_card.attacks.iter()
                    .max_by_key(|a| a.damage)
                    .map(|a| a.cost.len() as i16)
                    .unwrap_or(0);
                let current_slot = crate::state::get_slot(state, target);
                let current_energy = current_slot.map(|s| s.total_energy() as i16).unwrap_or(0);
                let missing = (best_cost - current_energy).max(0);
                let readiness_bonus = match missing {
                    0 | 1 => 10.0,
                    2 => 5.0,
                    _ => 0.0,
                };
                65.0 + stage_bonus + pos_bonus + max_dmg as f32 * 0.1 + readiness_bonus
            } else {
                65.0
            }
        }

        ActionKind::PlayCard => {
            if let Some(hidx) = action.hand_index {
                let card = db.get_by_idx(player.hand[hidx]);
                match card.kind {
                    crate::types::CardKind::Pokemon if card.stage == Some(crate::types::Stage::Basic) => {
                        let empty = player.bench.iter().filter(|s| s.is_none()).count();
                        // Place bench Pokemon based on turn and bench fill
                        if state.turn_number <= 2 {
                            return if empty >= 2 { 60.0 } else { 45.0 };
                        }
                        return match empty {
                            e if e >= 2 => 48.0,
                            1 => 30.0,
                            _ => 8.0,
                        };
                    }
                    crate::types::CardKind::Supporter => {
                        // Giovanni: score higher so AI plays it before attacking
                        if card.name == "Giovanni" {
                            return 92.0;
                        }
                        // Dawn: move a bench Pokemon's energy to the active.
                        // Most valuable when the active is one energy short of attacking
                        // OR when the active discarded energy (Lycanroc ex Lycanfang).
                        if card.name == "Dawn" {
                            let active = player.active.as_ref();
                            let has_bench_energy = player.bench.iter().any(|bs| {
                                bs.as_ref().map(|s| s.total_energy() > 0).unwrap_or(false)
                            });
                            if !has_bench_energy { return 5.0; }
                            if let Some(active_slot) = active {
                                let active_card = db.get_by_idx(active_slot.card_idx);
                                let best_cost = active_card.attacks.iter()
                                    .max_by_key(|a| a.damage)
                                    .map(|a| a.cost.len() as i16).unwrap_or(0);
                                let missing = (best_cost - active_slot.total_energy() as i16).max(0);
                                // Very useful when 1 energy short (can attack this turn after Dawn)
                                return match missing {
                                    1 => 90.0,  // moves us to attacking this turn!
                                    2 => 55.0,
                                    _ => 30.0,
                                };
                            }
                            return 30.0;
                        }
                        // Sabrina: pull opponent bench to active.
                        // Useful when opponent has a damaged/weak bench Pokemon.
                        if card.name == "Sabrina" {
                            let opp = 1 - player_idx;
                            let opp_active_hp = state.players[opp].active.as_ref().map(|s| s.current_hp).unwrap_or(999);
                            // If opponent active is healthy, check if a bench target is weaker
                            let weakest_bench_hp = state.players[opp].bench.iter()
                                .filter_map(|bs| bs.as_ref().map(|s| s.current_hp))
                                .min()
                                .unwrap_or(999);
                            let best_target_hp = opp_active_hp.min(weakest_bench_hp);
                            // Score higher when we can pull a low-HP bench target
                            if weakest_bench_hp < opp_active_hp && weakest_bench_hp <= 80 {
                                return 70.0 + (100 - best_target_hp.min(100)) as f32 * 0.3;
                            }
                            return 38.0;
                        }
                        // Cyrus: legal_actions emits one action per damaged
                        // opponent bench slot (target = that bench). Score the
                        // chosen target by how much closer the active KO is.
                        if card.name == "Cyrus" {
                            if let Some(t) = action.target {
                                let opp = t.player as usize;
                                if t.is_bench() {
                                    if let Some(slot) = state.players[opp].bench[t.bench_index()].as_ref() {
                                        let damage = (slot.max_hp - slot.current_hp).max(0) as f32;
                                        let close_to_ko = (slot.current_hp <= 40) as i32 as f32;
                                        // Higher = drag a Pokemon close to KO into the active spot.
                                        return 55.0 + damage * 0.2 + close_to_ko * 25.0;
                                    }
                                }
                            }
                            return 35.0;
                        }
                        // Misty: legal_actions emits one action per own Water
                        // Pokemon (target = that slot). Prefer attaching to a
                        // Pokemon close to its highest-cost attack threshold.
                        if card.name == "Misty" {
                            if let Some(t) = action.target {
                                if let Some(slot) = crate::state::get_slot(state, t) {
                                    let c = db.get_by_idx(slot.card_idx);
                                    let max_cost = c.attacks.iter()
                                        .map(|a| a.cost.len())
                                        .max()
                                        .unwrap_or(0) as i16;
                                    let have = slot.total_energy() as i16;
                                    let missing = (max_cost - have).max(0);
                                    // Big payoff when missing 1-2 energy.
                                    return match missing {
                                        1 => 65.0,
                                        2 => 55.0,
                                        3 => 45.0,
                                        _ => 35.0,
                                    };
                                }
                            }
                            return 35.0;
                        }
                        // Professor's Research: always useful
                        if card.name == "Professor's Research" {
                            return 45.0;
                        }
                        // Red: +20 damage vs ex next attack.  Peers with Giovanni —
                        // score very high when opponent is ex, else modest.
                        if card.name == "Red" {
                            let opp = 1 - player_idx;
                            let opp_is_ex = state.players[opp].active.as_ref()
                                .map(|s| db.get_by_idx(s.card_idx).is_ex).unwrap_or(false);
                            return if opp_is_ex { 92.0 } else { 22.0 };
                        }
                        // Mars: opponent discards 1 random card.  Disruption
                        // value scales with opponent hand size.
                        if card.name == "Mars" {
                            let opp_hand = state.players[1 - player_idx].hand.len() as f32;
                            return 32.0 + opp_hand.min(7.0) * 4.0;
                        }
                        // Iono: shuffle both hands & draw 3 each.  Good when
                        // our own hand is weak, or opponent hand is loaded.
                        if card.name == "Iono" {
                            let own_hand = player.hand.len();
                            let opp_hand = state.players[1 - player_idx].hand.len();
                            if own_hand <= 2 { return 72.0; }
                            if opp_hand >= 5 && own_hand <= 4 { return 58.0; }
                            return 28.0;
                        }
                        // Copycat: draw cards = opponent's hand size.  Best
                        // when we're card-starved and they're card-rich.
                        if card.name == "Copycat" {
                            let own_hand = player.hand.len() as f32;
                            let opp_hand = state.players[1 - player_idx].hand.len() as f32;
                            let diff = (opp_hand - own_hand).max(0.0);
                            if opp_hand >= 4.0 && own_hand <= 3.0 {
                                return 68.0 + diff * 2.0;
                            }
                            return 30.0 + diff * 3.0;
                        }
                        // Lillie: heal 60 from a Stage 2 Pokémon. (Earlier
                        // I scored this as a draw card — wrong.  legal_actions
                        // emits one play_item per damaged Stage 2 target via
                        // heal_target_actions; this branch scores the
                        // chosen target with the survival-aware heal scorer.)
                        if card.name == "Lillie" {
                            let target_slot = action.target.and_then(
                                |t| crate::state::get_slot(state, t));
                            if let Some(slot) = target_slot {
                                return 18.0 + heal_benefit_score(
                                    state, db, player_idx, slot, 60,
                                );
                            }
                            return 22.0;
                        }
                        // Gladion: search deck for any card.  Always useful
                        // while the deck still has cards.
                        if card.name == "Gladion" {
                            return if !player.deck.is_empty() { 58.0 } else { 10.0 };
                        }
                        // Pokémon Center Lady: heal 30 + cure status.  Heal
                        // targeting flows through heal_target_actions; this
                        // scorer is reached once a damaged target was chosen.
                        // (Card heals 30, not 60 — earlier round had this wrong.)
                        if card.name == "Pokémon Center Lady" {
                            let target_slot = action.target.and_then(
                                |t| crate::state::get_slot(state, t));
                            if let Some(slot) = target_slot {
                                let status_bonus = if slot.has_any_status() { 10.0 } else { 0.0 };
                                return 20.0 + heal_benefit_score(
                                    state, db, player_idx, slot, 30,
                                ) + status_bonus;
                            }
                            return 25.0;
                        }
                        // Erika (heal 50 HP to a Grass Pokémon) — supporters
                        // targeted via heal_grass_target already ensure the
                        // target is damaged; further judge the heal's value.
                        if card.name == "Erika" {
                            let target_slot = action.target.and_then(
                                |t| crate::state::get_slot(state, t));
                            if let Some(slot) = target_slot {
                                return 15.0 + heal_benefit_score(
                                    state, db, player_idx, slot, 50,
                                );
                            }
                            return 20.0;
                        }
                        // Leaf: -2 retreat cost on the Active Pokémon this turn.
                        // (NOT a heal — earlier round had this wrong.  legal_actions
                        // already gates on active retreat cost ≥ 1.)  Higher
                        // value when we actually want to retreat right now.
                        if card.name == "Leaf" {
                            if should_retreat_now(state, db, player_idx) {
                                return 60.0;
                            }
                            return 18.0;
                        }
                        // Budding Expeditioner: return Mew ex active → hand.
                        // legal_actions already ensures Mew ex is active +
                        // bench has Pokemon.  Worth playing when Mew ex is
                        // threatened (KO'd next turn) so we save it.
                        if card.name == "Budding Expeditioner" {
                            let active = match player.active.as_ref() {
                                Some(s) => s,
                                None => return 5.0,
                            };
                            let opp_dmg = opponent_expected_damage_to(
                                state, db, player_idx, active);
                            let will_ko = opp_dmg >= active.current_hp;
                            // If Mew ex will die next turn, saving it by
                            // bouncing is a big deal (preserves the ex so
                            // opponent doesn't bank points).
                            if will_ko { return 85.0; }
                            // Otherwise it trades a card for resetting the
                            // active — weak value when Mew ex is safe.
                            return 12.0;
                        }
                        // May: put 2 random Pokemon deck→hand + shuffle
                        // back.  Useful early for deck thinning / finding
                        // evolution lines.
                        if card.name == "May" {
                            let pokemon_in_deck = player.deck.iter()
                                .filter(|&&idx| db.try_get_by_idx(idx)
                                    .map(|c| c.kind == crate::types::CardKind::Pokemon)
                                    .unwrap_or(false))
                                .count();
                            if pokemon_in_deck >= 4 && state.turn_number <= 6 {
                                return 52.0;
                            }
                            return 28.0;
                        }
                        // Guzma: discard ALL Pokémon Tool cards attached to
                        // the opponent's Pokémon.  Score by count of opp
                        // Pokémon currently carrying a tool — bigger discard,
                        // bigger play.  (Previous round mis-scored this as a
                        // bench-switch like Cyrus.)
                        if card.name == "Guzma" {
                            let opp = 1 - player_idx;
                            let mut tool_count = 0u8;
                            if let Some(s) = state.players[opp].active.as_ref() {
                                if s.tool_idx.is_some() { tool_count += 1; }
                            }
                            for j in 0..3 {
                                if let Some(s) = state.players[opp].bench[j].as_ref() {
                                    if s.tool_idx.is_some() { tool_count += 1; }
                                }
                            }
                            if tool_count == 0 { return 5.0; }
                            return 35.0 + (tool_count as f32) * 12.0;
                        }
                        // Lusamine: recycle Ultra Beast supporters.
                        if card.name == "Lusamine" {
                            return 42.0;
                        }
                        // Other supporters
                        return 40.0;
                    }
                    crate::types::CardKind::Item => {
                        // Potion: heal 20 HP off the active.  Use the
                        // survival-aware heal scorer so we don't burn a Potion
                        // on a 10-damage or doomed active.
                        if card.name == "Potion" {
                            let active_slot = match player.active.as_ref() {
                                Some(s) => s,
                                None => return 5.0,
                            };
                            let damage_taken = active_slot.max_hp - active_slot.current_hp;
                            if damage_taken < 20 { return 5.0; }
                            let heal_score = heal_benefit_score(
                                state, db, player_idx, active_slot, 20,
                            );
                            return 20.0 + heal_score;
                        }
                        // Rare Candy: check if it can be used (Stage 2 evo)
                        if card.name == "Rare Candy" {
                            // Rare Candy evolves a Basic Pokemon directly to a Stage 2 (skipping
                            // Stage 1). The scorer must check the BASIC→STAGE2 chain via
                            // `db.basic_to_stage2`, NOT the Stage 2's `evolves_from` (which
                            // names the Stage 1 — typically not in Rare Candy decks).
                            //
                            // Also: a freshly-played Basic can't be evolved this turn (engine
                            // requires `turns_in_play >= 1`), so we discount when no in-play
                            // basic qualifies.
                            let basic_in_play_qualifies = |slot_card_idx: u16, turns_in_play: u8| -> bool {
                                if turns_in_play < 1 { return false; }
                                let c = db.get_by_idx(slot_card_idx);
                                if c.stage != Some(crate::types::Stage::Basic) { return false; }
                                let reachable = match db.basic_to_stage2.get(&c.name) {
                                    Some(r) if !r.is_empty() => r,
                                    _ => return false,
                                };
                                // Is there a Stage 2 in hand that this Basic can evolve into?
                                player.hand.iter().enumerate().any(|(hi, &ci)| {
                                    if hi == hidx { return false; } // skip the Rare Candy itself
                                    let s2 = db.get_by_idx(ci);
                                    s2.stage == Some(crate::types::Stage::Stage2)
                                        && reachable.contains(&s2.name)
                                })
                            };
                            let active_ok = player.active.as_ref()
                                .map(|s| basic_in_play_qualifies(s.card_idx, s.turns_in_play))
                                .unwrap_or(false);
                            let bench_ok = player.bench.iter().any(|bs| {
                                bs.as_ref()
                                    .map(|s| basic_in_play_qualifies(s.card_idx, s.turns_in_play))
                                    .unwrap_or(false)
                            });
                            return if active_ok || bench_ok { 78.0 } else { 10.0 };
                        }
                        // Poké Ball: search a random Basic.  More valuable
                        // early when setup matters, still useful late.
                        if card.name == "Poké Ball" || card.name == "Poke Ball" {
                            let basic_in_deck = player.deck.iter()
                                .filter(|&&idx| db.try_get_by_idx(idx)
                                    .map(|c| c.kind == crate::types::CardKind::Pokemon
                                          && c.stage == Some(crate::types::Stage::Basic))
                                    .unwrap_or(false))
                                .count();
                            if basic_in_deck == 0 { return 5.0; }
                            return if state.turn_number <= 4 { 55.0 } else { 40.0 };
                        }
                        // X Speed: reduce retreat cost by 1 this turn.  Only
                        // useful when we actually want to retreat this turn.
                        if card.name == "X Speed" {
                            if should_retreat_now(state, db, player_idx) {
                                return 62.0;
                            }
                            return 12.0;
                        }
                        // Red Card: opponent shuffles hand, draws 3.
                        // Best when opponent has 5+ cards (disruption value).
                        if card.name == "Red Card" {
                            let opp_hand = state.players[1 - player_idx].hand.len();
                            if opp_hand >= 6 { return 55.0; }
                            if opp_hand >= 5 { return 38.0; }
                            return 12.0;
                        }
                        // Flame Patch: legal_actions already gates this on
                        // Fire-in-discard AND Fire-active.  If we see it,
                        // play it — turns buried energy into attacking ready.
                        if card.name == "Flame Patch" {
                            return 50.0;
                        }
                        // Starting Plains: +20 HP to every Basic in play.
                        // Strongly asymmetric with Basic-heavy decks; play
                        // it early to maximise total HP boost.
                        if card.name == "Starting Plains" {
                            let own_basics = count_basics_in_play(state, db, player_idx);
                            let opp_basics = count_basics_in_play(state, db, 1 - player_idx);
                            if own_basics > opp_basics { return 55.0; }
                            return 25.0;
                        }
                        // Skull Fossil: play to get Cranidos — always useful
                        // if Cranidos/Rampardos isn't already down.
                        if card.name == "Skull Fossil" {
                            return 48.0;
                        }
                        // Items: base moderate score
                        return 35.0;
                    }
                    crate::types::CardKind::Tool => {
                        let target = action.target;
                        let target_slot = target.and_then(|t| crate::state::get_slot(state, t));
                        let target_card = target_slot.map(|s| db.get_by_idx(s.card_idx));
                        let target_is_active = target.map(|t| t.is_active()).unwrap_or(false);
                        let target_element = target_card.and_then(|c| c.element);
                        let target_is_ex = target_card.map(|c| c.is_ex).unwrap_or(false);
                        let target_hp = target_card.map(|c| c.hp).unwrap_or(0);

                        // Giant Cape (+20 HP): best on the highest-HP attacker
                        // (usually an ex in the active spot).
                        if card.name == "Giant Cape" {
                            if target_is_ex { return 48.0; }
                            if target_hp >= 110 { return 38.0; }
                            return 22.0;
                        }
                        // Rocky Helmet (retaliate 20 on hit): best on a bulky
                        // active that's likely to be attacked.
                        if card.name == "Rocky Helmet" {
                            if target_is_active && target_hp >= 120 { return 42.0; }
                            if target_is_active { return 28.0; }
                            return 16.0;
                        }
                        // Poison Barb (may poison attacker on hit): only
                        // really valuable on the active Pokémon.
                        if card.name == "Poison Barb" {
                            if target_is_active { return 38.0; }
                            return 14.0;
                        }
                        // Inflatable Boat (–1 retreat on Water): only useful
                        // attached to a Water Pokémon.
                        if card.name == "Inflatable Boat" {
                            if target_element == Some(crate::types::Element::Water) {
                                return 40.0;
                            }
                            return 5.0;
                        }
                        return 28.0;
                    }
                    _ => return 20.0,
                }
            }
            20.0
        }

        ActionKind::AttachEnergy => {
            // Attaching energy is important — score by progress toward attacks
            if let Some(target) = action.target {
                let slot = match crate::state::get_slot(state, target) {
                    Some(s) => s,
                    None => return 0.0,
                };
                let card = db.get_by_idx(slot.card_idx);
                if card.attacks.is_empty() {
                    return 5.0;
                }

                // Estimate effective damage for each attack on this card.
                // For 0-base-damage attacks with CopyOpponentAttack (e.g. Mew ex
                // Genome Hacking), substitute the opponent's best attack damage so
                // the agent correctly recognises their value and saves energy for them.
                let opp_idx = 1 - target.player as usize;
                let opp_best_dmg: i16 = state.players[opp_idx].active.as_ref()
                    .map(|s| db.get_by_idx(s.card_idx).attacks.iter().map(|a| a.damage).max().unwrap_or(0))
                    .unwrap_or(0);

                let (best_dmg, best_cost) = card.attacks.iter()
                    .map(|a| {
                        let has_copy = a.effects.iter().any(|e| matches!(e, EffectKind::CopyOpponentAttack));
                        let effective_dmg = if has_copy && a.damage == 0 {
                            opp_best_dmg + state.players[target.player as usize].attack_damage_bonus as i16
                        } else {
                            a.damage
                        };
                        (effective_dmg, a.cost.len() as i16)
                    })
                    .max_by_key(|(dmg, _)| *dmg)
                    .unwrap_or((0, 0));

                let current_energy = slot.total_energy() as i16;
                let missing = (best_cost - current_energy).max(0);

                // Higher score for targets that are 1 energy away from attacking
                let readiness_bonus = match missing {
                    0 => 5.0,  // Already has enough - small bonus (shouldn't need more)
                    1 => 20.0, // One more and they can attack!
                    2 => 12.0,
                    _ => 5.0,
                };

                let base = if target.is_active() { 38.0 } else { 24.0 };
                base + readiness_bonus + best_dmg as f32 * 0.1
            } else {
                20.0
            }
        }

        ActionKind::UseAbility => {
            if let Some(target) = action.target {
                if let Some(slot) = crate::state::get_slot(state, target) {
                    let card = db.get_by_idx(slot.card_idx);
                    if let Some(ref ab) = card.ability {
                        for effect in &ab.effects {
                            match effect {
                                // Energy-attach abilities (Gardevoir Psy Shadow, etc.).
                                // These attach energy to the acting player's ACTIVE Pokemon.
                                // Score based on whether the extra energy unlocks a better
                                // attack THIS SAME TURN, so the ability is always used before
                                // attacking when it matters (e.g. Mew ex Genome Hacking).
                                EffectKind::AttachEnergyZoneSelf
                                | EffectKind::AttachEnergyZoneSelfN { .. }
                                | EffectKind::AttachEnergyZoneSelfBracket { .. } => {
                                    let gain = energy_attach_attack_gain(state, db, player_idx);
                                    if gain > 0 {
                                        // Unlocks a stronger attack this turn: score above
                                        // normal attack so we always use the ability first.
                                        return 95.0 + gain as f32 * 0.8;
                                    }
                                    // No unlocking benefit — still useful for future turns.
                                    return 52.0;
                                }
                                // Bench-damage abilities (Greninja Water Shuriken)
                                EffectKind::BenchHitOpponent { amount } => {
                                    // Score like an attack — check if it KOs any bench target
                                    let opp = 1 - player_idx;
                                    let ko_bonus = state.players[opp].bench.iter().any(|s| {
                                        s.as_ref().map(|slot| slot.current_hp <= *amount).unwrap_or(false)
                                    });
                                    return if ko_bonus { 195.0 } else { 80.0 + *amount as f32 * 0.5 };
                                }
                                // Shiinotic Illuminate: random Pokémon from
                                // deck to hand.  Great consistency tool,
                                // especially when hand lacks evolutions.
                                EffectKind::SearchDeckRandomPokemon => {
                                    let pokemon_in_deck = state.players[player_idx].deck.iter()
                                        .filter(|&&idx| db.try_get_by_idx(idx)
                                            .map(|c| c.kind == crate::types::CardKind::Pokemon)
                                            .unwrap_or(false))
                                        .count();
                                    if pokemon_in_deck == 0 { return 5.0; }
                                    // Higher score when we're actively searching
                                    // for an evolution / attacker.
                                    let own_hand_has_pokemon = state.players[player_idx].hand.iter()
                                        .any(|&idx| db.try_get_by_idx(idx)
                                            .map(|c| c.kind == crate::types::CardKind::Pokemon)
                                            .unwrap_or(false));
                                    return if own_hand_has_pokemon { 55.0 } else { 70.0 };
                                }
                                // Toxic Poison (Nihilego More Poison) — use before attacking
                                // so the poison damage stacks with our attack damage.
                                // Score high if opponent is not already at full toxic stack,
                                // lower if we've already used it this game.
                                EffectKind::ToxicPoison => {
                                    let opp = 1 - player_idx;
                                    let opp_poisoned = state.players[opp].active.as_ref()
                                        .map(|s| s.has_status(crate::types::StatusEffect::Poisoned))
                                        .unwrap_or(false);
                                    // High priority: poisons if not yet poisoned, OR stacks more damage
                                    return if opp_poisoned {
                                        // Already poisoned — still valuable to add +20 more/turn
                                        75.0
                                    } else {
                                        // Not yet poisoned — very high priority to set up Venoshock / Unseen Claw
                                        88.0
                                    };
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
            30.0
        }

        ActionKind::Retreat => {
            if let Some(target) = action.target {
                let active = match state.players[player_idx].active.as_ref() {
                    Some(s) => s,
                    None => return 3.0,
                };
                let active_card = db.get_by_idx(active.card_idx);
                let bench_slot = match crate::state::get_slot(state, target) {
                    Some(s) => s,
                    None => return 0.0,
                };
                let bench_card = db.get_by_idx(bench_slot.card_idx);

                // Check if active is about to be KO'd by opponent
                let opp_active = state.players[opp_idx].active.as_ref();
                let active_threatened = if let Some(opp) = opp_active {
                    let opp_card = db.get_by_idx(opp.card_idx);
                    let opp_dmg = opp_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                    let opp_dmg_with_weakness = if crate::constants::is_weak_to(active_card.weakness, opp_card.element) {
                        opp_dmg + crate::constants::WEAKNESS_BONUS
                    } else {
                        opp_dmg
                    };
                    active.current_hp <= opp_dmg_with_weakness
                } else {
                    false
                };

                let bench_max_dmg = bench_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                let bench_best_cost = bench_card.attacks.iter()
                    .max_by_key(|a| a.damage)
                    .map(|a| a.cost.len() as i16)
                    .unwrap_or(0);
                let bench_energy = bench_slot.total_energy() as i16;
                let bench_ready = bench_best_cost > 0 && bench_energy >= bench_best_cost;

                let active_max_dmg = active_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                let active_best_cost = active_card.attacks.iter()
                    .max_by_key(|a| a.damage)
                    .map(|a| a.cost.len() as i16)
                    .unwrap_or(0);
                let active_ready = active_best_cost > 0
                    && (active.total_energy() as i16) >= active_best_cost;

                // Defensive retreat: about to be KO'd, bench can bail us out
                if active_threatened && bench_energy > 0 {
                    return 60.0 + bench_max_dmg as f32 * 0.3;
                }

                // Offensive retreat: the active is stuck (can't attack this
                // turn and little progress) but the bench has a ready heavy
                // hitter.  Swap in so the ready attacker starts dealing.
                if bench_ready
                    && !active_ready
                    && bench_max_dmg >= active_max_dmg + 40
                    && active.total_energy() <= 1
                {
                    return 48.0 + (bench_max_dmg - active_max_dmg) as f32 * 0.15;
                }
                3.0
            } else {
                3.0
            }
        }

        ActionKind::Promote => {
            // Pick the best bench Pokémon to promote after our active KO'd.
            // Factors:
            //   - Can it attack RIGHT NOW? (energy >= best attack cost) — big bonus
            //   - Energy already attached (partial readiness)
            //   - Current HP (tank value)
            //   - Best attack damage (offensive upside)
            //   - Evolved stage / ex status (investment we don't want to lose)
            if let Some(target) = action.target {
                let p = &state.players[target.player as usize];
                if let Some(slot) = p.bench[target.bench_index()].as_ref() {
                    let card = db.get_by_idx(slot.card_idx);
                    let best_dmg = card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                    let best_cost = card.attacks.iter()
                        .max_by_key(|a| a.damage)
                        .map(|a| a.cost.len() as i16)
                        .unwrap_or(0);
                    let energy = slot.total_energy() as i16;
                    let ready_now = best_cost > 0 && energy >= best_cost;
                    let ready_bonus: f32 = if ready_now { 80.0 } else { 0.0 };
                    let energy_progress = (energy.min(best_cost.max(1))) as f32 * 10.0;
                    let hp_bonus = slot.current_hp as f32 * 0.4;
                    let dmg_bonus = best_dmg as f32 * 0.25;
                    let stage_bonus = match card.stage {
                        Some(crate::types::Stage::Stage2) => 25.0,
                        Some(crate::types::Stage::Stage1) => 12.0,
                        _ => 0.0,
                    };
                    let ex_bonus: f32 = if card.is_ex { 18.0 } else { 0.0 };
                    return hp_bonus + dmg_bonus + energy_progress
                         + ready_bonus + stage_bonus + ex_bonus;
                }
            }
            0.0
        }

        ActionKind::EndTurn => 1.0,
    }
}

/// Select the highest-scoring action from the legal set.
fn select_heuristic_action(
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
    actions: &[Action],
) -> Action {
    let mut best_score = f32::NEG_INFINITY;
    let mut best_idx = 0usize;

    for (i, action) in actions.iter().enumerate() {
        let score = score_action(state, db, player_idx, action);
        if score > best_score {
            best_score = score;
            best_idx = i;
        }
    }

    actions[best_idx].clone()
}

/// Compute the marginal attack-damage gain from using an energy-attach ability
/// this turn before attacking.  Returns how many extra damage points the best
/// newly-unlocked attack deals compared to the best attack available right now.
///
/// Used to score UseAbility (Gardevoir Psy Shadow, etc.) above a plain attack
/// when the extra energy would unlock a much stronger attack.
fn energy_attach_attack_gain(state: &GameState, db: &CardDb, player_idx: usize) -> i16 {
    let active = match state.players[player_idx].active.as_ref() {
        Some(s) => s,
        None => return 0,
    };
    let card = db.get_by_idx(active.card_idx);
    let cur_energy = active.total_energy();

    // Best damage achievable right now (with current energy).
    let dmg_now = (0..card.attacks.len())
        .map(|i| estimate_damage(state, db, player_idx, i))
        .max()
        .unwrap_or(0);

    // Best damage achievable with exactly one extra Colorless energy.
    // Simulate +1 Colorless by checking attacks whose TOTAL cost == cur_energy + 1.
    // For those attacks, estimate damage as if the energy check passes.
    let opp = 1 - player_idx;
    let opp_active = match state.players[opp].active.as_ref() {
        Some(s) => s,
        None => return 0,
    };
    let opp_card = db.get_by_idx(opp_active.card_idx);

    let dmg_with_extra = card.attacks.iter()
        .filter(|atk| atk.cost.len() as u8 == cur_energy + 1)
        .map(|atk| {
            // Estimate damage for this attack (energy check will pass after +1).
            let mut dmg = atk.damage;
            dmg += state.players[player_idx].attack_damage_bonus as i16;
            if crate::constants::is_weak_to(opp_card.weakness, card.element) {
                dmg += crate::constants::WEAKNESS_BONUS;
            }
            dmg = (dmg - opp_active.incoming_damage_reduction as i16).max(0);
            // Handle 0-base-damage effects (Genome Hacking, BenchHitOpponent).
            for effect in &atk.effects {
                match effect {
                    EffectKind::CopyOpponentAttack => {
                        let best = opp_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                        dmg = best + state.players[player_idx].attack_damage_bonus as i16;
                    }
                    EffectKind::BenchHitOpponent { amount } => {
                        if dmg == 0 { dmg = *amount; }
                    }
                    EffectKind::RandomMultiHit { count, amount } => {
                        dmg = (*count as i16) * (*amount);
                    }
                    _ => {}
                }
            }
            dmg
        })
        .max()
        .unwrap_or(0);

    (dmg_with_extra - dmg_now).max(0)
}

/// Estimate damage dealt by the active Pokemon's given attack, including weakness.
/// Returns 0 if the attacker cannot pay the attack's energy cost.
fn estimate_damage(
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
    attack_index: usize,
) -> i16 {
    let player = &state.players[player_idx];
    let active = match player.active.as_ref() {
        Some(s) => s,
        None => return 0,
    };
    let card = db.get_by_idx(active.card_idx);
    let opp = 1 - player_idx;
    let opp_active = match state.players[opp].active.as_ref() {
        Some(s) => s,
        None => return 0,
    };
    let opp_card = db.get_by_idx(opp_active.card_idx);

    if attack_index >= card.attacks.len() {
        return 0;
    }
    let attack = &card.attacks[attack_index];

    // Check that attacker can actually pay the cost
    if !crate::engine::attack::can_pay_cost(active, &attack.cost) {
        return 0;
    }

    let mut dmg = attack.damage;

    // Add player damage bonus aura (e.g. Giovanni effect)
    dmg += player.attack_damage_bonus as i16;

    // Weakness bonus
    if crate::constants::is_weak_to(opp_card.weakness, card.element) {
        dmg += crate::constants::WEAKNESS_BONUS;
    }

    // Tool / incoming damage reduction on defender
    dmg = (dmg - opp_active.incoming_damage_reduction as i16).max(0);

    // Check effects for handler-based damage variants
    for effect in &attack.effects {
        match effect {
            EffectKind::RandomMultiHit { count, amount } => {
                // Draco Meteor: 4 hits × 50 = 200 total spread across opponent's team.
                // Hits are random but total damage dealt equals count * amount.
                // Use full expected value since this is the primary damage source.
                dmg = (*count as i16) * (*amount);
            }
            EffectKind::BenchHitOpponent { amount } => {
                // Pierce the Pain and similar: sets the full bench damage.
                // This attack has 0 base damage so we override the estimate entirely.
                dmg = *amount + player.attack_damage_bonus as i16;
            }
            EffectKind::MultiCoinPerEnergyDamage { per } => {
                // Average: 0.5 heads per coin per energy
                let energy = active.total_energy() as f32;
                dmg = (energy * 0.5 * *per as f32) as i16;
            }
            // coin_flip_nothing: attack does nothing on tails — estimate 50% of damage
            EffectKind::CoinFlipNothing => {
                dmg = dmg / 2;
            }
            // coin_flip_bonus_damage: +bonus on heads — add 50% of bonus as expected value
            EffectKind::CoinFlipBonusDamage { amount } => {
                dmg += amount / 2;
            }
            EffectKind::CopyOpponentAttack => {
                // Genome Hacking: copies opponent's highest-damage attack.
                // Replace whatever base estimate we had with the copied damage
                // (the attack has 0 base damage, so dmg is only the aura bonus
                // at this point — we must set it to the copied damage directly).
                let best = opp_card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                dmg = best + player.attack_damage_bonus as i16;
            }
            EffectKind::BonusIfBenchDamaged { bonus } => {
                // Drampa Berserk: add bonus if any own bench pokemon is damaged.
                let bench_damaged = state.players[player_idx].bench.iter().any(|bs| {
                    bs.as_ref().map(|s| s.current_hp < s.max_hp).unwrap_or(false)
                });
                if bench_damaged { dmg += bonus; }
            }
            EffectKind::BonusIfExtraEnergy { threshold, bonus, energy_type } => {
                let count = if energy_type.is_empty() {
                    active.total_energy() as i16
                } else {
                    crate::types::Element::from_str(energy_type)
                        .map(|el| active.energy[el.idx()] as i16)
                        .unwrap_or(0)
                };
                if count >= *threshold { dmg += bonus; }
            }
            // Venoshock / Clodsire: +bonus when opponent is poisoned
            EffectKind::BonusIfOpponentPoisoned { bonus } => {
                if opp_active.has_status(crate::types::StatusEffect::Poisoned) {
                    dmg += bonus;
                }
            }
            // Absol Unseen Claw: +bonus when opponent has any status
            EffectKind::BonusIfOpponentHasStatus { bonus } => {
                if opp_active.has_any_status() {
                    dmg += bonus;
                }
            }
            _ => {}
        }
    }

    dmg
}

// ------------------------------------------------------------------ //
// Unit tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::{Card, CardDb};
    use crate::state::{GameState, PokemonSlot};
    use crate::types::{ActionKind, CardKind, GamePhase, Stage};
    use std::collections::HashMap;

    /// Build a minimal CardDb with two cards: one basic attacker (card 0) and
    /// a defender (card 1). The attacker has one attack dealing 60 damage.
    fn build_db() -> CardDb {
        let attacker = Card {
            id: "atk-001".to_string(),
            idx: 0,
            name: "Attacker".to_string(),
            kind: CardKind::Pokemon,
            stage: Some(Stage::Basic),
            element: Some(crate::types::Element::Fire),
            hp: 80,
            weakness: None,
            retreat_cost: 1,
            is_ex: false,
            is_mega_ex: false,
            evolves_from: None,
            attacks: vec![crate::card::Attack {
                name: "Flamethrower".to_string(),
                damage: 60,
                cost: vec![crate::types::CostSymbol::Fire, crate::types::CostSymbol::Fire],
                effect_text: String::new(),
                handler: String::new(),
                effects: vec![],
                legal_conditions: vec![],
            }],
            ability: None,
            trainer_effect_text: String::new(),
            trainer_handler: String::new(),
            trainer_effects: vec![],
            trainer_legal_conditions: vec![],
            ko_points: 1,
        };

        let defender = Card {
            id: "def-001".to_string(),
            idx: 1,
            name: "Defender".to_string(),
            kind: CardKind::Pokemon,
            stage: Some(Stage::Basic),
            element: Some(crate::types::Element::Grass),
            hp: 50,
            weakness: Some(crate::types::Element::Fire), // weak to Fire
            retreat_cost: 1,
            is_ex: false,
            is_mega_ex: false,
            evolves_from: None,
            attacks: vec![],
            ability: None,
            trainer_effect_text: String::new(),
            trainer_handler: String::new(),
            trainer_effects: vec![],
            trainer_legal_conditions: vec![],
            ko_points: 1,
        };

        let mut id_to_idx = HashMap::new();
        id_to_idx.insert("atk-001".to_string(), 0u16);
        id_to_idx.insert("def-001".to_string(), 1u16);

        let mut name_to_indices = HashMap::new();
        name_to_indices.insert("Attacker".to_string(), vec![0u16]);
        name_to_indices.insert("Defender".to_string(), vec![1u16]);

        CardDb {
            cards: vec![attacker, defender],
            id_to_idx,
            name_to_indices,
            basic_to_stage2: HashMap::new(),
        }
    }

    /// Build a minimal state where player 0 has a fully energised attacker and
    /// player 1 has a weak defender with low HP — so ATTACK is clearly best.
    fn build_combat_state() -> GameState {
        let mut state = GameState::new(42);
        state.phase = GamePhase::Main;
        state.turn_number = 3;
        state.current_player = 0;

        let mut attacker_slot = PokemonSlot::new(0, 80);
        // Attach 2 Fire energy so the attack is payable
        attacker_slot.add_energy(crate::types::Element::Fire, 2);
        state.players[0].active = Some(attacker_slot);

        // Defender at low HP (30), weak to Fire — attack deals 60+20=80 ≥ 30, a KO
        state.players[1].active = Some(PokemonSlot::new(1, 30));

        state
    }

    #[test]
    fn random_agent_returns_valid_action() {
        let db = build_db();
        let state = build_combat_state();
        let agent = RandomAgent;
        let action = agent.select_action(&state, &db, 0);
        // Should be one of the legal actions (Attack or EndTurn)
        assert!(
            action.kind == ActionKind::Attack || action.kind == ActionKind::EndTurn,
            "RandomAgent returned unexpected action kind: {:?}",
            action.kind
        );
    }

    #[test]
    fn heuristic_agent_prefers_ko_attack() {
        let db = build_db();
        let state = build_combat_state();
        let agent = HeuristicAgent;
        let action = agent.select_action(&state, &db, 0);
        assert_eq!(
            action.kind,
            ActionKind::Attack,
            "HeuristicAgent should choose ATTACK when it KOs the opponent"
        );
        assert_eq!(action.attack_index, Some(0));
    }

    #[test]
    fn random_agent_promotion_phase() {
        let mut state = GameState::new(7);
        state.phase = GamePhase::AwaitingBenchPromotion;
        state.players[0].bench[1] = Some(PokemonSlot::new(0, 80));

        let db = build_db();
        let agent = RandomAgent;
        let action = agent.select_action(&state, &db, 0);
        assert_eq!(action.kind, ActionKind::Promote);
    }

    #[test]
    fn heuristic_agent_promotion_phase() {
        let mut state = GameState::new(7);
        state.phase = GamePhase::AwaitingBenchPromotion;
        state.players[0].bench[0] = Some(PokemonSlot::new(0, 80));
        state.players[0].bench[2] = Some(PokemonSlot::new(1, 50));

        let db = build_db();
        let agent = HeuristicAgent;
        let action = agent.select_action(&state, &db, 0);
        assert_eq!(action.kind, ActionKind::Promote);
    }
}
