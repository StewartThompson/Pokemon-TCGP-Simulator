// Agent trait, RandomAgent, HeuristicAgent, HumanAgent
// Implemented in Wave 8 (T22), HumanAgent added in Rust migration

pub mod human;

use crate::card::CardDb;
use crate::state::GameState;
use crate::actions::Action;
use crate::types::{ActionKind, GamePhase};
use crate::engine::legal_actions::{get_legal_actions, get_legal_promotions, get_legal_setup_placements, get_legal_setup_bench_placements};

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
            GamePhase::Setup => get_legal_setup_placements(state, db, player_idx),
            GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
            _ => get_legal_actions(state, db),
        };

        if actions.is_empty() {
            return Action::end_turn();
        }

        // Use a deterministic local rng seeded from turn/player so the agent
        // is reproducible without mutating state.
        let mut rng = SmallRng::seed_from_u64(
            state.turn_number as u64 ^ (player_idx as u64).wrapping_mul(0xdead_beef),
        );
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
            GamePhase::Setup => get_legal_setup_placements(state, db, player_idx),
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
            // KO detection — massive priority
            if dmg > 0 && dmg >= opp_active.current_hp {
                return 200.0 + opp_card.ko_points as f32 * 30.0;
            }
            // Non-KO: score by damage dealt
            let pct = if opp_active.max_hp > 0 {
                dmg as f32 / opp_active.max_hp as f32
            } else {
                0.0
            };
            55.0 + pct * 50.0 + dmg as f32 * 0.15
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
                65.0 + stage_bonus + pos_bonus + max_dmg as f32 * 0.1
            } else {
                65.0
            }
        }

        ActionKind::PlayCard => {
            // Play Basic Pokemon to bench
            if let Some(hidx) = action.hand_index {
                let card = db.get_by_idx(player.hand[hidx]);
                if card.kind == crate::types::CardKind::Pokemon
                    && card.stage == Some(crate::types::Stage::Basic)
                {
                    let empty = player.bench.iter().filter(|s| s.is_none()).count();
                    if state.turn_number <= 3 {
                        return if empty >= 2 { 72.0 } else { 55.0 };
                    }
                    return match empty {
                        e if e >= 2 => 55.0,
                        1 => 32.0,
                        _ => 10.0,
                    };
                }
                // Supporters / Items: moderate priority
                return 25.0;
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
                let best_dmg = card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                let base = if target.is_active() { 34.0 } else { 22.0 };
                base + best_dmg as f32 * 0.1
            } else {
                20.0
            }
        }

        ActionKind::UseAbility => 30.0,

        ActionKind::Retreat => 3.0,

        ActionKind::Promote => {
            // During AwaitingBenchPromotion, pick the slot with the most ready damage
            if let Some(target) = action.target {
                let p = &state.players[target.player as usize];
                if let Some(slot) = p.bench[target.bench_index()].as_ref() {
                    let card = db.get_by_idx(slot.card_idx);
                    let best_dmg = card.attacks.iter().map(|a| a.damage).max().unwrap_or(0);
                    return slot.current_hp as f32 + best_dmg as f32;
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

/// Estimate damage dealt by the active Pokemon's given attack, including weakness.
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
    let mut dmg = attack.damage;

    // Add player damage bonus aura (e.g. Giovanni effect)
    dmg += player.attack_damage_bonus as i16;

    // Weakness bonus
    if crate::constants::is_weak_to(opp_card.weakness, card.element) {
        dmg += crate::constants::WEAKNESS_BONUS;
    }

    // Tool / incoming damage reduction on defender
    dmg = (dmg - opp_active.incoming_damage_reduction as i16).max(0);

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
            }],
            ability: None,
            trainer_effect_text: String::new(),
            trainer_handler: String::new(),
            trainer_effects: vec![],
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
