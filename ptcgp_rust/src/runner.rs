// run_game
// Stub for T24 compile check — full implementation in Wave 9 (T23)

/// Result from a single simulated game.
#[derive(Debug, Clone)]
pub struct GameResult {
    /// Index of the winning player (0 or 1), or None for a draw / timeout.
    pub winner: Option<usize>,
    /// Number of turns the game lasted.
    pub turns: u32,
    /// Prize points earned by player 0.
    pub player0_points: u8,
    /// Prize points earned by player 1.
    pub player1_points: u8,
}

/// Run a single game to completion and return the result.
///
/// # Arguments
/// * `db`     — shared card database
/// * `deck0`  — list of card indices for player 0's deck (20 cards)
/// * `deck1`  — list of card indices for player 1's deck (20 cards)
/// * `e0`     — energy types available to player 0
/// * `e1`     — energy types available to player 1
/// * `agent0` — decision-making agent for player 0
/// * `agent1` — decision-making agent for player 1
/// * `seed`   — RNG seed for deterministic replay
pub fn run_game(
    db: &crate::card::CardDb,
    deck0: Vec<u16>,
    deck1: Vec<u16>,
    e0: Vec<crate::types::Element>,
    e1: Vec<crate::types::Element>,
    agent0: &dyn crate::agents::Agent,
    agent1: &dyn crate::agents::Agent,
    seed: u64,
) -> GameResult {
    use crate::engine::setup::{create_game, draw_opening_hands};
    use crate::types::{GamePhase, ActionKind};
    use crate::engine::legal_actions::{get_legal_actions, get_legal_promotions};
    use crate::engine::mutations::apply_action;

    const MAX_TURNS: u32 = 200;

    let mut state = create_game(db, deck0, deck1, e0, e1, seed);
    draw_opening_hands(&mut state, db);

    let mut turns = 0u32;

    loop {
        // Check win condition
        if let Some(winner_i8) = state.winner {
            let p0_pts = state.players[0].points;
            let p1_pts = state.players[1].points;
            return GameResult {
                winner: if winner_i8 >= 0 { Some(winner_i8 as usize) } else { None },
                turns,
                player0_points: p0_pts,
                player1_points: p1_pts,
            };
        }

        if turns >= MAX_TURNS {
            let p0_pts = state.players[0].points;
            let p1_pts = state.players[1].points;
            let winner = if p0_pts > p1_pts {
                Some(0)
            } else if p1_pts > p0_pts {
                Some(1)
            } else {
                None
            };
            return GameResult {
                winner,
                turns,
                player0_points: p0_pts,
                player1_points: p1_pts,
            };
        }

        let current = state.current_player;
        let agent: &dyn crate::agents::Agent = if current == 0 { agent0 } else { agent1 };

        let actions = match state.phase {
            GamePhase::AwaitingBenchPromotion => get_legal_promotions(&state, current),
            _ => get_legal_actions(&state, db),
        };

        let action = if actions.is_empty() {
            crate::actions::Action::end_turn()
        } else {
            agent.select_action(&state, db, current)
        };

        if action.kind == ActionKind::EndTurn {
            turns += 1;
        }

        apply_action(&mut state, db, &action);
    }
}
