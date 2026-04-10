//! GameRunner — drives a single complete game to completion.
//!
//! Implemented in Wave 9 (T23).

use crate::card::CardDb;
use crate::state::GameState;
use crate::types::{ActionKind, Element, GamePhase};
use crate::agents::Agent;
use crate::engine::{setup, mutations, ko, turn};
use crate::engine::legal_actions::{get_legal_setup_placements, get_legal_setup_bench_placements};
use crate::state::PokemonSlot;
use crate::constants::MAX_TURNS;

// ------------------------------------------------------------------ //
// Public API
// ------------------------------------------------------------------ //

/// Result of a completed game.
#[derive(Debug, Clone)]
pub struct GameResult {
    /// `Some(0)` player 0 wins, `Some(1)` player 1 wins, `None` for draw.
    pub winner: Option<usize>,
    /// Number of turns the game lasted.
    pub turns: u32,
    /// Prize points earned by player 0.
    pub player0_points: u8,
    /// Prize points earned by player 1.
    pub player1_points: u8,
}

/// Runs a complete game between two agents, returning the result.
///
/// # Arguments
/// * `db`                              — card database
/// * `deck0` / `deck1`                 — 20-card decks as card index vectors
/// * `energy_types0` / `energy_types1` — energy pools for each player
/// * `agent0` / `agent1`               — agents controlling each player
/// * `seed`                            — RNG seed for deterministic replay
pub fn run_game(
    db: &CardDb,
    deck0: Vec<u16>,
    deck1: Vec<u16>,
    energy_types0: Vec<Element>,
    energy_types1: Vec<Element>,
    agent0: &dyn Agent,
    agent1: &dyn Agent,
    seed: u64,
) -> GameResult {
    // 1. Create game state
    let mut state = setup::create_game(db, deck0, deck1, energy_types0, energy_types1, seed);

    // 2. Draw opening hands (mulligan loop inside)
    setup::draw_opening_hands(&mut state, db);

    // 3. Setup phase: each agent chooses which Basic to place as their active
    run_setup_phase(&mut state, db, agent0, agent1);

    // 4. Finalize setup (coin flip for first player, start turn 0)
    setup::finalize_setup(&mut state, db);

    // 5. Main game loop
    run_main_loop(&mut state, db, agent0, agent1);

    // 6. Build and return result
    // state.winner: None = ongoing, Some(-1) = draw,
    //               Some(0) = p0 wins, Some(1) = p1 wins
    let winner = match state.winner {
        Some(w) if w >= 0 => Some(w as usize),
        _ => None, // draw (Some(-1)) or unexpected None
    };

    GameResult {
        winner,
        turns: state.turn_number.max(0) as u32,
        player0_points: state.players[0].points,
        player1_points: state.players[1].points,
    }
}

// ------------------------------------------------------------------ //
// Internal helpers
// ------------------------------------------------------------------ //

/// Ask each agent to choose their starting active Basic Pokemon, then optionally
/// place additional Basics on their bench.
///
/// Both players choose simultaneously in a real game; here we ask agent 0
/// then agent 1.  For each player:
///   1. Agent picks an Active from their hand Basics.
///   2. Agent may place additional Basics on empty bench slots (one at a time)
///      until they pass (EndTurn) or run out of Basics / bench space.
fn run_setup_phase(
    state: &mut GameState,
    db: &CardDb,
    agent0: &dyn Agent,
    agent1: &dyn Agent,
) {
    for player_idx in 0..2 {
        // Step 1 — choose active.
        let legal = get_legal_setup_placements(state, db, player_idx);
        if legal.is_empty() {
            continue; // No basics (shouldn't happen after mulligan).
        }

        let agent: &dyn Agent = if player_idx == 0 { agent0 } else { agent1 };
        let action = agent.select_action(state, db, player_idx);
        let hand_idx = action.hand_index
            .unwrap_or_else(|| legal[0].hand_index.unwrap_or(0));
        setup::apply_setup_placement(state, db, player_idx, hand_idx, &[]);

        // Step 2 — optionally place bench Basics.
        run_setup_bench_phase(state, db, player_idx, agent);
    }
}

/// Let an agent place additional Basics on their bench during setup (optional).
///
/// Loops until the agent picks EndTurn, there are no more Basics in hand,
/// or all bench slots are full.
fn run_setup_bench_phase(
    state: &mut GameState,
    db: &CardDb,
    player_idx: usize,
    agent: &dyn Agent,
) {
    loop {
        let options = get_legal_setup_bench_placements(state, db, player_idx);
        // If the only option is "end turn" (no placeable Basics), stop.
        if options.len() <= 1 {
            break;
        }

        let action = agent.select_action(state, db, player_idx);

        match action.kind {
            ActionKind::EndTurn => break,
            ActionKind::PlayCard => {
                let hand_idx = match action.hand_index {
                    Some(i) => i,
                    None => break,
                };
                let bench_slot = match action.target {
                    Some(t) if t.is_bench() => t.bench_index(),
                    _ => break,
                };
                if hand_idx >= state.players[player_idx].hand.len() {
                    break;
                }
                let card_idx = state.players[player_idx].hand[hand_idx];
                let hp = db.get_by_idx(card_idx).hp;
                state.players[player_idx].bench[bench_slot] = Some(PokemonSlot::new(card_idx, hp));
                state.players[player_idx].hand.remove(hand_idx);
            }
            _ => break,
        }
    }
}

/// Drive the main game loop until a winner is determined or the turn limit is hit.
///
/// Mirrors the Python `game_runner.py` logic:
/// - `ATTACK` and `END_TURN` both trigger `advance_turn`.
/// - `Attack` also triggers `check_and_handle_kos` before advancing.
/// - `AwaitingBenchPromotion` is resolved before continuing the turn.
fn run_main_loop(
    state: &mut GameState,
    db: &CardDb,
    agent0: &dyn Agent,
    agent1: &dyn Agent,
) {
    // Hard action-step cap — prevents infinite loops from engine bugs.
    // Expected: ~10 actions/turn × 60 turns ≈ 600 steps. Allow 5×.
    const MAX_STEPS: u32 = 3_000;
    let mut steps: u32 = 0;

    loop {
        steps += 1;
        if steps > MAX_STEPS {
            ko::check_winner(state);
            break;
        }

        // Exit if the game is already over
        if state.winner.is_some() || state.phase == GamePhase::GameOver {
            break;
        }

        // Hard turn-limit guard
        if state.turn_number >= MAX_TURNS {
            ko::check_winner(state);
            break;
        }

        match state.phase {
            GamePhase::GameOver => break,

            GamePhase::AwaitingBenchPromotion => {
                // The player whose active is None must promote a bench Pokemon.
                let promoting_player = find_promotion_player(state);
                let agent: &dyn Agent = if promoting_player == 0 { agent0 } else { agent1 };
                let action = agent.select_action(state, db, promoting_player);
                // apply_action dispatches Promote → ko::promote_bench
                mutations::apply_action(state, db, &action);
                // After promotion phase returns to Main (or GameOver).
            }

            GamePhase::Main => {
                let current = state.current_player;
                let agent: &dyn Agent = if current == 0 { agent0 } else { agent1 };
                let action = agent.select_action(state, db, current);
                let action_kind = action.kind;

                // EndTurn → mutations::apply_action → advance_turn (handles turn flip).
                // Attack → execute_attack (no turn flip inside mutations); we handle below.
                // All other actions just mutate state; loop continues.
                mutations::apply_action(state, db, &action);

                // In PTCGP, attacking ends the turn (same as EndTurn).
                // The Rust mutations layer doesn't auto-advance on Attack, so we mirror
                // the Python runner: `if action.kind in (ATTACK, END_TURN): advance_turn`.
                if action_kind == ActionKind::Attack
                    && state.phase == GamePhase::Main
                    && state.winner.is_none()
                {
                    // Process KOs from the attack before advancing the turn.
                    ko::check_and_handle_kos(state, db);
                    if state.winner.is_none() && state.phase == GamePhase::Main {
                        turn::advance_turn(state, db);
                    }
                }
            }

            GamePhase::Setup => {
                // Should not be reached after finalize_setup; bail safely.
                break;
            }
        }
    }
}

/// Return the index (0 or 1) of the player who needs to promote a bench Pokemon.
///
/// In `AwaitingBenchPromotion` the player whose active is `None` is the one
/// who must promote.  Falls back to `current_player` if ambiguous.
fn find_promotion_player(state: &GameState) -> usize {
    for i in 0..2 {
        if state.players[i].active.is_none()
            && state.players[i].bench.iter().any(|s| s.is_some())
        {
            return i;
        }
    }
    state.current_player
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agents::RandomAgent;
    use crate::card::CardDb;
    use crate::types::{CardKind, Stage};
    use std::path::PathBuf;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    fn load_db() -> CardDb {
        CardDb::load_from_dir(&assets_dir())
    }

    /// Build a 20-card deck of basic Pokemon (up to 2 copies each) and
    /// return a matching energy type.
    fn make_basic_deck(db: &CardDb) -> (Vec<u16>, Vec<Element>) {
        let basics: Vec<u16> = db
            .cards
            .iter()
            .filter(|c| {
                c.kind == CardKind::Pokemon && c.stage == Some(Stage::Basic) && c.hp > 0
            })
            .take(10)
            .flat_map(|c| [c.idx, c.idx]) // 2 copies each → up to 20
            .take(20)
            .collect();

        let energy_type = db
            .cards
            .iter()
            .find(|c| c.kind == CardKind::Pokemon && c.stage == Some(Stage::Basic))
            .and_then(|c| c.element)
            .unwrap_or(Element::Grass);

        (basics, vec![energy_type])
    }

    #[test]
    fn run_game_completes_without_panic() {
        let db = load_db();
        let (deck0, et0) = make_basic_deck(&db);
        let (deck1, et1) = make_basic_deck(&db);

        assert!(!deck0.is_empty(), "Need at least one basic Pokemon in the db");

        let agent0 = RandomAgent;
        let agent1 = RandomAgent;

        let result = run_game(&db, deck0, deck1, et0, et1, &agent0, &agent1, 42);

        // Game must have lasted at least one turn
        assert!(result.turns > 0, "Game should last at least one turn, got {:?}", result);

        // Either a winner is identified or the game reached the turn limit (draw)
        assert!(
            result.winner.is_some()
                || result.player0_points > 0
                || result.player1_points > 0
                || result.turns >= MAX_TURNS as u32,
            "Game ended with no winner and no clear draw condition: {:?}",
            result,
        );
    }

    #[test]
    fn run_game_reproducible_with_same_seed() {
        let db = load_db();
        let (deck0, et0) = make_basic_deck(&db);
        let (deck1, et1) = make_basic_deck(&db);

        let agent0 = RandomAgent;
        let agent1 = RandomAgent;

        let r1 = run_game(
            &db,
            deck0.clone(), deck1.clone(),
            et0.clone(), et1.clone(),
            &agent0, &agent1,
            7,
        );
        let r2 = run_game(
            &db,
            deck0, deck1,
            et0, et1,
            &agent0, &agent1,
            7,
        );

        assert_eq!(r1.winner, r2.winner, "Same seed must give same winner");
        assert_eq!(r1.turns, r2.turns, "Same seed must give same turn count");
        assert_eq!(r1.player0_points, r2.player0_points);
        assert_eq!(r1.player1_points, r2.player1_points);
    }

    #[test]
    fn run_game_different_seeds_no_panic() {
        let db = load_db();
        let (deck0, et0) = make_basic_deck(&db);
        let (deck1, et1) = make_basic_deck(&db);

        let agent0 = RandomAgent;
        let agent1 = RandomAgent;

        // Just verify these seeds don't panic
        let _r1 = run_game(&db, deck0.clone(), deck1.clone(), et0.clone(), et1.clone(), &agent0, &agent1, 0);
        let _r2 = run_game(&db, deck0, deck1, et0, et1, &agent0, &agent1, 999_999);
    }
}
