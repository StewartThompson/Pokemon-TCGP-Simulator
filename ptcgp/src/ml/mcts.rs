//! Monte Carlo Tree Search agent.
//!
//! Wave 1 implementation (no value network):
//!   * UCB1 selection.
//!   * Random rollouts to game end (or a depth cap) at unexpanded leaves.
//!   * Arena-allocated tree — borrow-checker-friendly.
//!   * Values stored from the root player's perspective; at opponent nodes
//!     we flip the sign during UCB selection (minimax on top of samples).
//!   * Single determinization per MCTS call — keeps the agent from cheating
//!     at opponent hand/deck info while staying fast. Per-rollout PIMC is
//!     a Wave 3 upgrade.
//!
//! # Fast paths
//!
//! * If only one legal action is available, return it directly without
//!   building a tree. In PTCGP many turn-states are forced.
//! * During `GamePhase::Setup` and `GamePhase::AwaitingBenchPromotion` we
//!   delegate to [`HeuristicAgent`] — these are shallow mechanical choices
//!   where full search is pure overhead.

use std::sync::Arc;

use rand::Rng;
use rand::SeedableRng;
use rand::rngs::SmallRng;

use crate::actions::Action;
use crate::agents::{Agent, HeuristicAgent, RandomAgent};
use crate::card::CardDb;
use crate::engine::legal_actions::{
    get_legal_actions, get_legal_promotions, get_legal_setup_bench_placements,
    get_legal_setup_placements,
};
use crate::engine::{ko, mutations, turn};
use crate::state::GameState;
use crate::types::{ActionKind, GamePhase};

use super::card_embed::{build_embed_cache, CARD_EMBED_DIM};
use super::determinize::determinize_for;
use super::features::encode_with_cache;
use super::net::ValueNet;

// ------------------------------------------------------------------ //
// Config
// ------------------------------------------------------------------ //

/// How to evaluate an unexpanded leaf inside MCTS.
#[derive(Clone, Debug)]
pub enum LeafValue {
    /// Play out with [`RandomAgent`] on both sides to a (capped) terminal.
    RandomRollout,
    /// Play out with [`HeuristicAgent`] on both sides (stronger but slower).
    HeuristicRollout,
    /// Call the learned value net on the leaf state instead of rolling out.
    /// Orders of magnitude faster than full rollouts once the net is trained.
    /// The agent must also carry the net itself (see [`MctsAgent::net`]).
    ValueNet,
    /// Hybrid leaf eval — blend the value net's prediction with a short
    /// random rollout. Guards against value-net errors in under-trained
    /// regions of the state space (which is ALL of them at small scales).
    ///
    /// `net_weight` in [0, 1] is the NN's fraction of the final value;
    /// the remaining `(1 - net_weight)` comes from a random rollout of
    /// up to `rollout_depth` plies. This is how the original AlphaGo
    /// combined its value net with Monte Carlo rollouts.
    HybridValueRollout { net_weight: f32, rollout_depth: u32 },
}

#[derive(Clone, Debug)]
pub struct MctsConfig {
    /// Total number of MCTS simulations per `select_action` call.
    pub total_sims: usize,
    /// UCB1 exploration constant. ~1.4 is a reasonable default.
    pub c_puct: f64,
    /// Action-selection temperature. 0 = argmax over visit counts (strongest
    /// at play time). >0 = sample proportional to visits^(1/T) (used during
    /// training for exploration).
    pub temperature: f32,
    /// Value source for leaf evaluation.
    pub leaf_value_source: LeafValue,
    /// Hard cap on plies during a rollout. Prevents pathological infinite
    /// sequences and keeps each sim cheap.
    pub rollout_depth_cap: u32,
    /// If true and only one legal action exists, return it without searching.
    pub delegate_trivial: bool,
    /// If true, defer to `HeuristicAgent` during Setup + Promotion phases.
    pub delegate_setup: bool,
}

impl Default for MctsConfig {
    fn default() -> Self {
        Self {
            total_sims: 500,
            c_puct: 1.4,
            temperature: 0.0,
            leaf_value_source: LeafValue::RandomRollout,
            rollout_depth_cap: 200,
            delegate_trivial: true,
            delegate_setup: true,
        }
    }
}

/// MCTS agent. Implements [`Agent`] so it drops into the existing runner.
pub struct MctsAgent {
    pub config: MctsConfig,
    pub db: Arc<CardDb>,
    /// Base seed for per-call RNG. The actual per-call seed mixes this with
    /// `state.turn_number + player_idx` so repeated calls on identical
    /// states explore differently across games.
    pub rng_seed: u64,
    /// Optional learned value net. Only consulted when
    /// `config.leaf_value_source == LeafValue::ValueNet`. Shared across
    /// rayon threads via `Arc`.
    pub net: Option<Arc<ValueNet>>,
    /// Pre-computed card embeddings. Built once from the `CardDb` and
    /// reused on every feature encoding during search — avoids rebuilding
    /// the cache on each hot-path call.
    pub embed_cache: Arc<Vec<[f32; CARD_EMBED_DIM]>>,
}

impl MctsAgent {
    pub fn new(config: MctsConfig, db: Arc<CardDb>) -> Self {
        let embed_cache = Arc::new(build_embed_cache(&db));
        Self {
            config,
            db,
            rng_seed: 0xCAFE_BABE_DEAD_BEEF,
            net: None,
            embed_cache,
        }
    }

    pub fn with_seed(mut self, seed: u64) -> Self {
        self.rng_seed = seed;
        self
    }

    /// Attach a value net. Required when
    /// `config.leaf_value_source == LeafValue::ValueNet`.
    pub fn with_net(mut self, net: Arc<ValueNet>) -> Self {
        self.net = Some(net);
        self
    }
}

// ------------------------------------------------------------------ //
// Agent impl
// ------------------------------------------------------------------ //

impl Agent for MctsAgent {
    fn select_action(&self, state: &GameState, db: &CardDb, player_idx: usize) -> Action {
        // Fast path 1: shallow phases → heuristic. Setup and bench-promotion
        // choices are simple and searching them wastes budget.
        if self.config.delegate_setup {
            match state.phase {
                GamePhase::Setup | GamePhase::AwaitingBenchPromotion => {
                    return HeuristicAgent.select_action(state, db, player_idx);
                }
                _ => {}
            }
        }

        let legal = legal_for_phase(state, db, player_idx);
        if legal.is_empty() {
            return Action::end_turn();
        }

        // Fast path 2: only one legal action → return directly.
        if self.config.delegate_trivial && legal.len() == 1 {
            return legal.into_iter().next().unwrap();
        }

        // Per-call seed: mixes base seed with a state-derived stir so that
        // independent games explore independently.
        let per_call_seed = self
            .rng_seed
            .rotate_left(13)
            .wrapping_add(state.turn_number as u64)
            .wrapping_add(player_idx as u64 * 1_000_003)
            .wrapping_add(
                state.players[player_idx]
                    .hand
                    .iter()
                    .copied()
                    .map(u64::from)
                    .fold(0u64, |a, c| a.wrapping_mul(31).wrapping_add(c)),
            );

        // Single determinization per MCTS call (Wave 1 simplification).
        let search_state = determinize_for(state, player_idx, per_call_seed);

        // Build and populate the tree.
        let mut tree = Tree::new(
            player_idx,
            self.config.clone(),
            per_call_seed,
            self.net.as_deref(),
            self.embed_cache.as_slice(),
        );
        let root = tree.new_node(&search_state, db);
        tree.root = root;

        for i in 0..self.config.total_sims {
            let mut sim_state = search_state.clone();
            // Each sim gets a fresh RNG so coin flips / energy gen aren't lock-stepped.
            sim_state.rng = SmallRng::seed_from_u64(per_call_seed.wrapping_add(i as u64));
            tree.simulate(root, &mut sim_state, db);
        }

        tree.best_action(root)
    }
}

// ------------------------------------------------------------------ //
// Tree / nodes
// ------------------------------------------------------------------ //

struct Edge {
    action: Action,
    child: Option<usize>,
    visits: u32,
    value_sum: f64, // from root player's perspective
}

struct Node {
    /// Whose turn it is at this state (who picks among children).
    player_to_move: u8,
    children: Vec<Edge>,
    visits: u32,
    value_sum: f64,
    is_terminal: bool,
    /// Set only when `is_terminal`. From root player's perspective.
    terminal_value: f64,
}

struct Tree<'a> {
    nodes: Vec<Node>,
    root_player: usize,
    root: usize,
    config: MctsConfig,
    rng: SmallRng,
    /// Optional value net — borrowed, not owned, so the same net is shared
    /// across many tree instances (one per MCTS call).
    net: Option<&'a ValueNet>,
    /// Card-embed cache for feature encoding at value-net leaves.
    embed_cache: &'a [[f32; CARD_EMBED_DIM]],
}

impl<'a> Tree<'a> {
    fn new(
        root_player: usize,
        config: MctsConfig,
        seed: u64,
        net: Option<&'a ValueNet>,
        embed_cache: &'a [[f32; CARD_EMBED_DIM]],
    ) -> Self {
        Self {
            nodes: Vec::with_capacity(256),
            root_player,
            root: 0,
            config,
            rng: SmallRng::seed_from_u64(seed),
            net,
            embed_cache,
        }
    }

    /// Create a node for the given state. Populates its edges with legal actions.
    fn new_node(&mut self, state: &GameState, db: &CardDb) -> usize {
        let pi = whose_turn(state);
        let legal = legal_for_phase(state, db, pi);
        let is_terminal = state.winner.is_some()
            || state.phase == GamePhase::GameOver
            || legal.is_empty();
        let terminal_value = if is_terminal {
            value_for_root(state, self.root_player)
        } else {
            0.0
        };
        let children: Vec<Edge> = legal
            .into_iter()
            .map(|a| Edge {
                action: a,
                child: None,
                visits: 0,
                value_sum: 0.0,
            })
            .collect();
        self.nodes.push(Node {
            player_to_move: pi as u8,
            children,
            visits: 0,
            value_sum: 0.0,
            is_terminal,
            terminal_value,
        });
        self.nodes.len() - 1
    }

    /// One full selection → (expand)→ simulate → backup pass.
    ///
    /// Note on PTCGP stochasticity: many attacks/effects have randomized
    /// outcomes (coin flips, random energy discard, random bench targets).
    /// This means a path that was legal when a child node was first
    /// expanded may be invalidated on a later visit (e.g. the Pokémon
    /// we meant to attach a tool to got KO'd this sim). Wave 1 handles
    /// this defensively: before applying a cached action we verify it's
    /// still legal; if not, we fall back to a random legal action and
    /// break to a rollout rather than descending further into stale
    /// tree branches. Wave 3 will upgrade to proper open-loop MCTS.
    fn simulate(&mut self, root_idx: usize, state: &mut GameState, db: &CardDb) {
        let mut path: Vec<(usize, usize)> = Vec::with_capacity(64);
        let mut cur = root_idx;

        let value = loop {
            if self.nodes[cur].is_terminal {
                break self.nodes[cur].terminal_value;
            }
            if self.nodes[cur].children.is_empty() {
                break value_for_root(state, self.root_player);
            }

            // UCB selection among cached edges.
            let edge_idx = self.ucb_select(cur);
            let action = self.nodes[cur].children[edge_idx].action.clone();

            // Guard against stochastic drift: is the cached action still legal?
            let pi = whose_turn(state);
            let current_legal = legal_for_phase(state, db, pi);
            let still_legal = current_legal
                .iter()
                .any(|a| action_key_eq(a, &action));

            if !still_legal {
                // Cached path invalidated by randomness. Take a random legal
                // action from the current state and break out to rollout.
                // Don't record this edge in the path — we'd bias the tree
                // toward a spurious decision.
                if current_legal.is_empty() {
                    break value_for_root(state, self.root_player);
                }
                let fi: usize = self.rng.gen_range(0..current_legal.len());
                apply_and_settle(state, db, &current_legal[fi]);
                if state.winner.is_some() || state.phase == GamePhase::GameOver {
                    break value_for_root(state, self.root_player);
                }
                break self.rollout(state, db);
            }

            apply_and_settle(state, db, &action);
            path.push((cur, edge_idx));

            if state.winner.is_some() || state.phase == GamePhase::GameOver {
                break value_for_root(state, self.root_player);
            }

            // Descend into the cached child or expand a new one.
            match self.nodes[cur].children[edge_idx].child {
                Some(child) => {
                    cur = child;
                }
                None => {
                    let new_idx = self.new_node(state, db);
                    self.nodes[cur].children[edge_idx].child = Some(new_idx);
                    if self.nodes[new_idx].is_terminal {
                        break self.nodes[new_idx].terminal_value;
                    }
                    break self.rollout(state, db);
                }
            }
        };

        self.backup(root_idx, &path, value);
    }

    fn ucb_select(&self, node_idx: usize) -> usize {
        let node = &self.nodes[node_idx];
        let parent_visits = node.visits.max(1) as f64;
        let log_parent = parent_visits.ln().max(0.0);
        let is_root_player = node.player_to_move as usize == self.root_player;

        let mut best_idx = 0usize;
        let mut best_score = f64::NEG_INFINITY;

        for (i, edge) in node.children.iter().enumerate() {
            let score = if edge.visits == 0 {
                // Unvisited → explore first. Use INFINITY with a tiny
                // tiebreak on action index to keep the first encountered
                // unvisited edge selected deterministically per search.
                f64::INFINITY - (i as f64) * 1e-12
            } else {
                let mean = edge.value_sum / edge.visits as f64;
                // Flip sign at opponent nodes so UCB always maximizes
                // "value for the player currently choosing".
                let q = if is_root_player { mean } else { -mean };
                let u = self.config.c_puct * (log_parent / edge.visits as f64).sqrt();
                q + u
            };
            if score > best_score {
                best_score = score;
                best_idx = i;
            }
        }
        best_idx
    }

    /// Evaluate a leaf state: either roll out with a cheap policy to a
    /// (capped) terminal, call the learned value net directly, or blend
    /// the two. Returns a value in [-1, +1] from the root player's POV.
    fn rollout(&mut self, state: &mut GameState, db: &CardDb) -> f64 {
        // Pure value-net leaf eval: fast, no rollout.
        if matches!(self.config.leaf_value_source, LeafValue::ValueNet) {
            return self.net_value(state, db);
        }

        // Hybrid: net value + short rollout value, blended.
        if let LeafValue::HybridValueRollout {
            net_weight,
            rollout_depth,
        } = self.config.leaf_value_source
        {
            // 1. NN prediction on the leaf (before any further mutation).
            let v_net = self.net_value(state, db);
            // 2. Short rollout from the leaf to sharpen the estimate.
            let v_roll = self.do_rollout(state, db, rollout_depth, RolloutPolicy::Random);
            // 3. Blend.
            let w = net_weight as f64;
            return (w * v_net + (1.0 - w) * v_roll).clamp(-1.0, 1.0);
        }

        // Full-length rollout path (Random / Heuristic policies).
        let policy = match self.config.leaf_value_source {
            LeafValue::HeuristicRollout => RolloutPolicy::Heuristic,
            _ => RolloutPolicy::Random,
        };
        self.do_rollout(state, db, self.config.rollout_depth_cap, policy)
    }

    /// Run NN forward on `state` and return the win value from the root
    /// player's perspective. 0 on any error or missing net.
    fn net_value(&self, state: &GameState, db: &CardDb) -> f64 {
        match self.net {
            Some(net) => {
                let features =
                    encode_with_cache(state, db, self.root_player, self.embed_cache);
                net.win_value(&features).map(|v| v as f64).unwrap_or(0.0)
            }
            None => 0.0,
        }
    }

    /// Play forward until terminal or `max_steps` plies exhausted. Uses
    /// `policy` for action selection on every turn. Returns the terminal
    /// value from the root player's perspective (or a prize-differential
    /// proxy if the cap is hit).
    fn do_rollout(
        &mut self,
        state: &mut GameState,
        db: &CardDb,
        max_steps: u32,
        policy: RolloutPolicy,
    ) -> f64 {
        let mut steps = 0u32;
        while state.winner.is_none()
            && state.phase != GamePhase::GameOver
            && steps < max_steps
        {
            let pi = whose_turn(state);
            let action = match policy {
                RolloutPolicy::Random => RandomAgent.select_action(state, db, pi),
                RolloutPolicy::Heuristic => HeuristicAgent.select_action(state, db, pi),
            };
            apply_and_settle(state, db, &action);
            steps += 1;
        }

        if state.winner.is_some() || state.phase == GamePhase::GameOver {
            value_for_root(state, self.root_player)
        } else {
            let p0 = state.players[0].points as f64;
            let p1 = state.players[1].points as f64;
            let diff = (p0 - p1) / 3.0;
            if self.root_player == 0 { diff } else { -diff }
        }
    }

    /// Update stats along the path. Also increments the root node and each
    /// expanded child node along the way — so UCB has correct parent-visit
    /// counts on the next descent.
    fn backup(&mut self, root_idx: usize, path: &[(usize, usize)], value: f64) {
        self.nodes[root_idx].visits += 1;
        self.nodes[root_idx].value_sum += value;
        for &(n_idx, e_idx) in path {
            self.nodes[n_idx].children[e_idx].visits += 1;
            self.nodes[n_idx].children[e_idx].value_sum += value;
            if let Some(child_idx) = self.nodes[n_idx].children[e_idx].child {
                self.nodes[child_idx].visits += 1;
                self.nodes[child_idx].value_sum += value;
            }
        }
    }

    /// At the root: pick the action with highest visit count (temperature=0)
    /// or sample proportional to `visits^(1/T)` (temperature>0).
    fn best_action(&mut self, root_idx: usize) -> Action {
        let t = self.config.temperature;
        let node = &self.nodes[root_idx];
        if node.children.is_empty() {
            return Action::end_turn();
        }
        if t < 1e-6 {
            let best = node
                .children
                .iter()
                .enumerate()
                .max_by_key(|(_, e)| e.visits)
                .map(|(i, _)| i)
                .unwrap_or(0);
            return node.children[best].action.clone();
        }
        // Temperature sampling.
        let inv_t = 1.0 / t as f64;
        let weights: Vec<f64> = node
            .children
            .iter()
            .map(|e| (e.visits as f64).powf(inv_t))
            .collect();
        let total: f64 = weights.iter().sum();
        if total <= 0.0 {
            return node.children[0].action.clone();
        }
        let mut r: f64 = self.rng.gen_range(0.0..total);
        for (i, w) in weights.iter().enumerate() {
            r -= w;
            if r <= 0.0 {
                return node.children[i].action.clone();
            }
        }
        node.children.last().unwrap().action.clone()
    }
}

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //

/// Legal actions for whatever phase the state is in.
fn legal_for_phase(state: &GameState, db: &CardDb, player_idx: usize) -> Vec<Action> {
    match state.phase {
        GamePhase::Setup => {
            if state.players[player_idx].active.is_some() {
                get_legal_setup_bench_placements(state, db, player_idx)
            } else {
                get_legal_setup_placements(state, db, player_idx)
            }
        }
        GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
        GamePhase::GameOver => Vec::new(),
        GamePhase::Main => get_legal_actions(state, db),
    }
}

/// In `AwaitingBenchPromotion` the player whose active is None must promote.
/// In every other phase it's `state.current_player`.
fn whose_turn(state: &GameState) -> usize {
    if state.phase == GamePhase::AwaitingBenchPromotion {
        for i in 0..2 {
            if state.players[i].active.is_none()
                && state.players[i].bench.iter().any(|s| s.is_some())
            {
                return i;
            }
        }
    }
    state.current_player
}

/// Internal policy enum for rollouts. Distinct from [`LeafValue`] which
/// decides the whole leaf-eval strategy — this one just picks actions
/// during the rollout itself.
#[derive(Clone, Copy, Debug)]
enum RolloutPolicy {
    Random,
    Heuristic,
}

/// Compare two actions for "is this the same move?" based on the fields that
/// `legal_actions` uses to distinguish choices. [`Action`] doesn't implement
/// [`Eq`] (only [`PartialEq`]) and we want a cheap check that ignores any
/// debug-only fields that could be added later.
fn action_key_eq(a: &Action, b: &Action) -> bool {
    a.kind == b.kind
        && a.hand_index == b.hand_index
        && a.target == b.target
        && a.attack_index == b.attack_index
        && a.extra_hand_index == b.extra_hand_index
        && a.extra_target == b.extra_target
}

/// Terminal value from the root player's perspective.
/// +1 win, -1 loss, 0 draw or unfinished.
fn value_for_root(state: &GameState, root_player: usize) -> f64 {
    match state.winner {
        Some(w) if w == root_player as i8 => 1.0,
        Some(w) if w >= 0 => -1.0, // opponent won
        _ => 0.0,                  // None (ongoing) or Some(-1) (draw)
    }
}

/// Apply an action and then perform the runner's post-action settle:
/// on Attack + still-Main + no winner, run KO handling and advance turn.
///
/// Mirrors the logic in `runner::run_main_loop` (around the Attack branch)
/// so MCTS plays states forward consistently with real games.
fn apply_and_settle(state: &mut GameState, db: &CardDb, action: &Action) {
    let kind = action.kind;
    mutations::apply_action(state, db, action);
    if kind == ActionKind::Attack
        && state.phase == GamePhase::Main
        && state.winner.is_none()
    {
        ko::check_and_handle_kos(state, db);
        if state.winner.is_none() && state.phase == GamePhase::Main {
            turn::advance_turn(state, db);
        }
    }
}

// ------------------------------------------------------------------ //
// Tests
// ------------------------------------------------------------------ //

#[cfg(test)]
mod tests {
    use super::*;
    use crate::card::CardDb;
    use std::path::PathBuf;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    #[test]
    fn mcts_returns_legal_action_with_minimal_sims() {
        let db = Arc::new(CardDb::load_from_dir(&assets_dir()));
        // Minimal-sim smoke test: with `total_sims=2` the agent should still
        // produce some legal action rather than panicking on the tiny tree.
        let config = MctsConfig {
            total_sims: 2,
            ..Default::default()
        };
        let agent = MctsAgent::new(config, db.clone());

        // Build a minimal state in Main phase. We reuse the engine test
        // helpers' pattern: two actives, both with grass energy, turn 2.
        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        let mut state = GameState::new(1);
        state.phase = GamePhase::Main;
        state.turn_number = 2;
        state.players[0].active = Some(crate::state::PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[1].active = Some(crate::state::PokemonSlot::new(bulb.idx, bulb.hp));
        state.players[0].energy_types = vec![crate::types::Element::Grass];
        state.players[1].energy_types = vec![crate::types::Element::Grass];

        let action = agent.select_action(&state, &db, 0);
        // Should be one of the legal Main-phase action kinds — not panic.
        assert!(matches!(
            action.kind,
            ActionKind::PlayCard
                | ActionKind::AttachEnergy
                | ActionKind::Evolve
                | ActionKind::UseAbility
                | ActionKind::Retreat
                | ActionKind::Attack
                | ActionKind::EndTurn
        ));
    }

    #[test]
    fn mcts_delegates_trivial_single_action() {
        // A Setup-phase state forces HeuristicAgent (via delegate_setup).
        // This test verifies the delegate_setup code path doesn't panic
        // and returns a legal setup placement.
        let db = Arc::new(CardDb::load_from_dir(&assets_dir()));
        let config = MctsConfig::default();
        let agent = MctsAgent::new(config, db.clone());

        let bulb = db.get_by_id("a1-001").expect("a1-001 not found");
        let mut state = GameState::new(1);
        state.phase = GamePhase::Setup;
        state.players[0].hand = vec![bulb.idx];

        let action = agent.select_action(&state, &db, 0);
        assert_eq!(action.kind, ActionKind::PlayCard);
    }
}
