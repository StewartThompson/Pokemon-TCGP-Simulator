//! Self-learning bot — MCTS agent and (eventually) value net + training.
//!
//! # Wave 1 (current)
//!
//! Pure MCTS with random rollouts. No neural net, no training, no deps.
//! See `plans/composed-exploring-lagoon.md` for the full roadmap.
//!
//! ## What's here
//!
//! - [`mcts::MctsAgent`] — implements the standard [`crate::agents::Agent`]
//!   trait, so it plugs into `run_game` / `run_batch_fixed_decks` with no
//!   changes to the runner.
//! - [`determinize::determinize_for`] — re-samples the opponent's hidden
//!   information (hand + deck order) so MCTS can't cheat by inspecting cards
//!   the acting player shouldn't see.
//!
//! ## Design notes
//!
//! The tree is arena-allocated (`Vec<Node>`, edges hold `Option<usize>` child
//! indexes). This sidesteps borrow-checker contortions that plague
//! `Box<Node>` MCTS implementations.
//!
//! Value is stored from the *root player's* perspective throughout the tree.
//! UCB selection at each node flips sign when the node belongs to the
//! opponent (classic minimax-style search on top of sample returns).

pub mod card_embed;
pub mod checkpoint;
pub mod determinize;
pub mod features;
pub mod league;
pub mod mcts;
pub mod net;
pub mod nn_greedy;
pub mod replay;
pub mod selfplay;
pub mod train;

pub use checkpoint::{
    gen_dir, latest_generation, list_generations, load_generation, save_generation, Meta,
};
pub use league::{pick_opponent, Opponent};
pub use mcts::{action_to_policy_idx, LeafValue, MctsAgent, MctsConfig, PolicySource, RootQSource};
pub use net::{best_device, huber_loss, is_metal, make_optimizer, InferenceNet, ValueNet, ValueOutputs, HIDDEN_DIM, MAX_POLICY_SIZE};
pub use nn_greedy::NnGreedyAgent;
pub use replay::{ReplayBuffer, Sample};
pub use selfplay::{play_training_game, RecordingAgent};
pub use train::{train_epoch, train_epoch_weighted, TrainStats};
