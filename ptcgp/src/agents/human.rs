//! Human terminal agent — reads moves from stdin, displays board state.

use std::io::{self, BufRead, Write};
use crate::agents::Agent;
use crate::actions::Action;
use crate::card::CardDb;
use crate::state::{GameState, get_slot};
use crate::types::{ActionKind, GamePhase};
use crate::engine::legal_actions::{get_legal_actions, get_legal_promotions, get_legal_setup_placements};
use crate::ui::render_state;

// ------------------------------------------------------------------ //
// HumanAgent
// ------------------------------------------------------------------ //

pub struct HumanAgent {
    /// Which player index this human controls (0 or 1).
    pub player_index: usize,
}

impl HumanAgent {
    pub fn new(player_index: usize) -> Self {
        Self { player_index }
    }
}

impl Agent for HumanAgent {
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action {
        let actions = match state.phase {
            GamePhase::Setup => get_legal_setup_placements(state, db, player_idx),
            GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
            _ => get_legal_actions(state, db),
        };

        // Show the board (skip during setup — board is empty)
        if state.phase != GamePhase::Setup {
            render_state(state, db, self.player_index);
        }

        // Prompt label changes based on phase
        let prompt_label = match state.phase {
            GamePhase::Setup => "\nChoose your starting Active Pokemon:",
            GamePhase::AwaitingBenchPromotion => "\nChoose a Pokemon to promote to Active:",
            _ => "\nAvailable actions:",
        };
        println!("{}", prompt_label);
        for (i, action) in actions.iter().enumerate() {
            println!("  {}: {}", i + 1, describe_action(action, state, db, player_idx));
        }

        // Read choice from stdin
        loop {
            print!("Choose action (1-{}): ", actions.len());
            let _ = io::stdout().flush();

            let mut line = String::new();
            let stdin = io::stdin();
            match stdin.lock().read_line(&mut line) {
                Ok(0) => {
                    // EOF — fall back to first action (non-interactive mode)
                    return actions[0].clone();
                }
                Ok(_) => {}
                Err(_) => return actions[0].clone(),
            }

            match line.trim().parse::<usize>() {
                Ok(n) if n >= 1 && n <= actions.len() => {
                    return actions[n - 1].clone();
                }
                _ => {
                    println!(
                        "Invalid choice '{}'. Enter a number between 1 and {}.",
                        line.trim(),
                        actions.len()
                    );
                }
            }
        }
    }
}

// ------------------------------------------------------------------ //
// Action description
// ------------------------------------------------------------------ //

fn describe_action(
    action: &Action,
    state: &GameState,
    db: &CardDb,
    player_idx: usize,
) -> String {
    match action.kind {
        ActionKind::EndTurn => "End turn".to_string(),

        ActionKind::Attack => {
            let player = &state.players[player_idx];
            if let Some(ref active) = player.active {
                let card = db.get_by_idx(active.card_idx);
                if let Some(i) = action.attack_index {
                    if let Some(atk) = card.attacks.get(i) {
                        let cost_str = atk.cost.iter()
                            .map(|c| format!("{:?}", c))
                            .collect::<Vec<_>>()
                            .join(",");
                        return format!("Attack: {} ({}dmg) [{}]", atk.name, atk.damage, cost_str);
                    }
                }
            }
            "Attack".to_string()
        }

        ActionKind::AttachEnergy => {
            if let Some(target) = action.target {
                let player = &state.players[player_idx];
                let energy = player.energy_available
                    .map(|e| format!("{:?}", e))
                    .unwrap_or_else(|| "?".to_string());
                if target.is_active() {
                    format!("Attach {} energy to active", energy)
                } else {
                    let slot_name = action.target
                        .and_then(|t| get_slot(state, t))
                        .map(|s| db.get_by_idx(s.card_idx).name.clone())
                        .unwrap_or_else(|| "bench".to_string());
                    format!("Attach {} energy to bench slot {} ({})", energy, target.slot, slot_name)
                }
            } else {
                "Attach energy".to_string()
            }
        }

        ActionKind::PlayCard => {
            if let Some(hidx) = action.hand_index {
                let player = &state.players[player_idx];
                if let Some(&card_idx) = player.hand.get(hidx) {
                    let card = db.get_by_idx(card_idx);
                    if let Some(target) = action.target {
                        let bench_pos = if target.is_active() {
                            "active".to_string()
                        } else {
                            format!("bench slot {}", target.slot)
                        };
                        return format!("Play {} -> {}", card.name, bench_pos);
                    }
                    return format!("Play {}", card.name);
                }
            }
            "Play card".to_string()
        }

        ActionKind::Evolve => {
            if let Some(hidx) = action.hand_index {
                let player = &state.players[player_idx];
                if let Some(&card_idx) = player.hand.get(hidx) {
                    let evo_card = db.get_by_idx(card_idx);
                    let target_name = action.target
                        .and_then(|t| get_slot(state, t))
                        .map(|s| db.get_by_idx(s.card_idx).name.clone())
                        .unwrap_or_else(|| "?".to_string());
                    return format!("Evolve {} → {}", target_name, evo_card.name);
                }
            }
            "Evolve".to_string()
        }

        ActionKind::Retreat => {
            if let Some(target) = action.target {
                let bench_name = action.target
                    .and_then(|t| get_slot(state, t))
                    .map(|s| db.get_by_idx(s.card_idx).name.clone())
                    .unwrap_or_else(|| "?".to_string());
                let _ = target; // suppress unused warning
                format!("Retreat → bring in {}", bench_name)
            } else {
                "Retreat".to_string()
            }
        }

        ActionKind::UseAbility => {
            if let Some(target) = action.target {
                let slot_name = get_slot(state, target)
                    .map(|s| db.get_by_idx(s.card_idx).name.clone())
                    .unwrap_or_else(|| "?".to_string());
                format!("Use ability ({})", slot_name)
            } else {
                "Use ability".to_string()
            }
        }

        ActionKind::Promote => {
            if let Some(target) = action.target {
                let bench_name = get_slot(state, target)
                    .map(|s| db.get_by_idx(s.card_idx).name.clone())
                    .unwrap_or_else(|| "?".to_string());
                format!("Promote {} to active", bench_name)
            } else {
                "Promote".to_string()
            }
        }
    }
}
