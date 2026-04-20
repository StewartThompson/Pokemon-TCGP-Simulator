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
use super::features::{encode_into, encode_with_cache, FEATURE_DIM};
use super::net::{InferenceNet, ValueNet};

// Thread-local scratch buffer for zero-allocation feature encoding in the
// MCTS hot path. Each rayon worker gets its own buffer (thread_local is
// per-thread), so no synchronisation overhead even under heavy parallelism.
thread_local! {
    static FEATURE_BUF: std::cell::RefCell<[f32; FEATURE_DIM]> =
        std::cell::RefCell::new([0.0f32; FEATURE_DIM]);
}

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
    /// UCB1 exploration constant. Used in the bonus term
    /// `c * sqrt(ln(N) / n)` for visited edges.
    /// ~1.4 is the theoretical default; increase for more exploration.
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
    /// Inject Dirichlet noise into root edge priors during self-play.
    /// Disabled at eval time so the agent plays deterministically.
    pub use_dirichlet: bool,
    /// Concentration parameter for the Dirichlet distribution.
    /// AlphaZero uses α ≈ 0.3 for chess/Go; slightly higher values (0.5)
    /// give more exploration in a game with many short trees.
    pub dirichlet_alpha: f32,
    /// Fraction of the root prior that comes from Dirichlet noise.
    /// (1 - frac) comes from the uniform prior. AlphaZero default: 0.25.
    pub dirichlet_frac: f32,
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
            use_dirichlet: false,
            dirichlet_alpha: 0.3,
            dirichlet_frac: 0.25,
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
    /// Optional learned value net (Candle). Fallback when `inference_net` is
    /// absent. Kept for backward compatibility and training-time eval.
    pub net: Option<Arc<ValueNet>>,
    /// Pre-computed card embeddings. Built once from the `CardDb` and
    /// reused on every feature encoding during search — avoids rebuilding
    /// the cache on each hot-path call. Can be shared across agents via
    /// [`MctsAgent::with_embed_cache`] to avoid duplicate allocations.
    pub embed_cache: Arc<Vec<[f32; CARD_EMBED_DIM]>>,
    /// Pure-Rust inference net — zero allocation per call, no Candle tensors.
    /// When present, this takes priority over `net` for leaf evaluation.
    /// Build via [`ValueNet::to_inference_net`] and share via `Arc`.
    pub inference_net: Option<Arc<InferenceNet>>,
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
            inference_net: None,
        }
    }

    pub fn with_seed(mut self, seed: u64) -> Self {
        self.rng_seed = seed;
        self
    }

    /// Attach a Candle value net (fallback when `inference_net` is absent).
    pub fn with_net(mut self, net: Arc<ValueNet>) -> Self {
        self.net = Some(net);
        self
    }

    /// Attach a pure-Rust inference net. When present, leaf evaluation uses
    /// this instead of `net` — eliminating all Candle tensor overhead.
    ///
    /// Build with `ValueNet::to_inference_net()` after each training step and
    /// share via `Arc` across all rayon workers for the same generation.
    pub fn with_inference_net(mut self, inet: Arc<InferenceNet>) -> Self {
        self.inference_net = Some(inet);
        self
    }

    /// Replace the internally-built embed cache with a shared one. Use this
    /// when constructing many agents for the same `CardDb` (e.g. all rayon
    /// workers in a generation) to avoid duplicate allocations.
    pub fn with_embed_cache(mut self, cache: Arc<Vec<[f32; CARD_EMBED_DIM]>>) -> Self {
        self.embed_cache = cache;
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
            self.inference_net.as_deref(),
            self.net.as_deref(),
            self.embed_cache.as_slice(),
        );
        let root = tree.new_node(&search_state, db);
        tree.root = root;

        // Inject Dirichlet noise into root edge priors (training only).
        // This ensures different games explore different root actions first,
        // preventing the policy from collapsing to deterministic play.
        if self.config.use_dirichlet {
            let n = tree.nodes[root].children.len();
            if n > 1 {
                let noise = sample_dirichlet(
                    self.config.dirichlet_alpha,
                    n,
                    &mut SmallRng::seed_from_u64(per_call_seed.wrapping_add(0xD1D1_D1D1)),
                );
                let frac = self.config.dirichlet_frac;
                let uniform = 1.0 / n as f32;
                for (edge, &eta) in tree.nodes[root].children.iter_mut().zip(noise.iter()) {
                    edge.prior = (1.0 - frac) * uniform + frac * eta;
                }
            }
        }

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
    /// Prior probability for this edge (used in P-UCB exploration bonus).
    /// Initialised to uniform (1 / n_children). At the root during training,
    /// this is mixed with Dirichlet noise before any simulations run.
    prior: f32,
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
    /// Pure-Rust inference net (fast path). When present, `net` is ignored.
    inet: Option<&'a InferenceNet>,
    /// Candle value net (fallback when `inet` is absent).
    net: Option<&'a ValueNet>,
    /// Card-embed cache for feature encoding at value-net leaves.
    embed_cache: &'a [[f32; CARD_EMBED_DIM]],
}

impl<'a> Tree<'a> {
    fn new(
        root_player: usize,
        config: MctsConfig,
        seed: u64,
        inet: Option<&'a InferenceNet>,
        net: Option<&'a ValueNet>,
        embed_cache: &'a [[f32; CARD_EMBED_DIM]],
    ) -> Self {
        Self {
            nodes: Vec::with_capacity(256),
            root_player,
            root: 0,
            config,
            rng: SmallRng::seed_from_u64(seed),
            inet,
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
        let n = legal.len();
        let uniform_prior = if n > 0 { 1.0 / n as f32 } else { 1.0 };
        let children: Vec<Edge> = legal
            .into_iter()
            .map(|a| Edge {
                action: a,
                child: None,
                visits: 0,
                value_sum: 0.0,
                prior: uniform_prior,
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
        let is_root = node_idx == self.root;

        let mut best_idx = 0usize;
        let mut best_score = f64::NEG_INFINITY;

        for (i, edge) in node.children.iter().enumerate() {
            let score = if edge.visits == 0 {
                // Unvisited → must be explored before any visited edge.
                // At the root, use the Dirichlet-noised prior to randomise
                // which unvisited edge is tried first: higher prior ⟹
                // explored earlier. This gives each game a different root
                // exploration order without changing the UCB formula for
                // visited edges, preserving the proven UCB1 behaviour.
                // At non-root nodes we keep the original deterministic
                // index-based tiebreak (prior is uniform there, noise-free).
                if is_root {
                    f64::INFINITY + edge.prior as f64 * 1e-3
                } else {
                    f64::INFINITY - (i as f64) * 1e-12
                }
            } else {
                let mean = edge.value_sum / edge.visits as f64;
                // Flip sign at opponent nodes so UCB always maximises for
                // the player currently choosing.
                let q = if is_root_player { mean } else { -mean };
                // Standard UCB1 exploration term.
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
            // 2. Short heuristic rollout from the leaf to sharpen the estimate.
            // Must use Heuristic policy — Random rollouts are near-zero signal
            // in PTCGP (random vs random ≈ 50/50 from any state), which would
            // drown out the net value rather than complement it.
            let v_roll = self.do_rollout(state, db, rollout_depth, RolloutPolicy::Heuristic);
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
    /// player's perspective. Returns 0 when no net is attached.
    ///
    /// Training data (selfplay.rs) records BOTH players' decisions, each
    /// from their own POV with win_target = that player's outcome.  The net
    /// therefore learns: "given board features from the current mover's POV,
    /// predict whether the current mover wins."
    ///
    /// We encode from `current_player`'s POV here to match that training
    /// distribution.  The output is always "current_player wins probability",
    /// which we negate when current_player ≠ root_player to convert to
    /// root_player's perspective for backup.
    ///
    /// Fast path: when `self.inet` is set (pure-Rust weights), we write into
    /// a thread-local `[f32; FEATURE_DIM]` and call `inet.win_value` — zero
    /// heap allocation, no Candle tensors.  Fallback: use the Candle net via
    /// `encode_with_cache` + `win_value` (allocates a `Vec<f32>`).
    fn net_value(&self, state: &GameState, db: &CardDb) -> f64 {
        let current_player = whose_turn(state);

        // ── Fast path: InferenceNet (pure Rust, zero allocation) ──────────
        if let Some(inet) = self.inet {
            let v = FEATURE_BUF.with(|cell| {
                let mut buf = cell.borrow_mut();
                encode_into(state, db, current_player, self.embed_cache, &mut *buf);
                inet.win_value(&*buf) as f64
            });
            return if current_player == self.root_player { v } else { -v };
        }

        // ── Fallback: Candle ValueNet (allocates Vec<f32>) ────────────────
        if let Some(net) = self.net {
            let features = encode_with_cache(state, db, current_player, self.embed_cache);
            let v = net.win_value(&features).map(|v| v as f64).unwrap_or(0.0);
            return if current_player == self.root_player { v } else { -v };
        }

        0.0
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
            // Rollout hit the depth cap without a decisive result.
            // Prize-diff proxy: (my_prizes - opp_prizes) / 3.0, range [-1, +1].
            // We subtract a stall penalty (-0.25) to discourage the agent
            // from preferring stalling strategies over decisive attacks.
            // Matched to the draw value (-0.5): a rollout that hit the cap
            // with 0 prizes taken is slightly BETTER than a draw (the game
            // might still be won), but clearly worse than a decisive outcome.
            let p0 = state.players[0].points as f64;
            let p1 = state.players[1].points as f64;
            let diff = (p0 - p1) / 3.0;
            let stall_penalty = -0.25;
            let raw = if self.root_player == 0 { diff } else { -diff };
            (raw + stall_penalty).clamp(-1.0, 1.0)
        }
    }

    /// Update stats along the path.
    ///
    /// For each `(parent_node, edge_idx)` in `path`, we update both the edge
    /// counters and the child node's own counters. This keeps `node.visits`
    /// current so `ucb_select` computes the exploration term correctly at
    /// every depth — without it, non-root nodes have visits=0 forever, the
    /// `ln(N)` term collapses to zero, and UCB degenerates to pure greedy
    /// exploitation (no exploration at all).
    ///
    /// The root node is updated explicitly at the top; it does NOT get a
    /// second update from the first path entry because the path stores child
    /// pointers, not self pointers — root is never its own child.
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

// ------------------------------------------------------------------ //
// Dirichlet noise
// ------------------------------------------------------------------ //

/// Sample from a symmetric Dirichlet(α, k) distribution.
/// Returns a Vec of `k` values that sum to 1.0.
///
/// Uses the Gamma-distribution trick: sample k independent Gamma(α,1) r.v.s
/// and normalise. For α < 1 (our default is 0.3) we use the Ahrens-Dieter /
/// Marsaglia-Tsang "squeeze" method which is numerically stable for small α.
fn sample_dirichlet(alpha: f32, k: usize, rng: &mut SmallRng) -> Vec<f32> {
    let mut samples: Vec<f32> = (0..k).map(|_| sample_gamma(alpha, rng)).collect();
    let sum: f32 = samples.iter().sum();
    if sum > 0.0 {
        for s in &mut samples {
            *s /= sum;
        }
    } else {
        // Degenerate fallback — uniform distribution.
        for s in &mut samples {
            *s = 1.0 / k as f32;
        }
    }
    samples
}

/// Sample one value from Gamma(shape, scale=1) distribution.
///
/// For shape >= 1: Marsaglia-Tsang (2000), "A Simple Method for Generating
///   Gamma Variables", ACM TOMS 26(3). Very fast, requires ~2 Gaussian draws
///   on average.
///
/// For shape < 1 (our case, α=0.3): apply the boost identity
///   Gamma(α) = Gamma(α+1) · U^(1/α)  where U ~ Uniform(0,1)
///   This converts an under-unit problem to a ≥1 problem.
fn sample_gamma(shape: f32, rng: &mut SmallRng) -> f32 {
    if shape < 1.0 {
        // Boost: Gamma(α) = Gamma(α+1) * U^(1/α)
        let u: f32 = rng.gen();
        sample_gamma(shape + 1.0, rng) * u.powf(1.0 / shape)
    } else {
        // Marsaglia-Tsang for shape >= 1.
        let d = (shape - 1.0 / 3.0) as f64;
        let c = (1.0 / (9.0 * d).sqrt()) as f64;
        loop {
            // Draw a standard normal via Box-Muller.
            let u1: f64 = rng.gen::<f64>().max(1e-12);
            let u2: f64 = rng.gen::<f64>().max(1e-12);
            let x = (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos();
            let v = (1.0 + c * x).powi(3);
            if v <= 0.0 {
                continue;
            }
            let u: f64 = rng.gen();
            // Marsaglia squeeze test — accepts ~98% of proposals.
            if u < 1.0 - 0.0331 * x.powi(4) {
                return (d * v) as f32;
            }
            if u.ln() < 0.5 * x * x + d * (1.0 - v + v.ln()) {
                return (d * v) as f32;
            }
        }
    }
}

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
        // Draw (turn limit hit, Some(-1)) or ongoing: moderately negative.
        // A draw means you never won — equivalent to a half-loss.
        // With 0.0 (neutral), MCTS treats stalling (expected draw) as
        // equivalent to an evenly-contested attack (EV ≈ 0), so both
        // MCTS agents stall into the turn limit (~65-74% draw rate on
        // slow decks). Setting -0.5 makes attacking strictly preferred in
        // any position where the expected win probability exceeds 25%.
        _ => -0.5,
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
    // After a Promote that resolved an attack-induced KO, the attacker's
    // turn ends (mirrors runner.rs). Without this the attacker would get to
    // act again after the defender promoted from bench.
    if kind == ActionKind::Promote
        && state.attack_pending_advance
        && state.phase == GamePhase::Main
        && state.winner.is_none()
    {
        turn::advance_turn(state, db);
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
        state.players[0].energy_types = smallvec::smallvec![crate::types::Element::Grass];
        state.players[1].energy_types = smallvec::smallvec![crate::types::Element::Grass];

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
        state.players[0].hand = smallvec::smallvec![bulb.idx];

        let action = agent.select_action(&state, &db, 0);
        assert_eq!(action.kind, ActionKind::PlayCard);
    }
}
