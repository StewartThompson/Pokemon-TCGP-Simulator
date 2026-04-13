// run_batch with Rayon
// Implemented in Wave 9 (T24)

use std::sync::Arc;
use rayon::prelude::*;
use crate::card::CardDb;
use crate::types::Element;
use crate::agents::Agent;
use crate::runner::{GameResult, run_game};

// ------------------------------------------------------------------ //
// BatchResult
// ------------------------------------------------------------------ //

/// Summary statistics aggregated from a batch of simulated games.
#[derive(Debug, Clone, Default)]
pub struct BatchResult {
    /// Total number of games run.
    pub total_games: usize,
    /// Number of games won by player 0.
    pub player0_wins: usize,
    /// Number of games won by player 1.
    pub player1_wins: usize,
    /// Number of games that ended in a draw or timeout.
    pub draws: usize,
    /// Average number of turns per game.
    pub avg_turns: f64,
    /// Win rate for player 0 (0.0 – 1.0).
    pub win_rate_player0: f64,
    /// Win rate for player 1 (0.0 – 1.0).
    pub win_rate_player1: f64,
}

impl BatchResult {
    /// Compute a `BatchResult` from a slice of individual game results.
    pub fn from_results(results: &[GameResult]) -> Self {
        let total = results.len();
        if total == 0 {
            return Self::default();
        }
        let p0_wins = results.iter().filter(|r| r.winner == Some(0)).count();
        let p1_wins = results.iter().filter(|r| r.winner == Some(1)).count();
        let draws = results.iter().filter(|r| r.winner.is_none()).count();
        let avg_turns = results.iter().map(|r| r.turns as f64).sum::<f64>() / total as f64;
        Self {
            total_games: total,
            player0_wins: p0_wins,
            player1_wins: p1_wins,
            draws,
            avg_turns,
            win_rate_player0: p0_wins as f64 / total as f64,
            win_rate_player1: p1_wins as f64 / total as f64,
        }
    }
}

// ------------------------------------------------------------------ //
// run_batch
// ------------------------------------------------------------------ //

/// Run `n_games` games in parallel using Rayon.
///
/// Each game receives a unique seed derived from `base_seed + game_index`,
/// so results are deterministic and reproducible for a given `base_seed`.
///
/// The `deck_builder` closure is called once per game with the game index,
/// allowing different deck configurations per game if desired.
///
/// # Arguments
/// * `db`           — shared, read-only card database
/// * `deck_builder` — closure `|game_idx| -> (deck0, deck1, energy0, energy1)`
/// * `agent0`       — agent for player 0 (must be `Send + Sync`)
/// * `agent1`       — agent for player 1 (must be `Send + Sync`)
/// * `n_games`      — total number of games to simulate
/// * `base_seed`    — base RNG seed; game `i` uses `base_seed.wrapping_add(i)`
pub fn run_batch(
    db: Arc<CardDb>,
    deck_builder: impl Fn(usize) -> (Vec<u16>, Vec<u16>, Vec<Element>, Vec<Element>) + Send + Sync,
    agent0: Arc<dyn Agent>,
    agent1: Arc<dyn Agent>,
    n_games: usize,
    base_seed: u64,
) -> BatchResult {
    let results: Vec<GameResult> = (0..n_games)
        .into_par_iter()
        .map(|i| {
            let (deck0, deck1, e0, e1) = deck_builder(i);
            run_game(
                &db,
                deck0,
                deck1,
                e0,
                e1,
                agent0.as_ref(),
                agent1.as_ref(),
                base_seed.wrapping_add(i as u64),
                None, // batch simulation — no narration
            )
        })
        .collect();

    BatchResult::from_results(&results)
}

// ------------------------------------------------------------------ //
// run_batch_fixed_decks
// ------------------------------------------------------------------ //

/// Convenience wrapper around [`run_batch`] for the common case where both
/// players use the same fixed decks for every game in the batch.
///
/// # Arguments
/// * `db`             — shared, read-only card database
/// * `deck0`          — card indices for player 0's deck (20 cards)
/// * `deck1`          — card indices for player 1's deck (20 cards)
/// * `energy_types0`  — energy pool for player 0
/// * `energy_types1`  — energy pool for player 1
/// * `agent0`         — agent for player 0
/// * `agent1`         — agent for player 1
/// * `n_games`        — total number of games to simulate
/// * `base_seed`      — base RNG seed
pub fn run_batch_fixed_decks(
    db: Arc<CardDb>,
    deck0: Vec<u16>,
    deck1: Vec<u16>,
    energy_types0: Vec<Element>,
    energy_types1: Vec<Element>,
    agent0: Arc<dyn Agent>,
    agent1: Arc<dyn Agent>,
    n_games: usize,
    base_seed: u64,
) -> BatchResult {
    run_batch(
        db,
        move |_| (deck0.clone(), deck1.clone(), energy_types0.clone(), energy_types1.clone()),
        agent0,
        agent1,
        n_games,
        base_seed,
    )
}

// ------------------------------------------------------------------ //
// Unit tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runner::GameResult;

    // ---------------------------------------------------------------- //
    // Helper: build a GameResult by hand
    // ---------------------------------------------------------------- //

    fn make_result(winner: Option<usize>, turns: u32) -> GameResult {
        GameResult {
            winner,
            turns,
            player0_points: 0,
            player1_points: 0,
        }
    }

    // ---------------------------------------------------------------- //
    // BatchResult math
    // ---------------------------------------------------------------- //

    #[test]
    fn batch_result_empty() {
        let br = BatchResult::from_results(&[]);
        assert_eq!(br.total_games, 0);
        assert_eq!(br.player0_wins, 0);
        assert_eq!(br.player1_wins, 0);
        assert_eq!(br.draws, 0);
        assert_eq!(br.avg_turns, 0.0);
        assert_eq!(br.win_rate_player0, 0.0);
        assert_eq!(br.win_rate_player1, 0.0);
    }

    #[test]
    fn batch_result_calculates_win_rates() {
        // 4 games: p0 wins 2, p1 wins 1, draw 1
        let results = vec![
            make_result(Some(0), 10),
            make_result(Some(0), 20),
            make_result(Some(1), 15),
            make_result(None, 200),
        ];
        let br = BatchResult::from_results(&results);

        assert_eq!(br.total_games, 4);
        assert_eq!(br.player0_wins, 2);
        assert_eq!(br.player1_wins, 1);
        assert_eq!(br.draws, 1);

        let expected_avg = (10.0 + 20.0 + 15.0 + 200.0) / 4.0;
        assert!((br.avg_turns - expected_avg).abs() < 1e-9);

        assert!((br.win_rate_player0 - 0.5).abs() < 1e-9);
        assert!((br.win_rate_player1 - 0.25).abs() < 1e-9);
    }

    #[test]
    fn batch_result_all_player0_wins() {
        let results: Vec<GameResult> = (0..10).map(|i| make_result(Some(0), i as u32 + 5)).collect();
        let br = BatchResult::from_results(&results);
        assert_eq!(br.total_games, 10);
        assert_eq!(br.player0_wins, 10);
        assert_eq!(br.player1_wins, 0);
        assert_eq!(br.draws, 0);
        assert!((br.win_rate_player0 - 1.0).abs() < 1e-9);
        assert!((br.win_rate_player1 - 0.0).abs() < 1e-9);
    }

    // ---------------------------------------------------------------- //
    // run_batch_fixed_decks — integration smoke test
    // ---------------------------------------------------------------- //

    #[test]
    fn run_batch_fixed_decks_produces_n_results() {
        let db = Arc::new(
            CardDb::load_from_dir(
                std::path::Path::new(
                    "/Users/stewart/Documents/projects/PokemonTCGP-BattleSimulator/assets/cards",
                ),
            ),
        );

        // Build a minimal 20-card Grass deck (Bulbasaur a1-001 repeated).
        let bulbasaur_idx = db.get_by_id("a1-001")
            .expect("a1-001 (Bulbasaur) not found in card DB")
            .idx;
        let deck: Vec<u16> = vec![bulbasaur_idx; 20];

        let agent0: Arc<dyn Agent> = Arc::new(crate::agents::RandomAgent);
        let agent1: Arc<dyn Agent> = Arc::new(crate::agents::RandomAgent);

        let n_games = 10;
        let result = run_batch_fixed_decks(
            Arc::clone(&db),
            deck.clone(),
            deck,
            vec![Element::Grass],
            vec![Element::Grass],
            agent0,
            agent1,
            n_games,
            12345,
        );

        assert_eq!(result.total_games, n_games, "total_games should equal n_games");
        assert_eq!(
            result.player0_wins + result.player1_wins + result.draws,
            n_games,
            "wins + draws must sum to total_games"
        );
        assert!(result.avg_turns > 0.0, "average turns should be positive");
        // Win rates sum to ≤ 1.0 (draws account for the remainder)
        assert!(result.win_rate_player0 + result.win_rate_player1 <= 1.0 + 1e-9);
    }

    #[test]
    fn run_batch_seeds_are_independent() {
        // Running two batches with the same base_seed should produce identical results.
        let db = Arc::new(
            CardDb::load_from_dir(
                std::path::Path::new(
                    "/Users/stewart/Documents/projects/PokemonTCGP-BattleSimulator/assets/cards",
                ),
            ),
        );

        let bulbasaur_idx = db.get_by_id("a1-001")
            .expect("a1-001 not found")
            .idx;
        let deck: Vec<u16> = vec![bulbasaur_idx; 20];

        let make_agents = || (
            Arc::new(crate::agents::RandomAgent) as Arc<dyn Agent>,
            Arc::new(crate::agents::RandomAgent) as Arc<dyn Agent>,
        );

        let (a0, a1) = make_agents();
        let r1 = run_batch_fixed_decks(
            Arc::clone(&db), deck.clone(), deck.clone(),
            vec![Element::Grass], vec![Element::Grass],
            a0, a1, 5, 99,
        );

        let (a0, a1) = make_agents();
        let r2 = run_batch_fixed_decks(
            Arc::clone(&db), deck.clone(), deck.clone(),
            vec![Element::Grass], vec![Element::Grass],
            a0, a1, 5, 99,
        );

        assert_eq!(r1.player0_wins, r2.player0_wins, "deterministic: p0 wins must match");
        assert_eq!(r1.player1_wins, r2.player1_wins, "deterministic: p1 wins must match");
        assert_eq!(r1.draws, r2.draws, "deterministic: draws must match");
    }
}
