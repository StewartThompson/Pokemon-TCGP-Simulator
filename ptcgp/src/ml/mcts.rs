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
use std::sync::atomic::{AtomicU32, Ordering};

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
use crate::engine::{ko, mutations, setup, turn};
use crate::state::GameState;
use crate::types::{ActionKind, CardKind, GamePhase, Stage};
use crate::constants::POINTS_TO_WIN;

use super::card_embed::{build_embed_cache, CARD_EMBED_DIM};
use super::determinize::determinize_for;
use super::features::{encode_into, encode_with_cache, FEATURE_DIM};
use super::net::{InferenceNet, ValueNet, MAX_POLICY_SIZE};

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
    /// When `determinizations > 1`, this budget is split evenly across all
    /// determinizations (e.g. 240 sims with 4 determinizations = 60 each).
    pub total_sims: usize,
    /// Number of independent determinizations (PIMC).
    ///
    /// Each determinization samples a fresh opponent hand from the pool of
    /// unknown cards and builds a separate MCTS tree. After all trees are
    /// searched, visit counts are *summed* across determinizations to produce
    /// the final action distribution.
    ///
    /// K=1 is the Wave 1 single-determinization behaviour. K=4 is a strong
    /// default that handles hidden information much better at the same total
    /// sim budget (each tree gets `total_sims / determinizations` sims).
    ///
    /// Reference: "Information Set Monte Carlo Tree Search" (Cowling et al.)
    pub determinizations: usize,
    /// P-UCT exploration constant (AlphaZero-style).
    ///
    /// Used in `c_puct * P(s,a) * sqrt(N_parent) / (1 + N(s,a))`.
    /// Unlike UCB1, the prior P(s,a) continuously scales the bonus, so
    /// high-prior actions (KO attacks, evolves) receive proportionally more
    /// exploration budget throughout the search. ~1.4 is the standard default.
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
    /// Use the neural network's policy logits as P-UCT priors in `new_node()`.
    ///
    /// When `false` (the default), heuristic domain-knowledge priors are used
    /// regardless of whether an inference net is attached. The policy head is
    /// still *trained* on MCTS visit distributions when false — it just isn't
    /// *used* for search yet.
    ///
    /// Set to `true` once the policy head is well-calibrated (typically after
    /// 20-30 gens) to use informed network priors for P-UCT selection. Using
    /// random network priors before training degrades search quality because
    /// with only 240 sims, bad priors significantly distort visit distributions.
    pub use_network_priors: bool,
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
    /// Temperature for sharpening MCTS visit-count distributions before using
    /// them as policy training targets.
    ///
    /// `policy_target[a] ∝ N(a)^(1/τ)` — lower τ = sharper / more peaked.
    ///
    /// With 240 sims the raw visit distribution is only mildly concentrated
    /// (~60% on the best action), giving a CE target whose entropy is close to
    /// `log(n_legal)`. This leaves almost no gradient for the policy head to
    /// climb. Sharpening amplifies the signal:
    ///
    /// | τ    | effective power | typical best-action mass (4 actions) |
    /// |------|-----------------|--------------------------------------|
    /// | 1.0  | raw visits      | ~60%   (original; weak gradient)     |
    /// | 0.5  | visits²         | ~90%   (recommended)                 |
    /// | 0.25 | visits⁴         | ~99%   (aggressive)                  |
    ///
    /// `τ = 0.5` (squaring visits) is the recommended default. It gives a
    /// clear best-action signal without collapsing to hard argmax, which would
    /// ignore the relative merits of second-best moves.
    ///
    /// Set to 1.0 to restore the original unsharpened behaviour.
    pub policy_target_tau: f32,
}

impl Default for MctsConfig {
    fn default() -> Self {
        Self {
            total_sims: 500,
            determinizations: 1,
            c_puct: 1.4,
            temperature: 0.0,
            leaf_value_source: LeafValue::RandomRollout,
            rollout_depth_cap: 200,
            delegate_trivial: true,
            delegate_setup: true,
            use_network_priors: false,
            use_dirichlet: false,
            dirichlet_alpha: 0.3,
            dirichlet_frac: 0.25,
            policy_target_tau: 0.5,
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
    /// Stores the f32 bits of the root Q-value from the most recent
    /// `select_action` call. AtomicU32 (not `Cell<f32>`) keeps `MctsAgent`
    /// `Sync` — required by `RecordingAgent`'s `&dyn Agent + Send + Sync`.
    ///
    /// Reset to `f32::NAN` at the top of each call; written after all sims
    /// complete. Fast-path calls (setup, trivial 1-action) leave NaN, which
    /// `last_root_q()` converts to `None` so callers can distinguish "no
    /// search ran" from a genuine near-zero Q value.
    last_root_q_bits: AtomicU32,
    /// Stores the policy target (MCTS visit-count distribution over
    /// [`MAX_POLICY_SIZE`] action slots) and legal mask from the most recent
    /// `select_action` call. Cleared to `None` at the top of each call so
    /// fast-path returns leave `None` (no search ran, no useful policy signal).
    ///
    /// [`RecordingAgent`](crate::ml::selfplay::RecordingAgent) reads this via
    /// the [`PolicySource`] trait to build AlphaZero-style policy supervision
    /// targets for the training samples.
    last_policy_data: std::sync::Mutex<Option<([f32; MAX_POLICY_SIZE], [f32; MAX_POLICY_SIZE])>>,
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
            last_root_q_bits: AtomicU32::new(f32::NAN.to_bits()),
            last_policy_data: std::sync::Mutex::new(None),
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
        // Reset sentinels so fast-path returns are distinguishable from genuine
        // search results. NaN Q → last_root_q() returns None. None policy →
        // last_policy_target() returns None (no useful supervision signal).
        self.last_root_q_bits.store(f32::NAN.to_bits(), Ordering::Relaxed);
        if let Ok(mut pd) = self.last_policy_data.lock() {
            *pd = None;
        }

        // Fast path 1a: bench-filling sub-phase of Setup → heuristic.
        // When active is already chosen, bench placement is trivially greedy
        // (place everything you have). Not a strategic decision worth searching.
        //
        // Fast path 1b: AwaitingBenchPromotion → heuristic.
        // After a KO, the player must promote a benched Pokémon. The choice
        // matters but promotion options are usually limited (1-3 bench slots),
        // and the right choice is almost always "the strongest Pokémon" which
        // the heuristic handles correctly.
        //
        // NOTE: Setup active-selection (no active yet) is intentionally NOT
        // fast-pathed here. Choosing which Pokémon leads is strategically
        // important — the wrong active choice (a fragile basic when you hold
        // an EX) can lose the game. MCTS will search it with the remaining
        // budget below.
        if self.config.delegate_setup {
            let is_bench_fill = state.phase == GamePhase::Setup
                && state.players[player_idx].active.is_some();
            if is_bench_fill || state.phase == GamePhase::AwaitingBenchPromotion {
                return HeuristicAgent.select_action(state, db, player_idx);
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

        // Fast path 3: instant-win attack. If any attack in the legal set
        // guarantees a KO that wins the game this turn, take it immediately —
        // no search needed. Conditions (conservative):
        //   a) my_points + opp_active.ko_points >= POINTS_TO_WIN
        //   b) attack.damage + my_damage_bonus >= opp_active.current_hp
        //      (we use the raw base damage only, no weakness, no coin flips —
        //       so this only fires when the kill is certain, not hopeful)
        if state.phase == GamePhase::Main {
            if let Some(win_attack) = find_winning_attack(&legal, state, &self.db) {
                return win_attack;
            }
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

        // PIMC: run K determinizations and aggregate visit counts.
        //
        // Each determinization samples a fresh opponent hand so the search
        // averages over hidden-information uncertainty rather than committing
        // to a single guess. For K=1 this is identical to the old single-
        // determinization behaviour (zero overhead).
        //
        // Root legal actions are the SAME across all determinizations because
        // they depend only on the acting player's own board/hand, not the
        // opponent's hidden cards. We therefore aggregate visit counts by
        // position index across all K root nodes.
        let n_det = self.config.determinizations.max(1);
        let sims_per_det = (self.config.total_sims + n_det - 1) / n_det;

        // Aggregated visit counts per root action (index → total visits).
        let n_actions = legal.len();
        let mut total_visits: Vec<u32> = vec![0u32; n_actions];
        let mut total_q: f64 = 0.0;

        for k in 0..n_det {
            // Different seed per determinization → different opponent hand samples.
            let det_seed = per_call_seed
                .wrapping_add(k as u64)
                .wrapping_mul(0x9E37_79B9_7F4A_7C15_u64)
                .wrapping_add(0x6C62_272E_07BB_0142_u64);
            let search_state = determinize_for(state, player_idx, det_seed);

            let mut tree = Tree::new(
                player_idx,
                self.config.clone(),
                det_seed,
                self.inference_net.as_deref(),
                self.net.as_deref(),
                self.embed_cache.as_slice(),
            );
            let root = tree.new_node(&search_state, db);
            tree.root = root;

            // Inject Dirichlet noise into root edge priors (training only).
            // Applied per-determinization so each tree explores independently.
            if self.config.use_dirichlet {
                let n = tree.nodes[root].children.len();
                if n > 1 {
                    let noise = sample_dirichlet(
                        self.config.dirichlet_alpha,
                        n,
                        &mut SmallRng::seed_from_u64(det_seed.wrapping_add(0xD1D1_D1D1)),
                    );
                    let frac = self.config.dirichlet_frac;
                    for (edge, &eta) in tree.nodes[root].children.iter_mut().zip(noise.iter()) {
                        edge.prior = (1.0 - frac) * edge.prior + frac * eta;
                    }
                }
            }

            for i in 0..sims_per_det {
                let mut sim_state = search_state.clone();
                // Each sim gets a fresh RNG so coin flips / energy gen aren't lock-stepped.
                sim_state.rng = SmallRng::seed_from_u64(det_seed.wrapping_add(i as u64));
                tree.simulate(root, &mut sim_state, db);
            }

            // Accumulate visit counts from this determinization's root.
            for (j, edge) in tree.nodes[root].children.iter().enumerate() {
                if j < n_actions {
                    total_visits[j] += edge.visits;
                }
            }
            total_q += tree.root_q() as f64;
        }

        // Store averaged root Q across all determinizations.
        let avg_q = (total_q / n_det as f64).clamp(-1.0, 1.0) as f32;
        self.last_root_q_bits.store(avg_q.to_bits(), Ordering::Relaxed);

        // Compute and store the AlphaZero-style policy supervision target.
        // This is the normalized visit-count distribution over MAX_POLICY_SIZE
        // canonical action slots. RecordingAgent reads it via PolicySource to
        // attach dense per-move supervision to each training sample.
        //
        // Temperature sharpening: `policy_target[a] ∝ N(a)^(1/τ)`.
        // With τ=0.5 (default) we square visit counts before normalizing,
        // amplifying the best-action signal from ~60% to ~90% for a typical
        // 4-action, 240-sim tree.  This gives the policy head a much stronger
        // gradient than raw visit fractions, which are near-uniform at low
        // sim counts.  τ=1.0 restores original unsharpened behaviour.
        //
        // Must happen BEFORE `legal.into_iter()` consumes the vector.
        {
            let total_v: u32 = total_visits.iter().sum();
            if total_v > 0 {
                let tau = self.config.policy_target_tau.max(1e-4);
                let inv_tau = 1.0 / tau;
                // Apply temperature: sharpened[i] = visits[i]^(1/τ)
                let sharpened: Vec<f32> = total_visits
                    .iter()
                    .map(|&v| (v as f32).powf(inv_tau))
                    .collect();
                let sum_sharp: f32 = sharpened.iter().sum();
                if sum_sharp > 0.0 {
                    let mut policy_target = [0.0f32; MAX_POLICY_SIZE];
                    let mut policy_legal  = [0.0f32; MAX_POLICY_SIZE];
                    for (j, action) in legal.iter().enumerate() {
                        if j < sharpened.len() {
                            let idx = action_to_policy_idx(action);
                            policy_legal[idx] = 1.0;
                            policy_target[idx] += sharpened[j] / sum_sharp;
                        }
                    }
                    if let Ok(mut pd) = self.last_policy_data.lock() {
                        *pd = Some((policy_target, policy_legal));
                    }
                }
            }
        }

        // Pick action from aggregated visit counts using temperature policy.
        let t = self.config.temperature;
        if t < 1e-6 {
            // Argmax: deterministic play.
            let best_idx = total_visits
                .iter()
                .enumerate()
                .max_by_key(|(_, &v)| v)
                .map(|(i, _)| i)
                .unwrap_or(0);
            legal.into_iter().nth(best_idx).unwrap_or(Action::end_turn())
        } else {
            // Temperature sampling: proportional to visits^(1/T).
            let inv_t = 1.0 / t as f64;
            let weights: Vec<f64> = total_visits
                .iter()
                .map(|&v| (v as f64).powf(inv_t))
                .collect();
            let total_w: f64 = weights.iter().sum();
            if total_w <= 0.0 {
                return legal.into_iter().next().unwrap_or(Action::end_turn());
            }
            let mut rng = SmallRng::seed_from_u64(per_call_seed.wrapping_add(0xABCD_1234_5678_u64));
            let mut r: f64 = rng.gen_range(0.0..total_w);
            let mut chosen = Action::end_turn();
            for (action, &w) in legal.into_iter().zip(weights.iter()) {
                r -= w;
                chosen = action;
                if r <= 0.0 {
                    break;
                }
            }
            chosen
        }
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

    /// Create a node for the given state. Populates its edges with legal actions
    /// and assigns heuristic prior probabilities (normalized to sum to 1.0).
    ///
    /// # Heuristic priors
    ///
    /// During Main phase, actions are scored by domain knowledge:
    /// - Attack-for-KO:       3.5 × (end the game immediately)
    /// - High-damage attack:  2.0 × (attack does ≥ half opp HP)
    /// - Evolve:              2.5 × (always a strong progression signal)
    /// - Generic attack:      1.5 × (attacking beats not attacking)
    /// - Attach to active:    1.5 × (power up the fighting Pokémon)
    /// - UseAbility:          1.2 ×
    /// - Attach to bench:     1.1 ×
    /// - PlayCard / Promote:  1.0 × (neutral)
    /// - Retreat:             0.7 ×
    /// - EndTurn:             0.4 × (last resort)
    ///
    /// These scores are normalized so they sum to 1.0 before storage,
    /// matching the UCB P-exploration term convention. During Setup /
    /// AwaitingBenchPromotion phases (which delegate to HeuristicAgent anyway)
    /// uniform priors are used instead.
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

        // Compute normalized priors for each legal action.
        //
        // Priority:
        //  1. Network policy logits — only when `config.use_network_priors` is
        //     true AND an InferenceNet is attached. Off by default: using random
        //     network priors early in training degrades search quality because
        //     at 240 sims the priors still strongly influence UCB selection.
        //     Enable once the policy head is calibrated (~20-30 gens).
        //  2. Heuristic scores — stable domain-knowledge priors. Always used
        //     when (1) is disabled.
        //  3. Uniform — non-Main phases delegated to HeuristicAgent anyway.
        let priors: Vec<f32> = if n == 0 {
            Vec::new()
        } else if state.phase != GamePhase::Main {
            vec![1.0 / n as f32; n]
        } else if self.config.use_network_priors {
            if let Some(inet) = self.inet {
                // Network policy priors: single inference call per new node.
                // Returns a masked-softmax distribution over legal action slots.
                let pidxs: Vec<usize> = legal.iter().map(|a| action_to_policy_idx(a)).collect();
                FEATURE_BUF.with(|cell| {
                    let mut buf = cell.borrow_mut();
                    encode_into(state, db, pi, self.embed_cache, &mut *buf);
                    let (_, logits) = inet.win_and_policy(&*buf);
                    InferenceNet::softmax_masked(&logits, &pidxs)
                })
            } else {
                // use_network_priors=true but no inet attached — fall back to heuristic.
                let mut scores: Vec<f32> = legal
                    .iter()
                    .map(|a| action_prior_score(a, state, db, pi))
                    .collect();
                let total: f32 = scores.iter().sum();
                let inv = if total > 0.0 { 1.0 / total } else { 1.0 / n as f32 };
                for s in &mut scores { *s *= inv; }
                scores
            }
        } else {
            // Heuristic priors (default): stable, domain-informed, no feedback instability.
            let mut scores: Vec<f32> = legal
                .iter()
                .map(|a| action_prior_score(a, state, db, pi))
                .collect();
            let total: f32 = scores.iter().sum();
            let inv = if total > 0.0 {
                1.0 / total
            } else {
                1.0 / n as f32
            };
            for s in &mut scores {
                *s *= inv;
            }
            scores
        };

        let children: Vec<Edge> = legal
            .into_iter()
            .zip(priors)
            .map(|(a, p)| Edge {
                action: a,
                child: None,
                visits: 0,
                value_sum: 0.0,
                prior: p,
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
        let sqrt_parent = parent_visits.sqrt();
        let is_root_player = node.player_to_move as usize == self.root_player;

        let mut best_idx = 0usize;
        let mut best_score = f64::NEG_INFINITY;

        for (i, edge) in node.children.iter().enumerate() {
            let score = if edge.visits == 0 {
                // Unvisited → must be explored before any visited edge.
                // Tiebreak by prior: higher-prior actions (KO attacks, evolves)
                // are explored first, matching the P-UCT formula's intent.
                f64::INFINITY + edge.prior as f64 * 1e-3
            } else {
                let mean = edge.value_sum / edge.visits as f64;
                // Flip sign at opponent nodes so UCB always maximises for
                // the player currently choosing.
                let q = if is_root_player { mean } else { -mean };
                // AlphaZero P-UCT: prior-weighted exploration bonus.
                //   U(s,a) = c_puct * P(s,a) * sqrt(N_parent) / (1 + N(s,a))
                //
                // Unlike UCB1 (which ignores the prior after first visit),
                // P-UCT continuously weights exploration by P(s,a). This means
                // KO attacks and evolves keep getting proportionally more budget
                // throughout the search, not just when unvisited.
                let u = self.config.c_puct
                    * edge.prior as f64
                    * sqrt_parent
                    / (1.0 + edge.visits as f64);
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
        // If the simulation reached (or started from) Setup phase, fast-forward
        // to Main phase using the heuristic before rolling out. This handles the
        // case where MCTS is called during active selection at game start.
        if state.phase == GamePhase::Setup {
            advance_through_setup(state, db);
        }
        if state.winner.is_some() || state.phase == GamePhase::GameOver {
            return value_for_root(state, self.root_player);
        }

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

    /// Mean backed-up value at the root after all simulations. Returns a value
    /// in [-1, +1] from the root player's perspective. Used by
    /// [`RootQSource`] to supply a lower-variance training target.
    fn root_q(&self) -> f32 {
        let root = &self.nodes[self.root];
        if root.visits == 0 {
            return 0.0;
        }
        (root.value_sum / root.visits as f64).clamp(-1.0, 1.0) as f32
    }

}

// ------------------------------------------------------------------ //
// RootQSource — extract MCTS Q for training label blending
// ------------------------------------------------------------------ //

/// Read the root Q-value from the most recent [`MctsAgent::select_action`] call.
///
/// MCTS root Q = `value_sum / visits` after N simulations — the average
/// backed-up win probability. It has variance ~1/N (vs 1/1 for the game
/// outcome), so blending it with the game outcome as the win target
/// substantially reduces label noise without introducing bias.
///
/// [`RecordingAgent`](crate::ml::selfplay::RecordingAgent) queries this after
/// each `select_action` call and stores the result alongside the features so
/// [`play_training_game`](crate::ml::selfplay::play_training_game) can blend
/// it into the final `win_target`.
pub trait RootQSource: Send + Sync {
    /// The mean backed-up value at the search root from the acting player's
    /// perspective, in [-1, +1]. Returns `None` when no full MCTS search ran
    /// for this decision (fast-path moves: setup phase, single legal action).
    fn last_root_q(&self) -> Option<f32>;
}

impl RootQSource for MctsAgent {
    fn last_root_q(&self) -> Option<f32> {
        let bits = self.last_root_q_bits.load(Ordering::Relaxed);
        let q = f32::from_bits(bits);
        // NaN is the sentinel written at the top of select_action for fast
        // paths that skip the full search.
        if q.is_nan() { None } else { Some(q) }
    }
}

// ------------------------------------------------------------------ //
// PolicySource — AlphaZero-style visit-count supervision signal
// ------------------------------------------------------------------ //

/// Provide the MCTS visit-count policy distribution from the most recent
/// [`MctsAgent::select_action`] call.
///
/// Returns `(policy_target, policy_legal)`:
/// - `policy_target[i]` is the fraction of total visits that went to canonical
///   action slot `i`. Sums to 1.0 over legal slots.
/// - `policy_legal[i]` is 1.0 if slot `i` was a legal action in this state,
///   0.0 otherwise.
///
/// [`RecordingAgent`](crate::ml::selfplay::RecordingAgent) queries this after
/// each `select_action` call and attaches the data to the training sample so
/// the policy head can be trained with cross-entropy against this distribution.
pub trait PolicySource: Send + Sync {
    /// The visit-count distribution and legal mask, or `None` when no full
    /// MCTS search ran (fast-path moves: setup phase, single legal action).
    fn last_policy_target(&self) -> Option<([f32; MAX_POLICY_SIZE], [f32; MAX_POLICY_SIZE])>;
}

impl PolicySource for MctsAgent {
    fn last_policy_target(&self) -> Option<([f32; MAX_POLICY_SIZE], [f32; MAX_POLICY_SIZE])> {
        self.last_policy_data.lock().ok().and_then(|g| *g)
    }
}

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //

/// Check whether any legal attack action is a guaranteed game-winning KO.
///
/// Returns the first attack action that:
/// 1. KOs the opponent's active Pokémon (base damage + my bonus ≥ opp HP).
///    We use only guaranteed damage (no coin-flip bonus, no weakness) so the
///    fast path only fires when the kill is certain.
/// 2. The resulting KO points push our total to ≥ POINTS_TO_WIN.
///
/// When both conditions hold, there is no strategic decision left — just
/// take the kill. Skipping the full MCTS search here saves the entire sim
/// budget (e.g. 240 simulations × tree overhead) with zero quality loss.
fn find_winning_attack(actions: &[Action], state: &GameState, db: &CardDb) -> Option<Action> {
    let pi = state.current_player;
    let my_points = state.players[pi].points;
    let Some(my_active) = state.players[pi].active.as_ref() else {
        return None;
    };
    let Some(opp_active) = state.players[1 - pi].active.as_ref() else {
        return None;
    };
    let bonus = state.players[pi].attack_damage_bonus as i16
        + my_active.attack_bonus_next_turn_self as i16;
    let opp_ko_points = db.get_by_idx(opp_active.card_idx).ko_points;

    // Only fast-path when this KO would actually win.
    if (my_points + opp_ko_points) < POINTS_TO_WIN {
        return None;
    }

    for action in actions {
        if action.kind != ActionKind::Attack {
            continue;
        }
        let Some(attack_idx) = action.attack_index else {
            continue;
        };
        let my_card = db.get_by_idx(my_active.card_idx);
        let Some(attack) = my_card.attacks.get(attack_idx) else {
            continue;
        };
        let guaranteed_dmg = attack.damage + bonus;
        // Only take the fast path when the KO is certain (no coin-flip luck
        // needed). Adding weakness would risk over-committing when the
        // opponent doesn't actually have the weakness.
        if guaranteed_dmg > 0 && guaranteed_dmg >= opp_active.current_hp {
            return Some(action.clone());
        }
    }
    None
}

/// Map any legal [`Action`] to a canonical policy slot index in
/// `[0, MAX_POLICY_SIZE)`.
///
/// The mapping is deterministic and stable across game states. All PTCGP
/// action kinds fit within 32 slots (MAX_POLICY_SIZE), leaving slots 27-31
/// as reserved expansion space:
///
/// | Slots  | Action kind                                     |
/// |--------|-------------------------------------------------|
/// | 0      | EndTurn                                         |
/// | 1–2    | Attack[0], Attack[1]                            |
/// | 3–5    | Retreat → bench[0], bench[1], bench[2]          |
/// | 6–8    | Promote → bench[0], bench[1], bench[2]          |
/// | 9–12   | AttachEnergy → active, bench[0], bench[1], bench[2] |
/// | 13–16  | UseAbility  → active, bench[0], bench[1], bench[2] |
/// | 17–26  | PlayCard / Evolve from hand[0..9]               |
/// | 27–31  | (reserved)                                      |
pub fn action_to_policy_idx(action: &Action) -> usize {
    // Bench-only target: Retreat/Promote always reference bench slot 0–2.
    let bench_slot = |t: Option<crate::actions::SlotRef>| -> usize {
        t.map(|s| (s.slot.max(0) as usize).min(2)).unwrap_or(0)
    };
    // Active-or-bench target: active (slot=-1) → 0, bench[0] → 1, bench[1] → 2, bench[2] → 3.
    let active_bench_slot = |t: Option<crate::actions::SlotRef>| -> usize {
        t.map(|s| {
            let idx = (s.slot as i16 + 1).max(0) as usize;
            idx.min(3)
        }).unwrap_or(0)
    };
    match action.kind {
        ActionKind::EndTurn     => 0,
        ActionKind::Attack      => 1 + action.attack_index.unwrap_or(0).min(1),
        ActionKind::Retreat     => 3 + bench_slot(action.target),
        ActionKind::Promote     => 6 + bench_slot(action.target),
        ActionKind::AttachEnergy => 9 + active_bench_slot(action.target),
        ActionKind::UseAbility  => 13 + active_bench_slot(action.target),
        ActionKind::PlayCard | ActionKind::Evolve => {
            // Slots 17–26 cover hand positions 0–9.
            // PTCGP has no hand limit, but hands exceeding 9 cards are rare
            // in practice. Cards at index ≥10 collapse to slot 26, which
            // corrupts the policy target for those positions.
            // TODO: extend MAX_POLICY_SIZE when a larger net is trained.
            debug_assert!(
                action.hand_index.unwrap_or(0) <= 9,
                "hand_index {} overflows policy slots (max 9)",
                action.hand_index.unwrap_or(0)
            );
            17 + action.hand_index.unwrap_or(0).min(9)
        }
    }
}

/// Domain-informed prior score for a single legal action.
///
/// Scores are **unnormalized** — `new_node` normalizes them to sum to 1.0.
/// The goal is not to be perfect, but to focus the MCTS budget away from
/// obviously-bad actions (EndTurn when a KO is available) toward high-value
/// ones (KO attacks, evolutions).
///
/// Called once per legal action during node expansion (the cold path, not
/// the UCB selection loop), so a small amount of state inspection is fine.
fn action_prior_score(action: &Action, state: &GameState, db: &CardDb, pi: usize) -> f32 {
    match action.kind {
        ActionKind::Attack => {
            let Some(attack_idx) = action.attack_index else {
                return 1.0;
            };
            let Some(my_active) = state.players[pi].active.as_ref() else {
                return 1.0;
            };
            let my_card = db.get_by_idx(my_active.card_idx);
            let Some(attack) = my_card.attacks.get(attack_idx) else {
                return 1.0;
            };
            let bonus = state.players[pi].attack_damage_bonus as i16
                + my_active.attack_bonus_next_turn_self as i16;
            let base_dmg = attack.damage + bonus;
            if base_dmg <= 0 {
                // Zero-damage attack (pure-effect move): treat as neutral
                return 1.0;
            }
            if let Some(opp_active) = state.players[1 - pi].active.as_ref() {
                // Be generous: include +20 for potential weakness bonus so we
                // don't suppress attacks that are close to a KO.
                let effective_dmg = base_dmg + 20;
                if effective_dmg >= opp_active.current_hp {
                    return 3.5; // Can KO the opponent's active Pokémon
                }
                if base_dmg * 2 >= opp_active.current_hp {
                    return 2.0; // High-damage (≥ half of opponent's remaining HP)
                }
            }
            1.5 // Generic damaging attack
        }
        ActionKind::Evolve => 2.5,
        ActionKind::AttachEnergy => {
            // Attaching to the active Pokémon charges the attacker now;
            // attaching to a benched Pokémon is future setup.
            match action.target {
                Some(t) if t.is_active() => 1.5,
                _ => 1.1,
            }
        }
        ActionKind::UseAbility => 1.2,
        ActionKind::PlayCard => 1.0, // trainer, item, or basic to bench
        ActionKind::Retreat => 0.7,
        ActionKind::EndTurn => 0.4,
        ActionKind::Promote => 1.0, // forced after KO — neutral
    }
}

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

/// Advance a game state that is still in `GamePhase::Setup` through to
/// `GamePhase::Main` using the HeuristicAgent for all remaining decisions.
///
/// Called by MCTS rollouts that start from (or land in) a Setup state. The
/// MCTS root decision (which Pokémon to place as active) has already been
/// reflected in the state by the time `rollout` runs — this function
/// completes whatever setup steps remain and calls `finalize_setup`.
///
/// Steps handled:
/// 1. If either player still needs an active Pokémon, pick one via heuristic.
/// 2. Bench-fill both players via heuristic (optional but greedy is fine).
/// 3. Call `setup::finalize_setup` → transitions phase to Main, starts turn 0.
fn advance_through_setup(state: &mut GameState, db: &CardDb) {
    // Step 1: ensure both players have an active Pokémon.
    for pi in 0..2 {
        if state.players[pi].active.is_none() {
            let legal = get_legal_setup_placements(state, db, pi);
            if legal.is_empty() {
                continue;
            }
            // Use heuristic to pick the best active Pokémon.
            let action = HeuristicAgent.select_action(state, db, pi);
            let hand_idx = action
                .hand_index
                .filter(|&i| i < state.players[pi].hand.len())
                .unwrap_or_else(|| legal[0].hand_index.unwrap_or(0));
            setup::apply_setup_placement(state, db, pi, hand_idx, &[]);
        }
    }

    // Step 2: bench-fill both players (greedy — always fill if possible).
    for pi in 0..2 {
        loop {
            let opts = get_legal_setup_bench_placements(state, db, pi);
            // Only placements (not EndTurn) are interesting.
            let placements: Vec<_> = opts
                .iter()
                .filter(|a| a.kind != ActionKind::EndTurn)
                .collect();
            if placements.is_empty() {
                break;
            }
            // Heuristic picks among the bench-placement actions.
            let action = HeuristicAgent.select_action(state, db, pi);
            if action.kind == ActionKind::EndTurn {
                break;
            }
            if let (Some(hi), Some(target)) = (action.hand_index, action.target) {
                if target.is_bench() {
                    let bench_idx = target.bench_index();
                    if state.players[pi].bench[bench_idx].is_none()
                        && hi < state.players[pi].hand.len()
                    {
                        let card_idx = state.players[pi].hand[hi];
                        let card = db.get_by_idx(card_idx);
                        let slot = crate::state::PokemonSlot::new(card_idx, card.hp);
                        state.players[pi].bench[bench_idx] = Some(slot);
                        state.players[pi].hand.remove(hi);
                        continue;
                    }
                }
            }
            break; // couldn't apply action, stop
        }
    }

    // Step 3: finalize setup → phase transitions to Main, turn counter starts.
    setup::finalize_setup(state, db);
}

/// Legal actions for whatever phase the state is in, with MCTS-specific
/// deduplication applied in Main phase:
///
/// **Bench slot deduplication**: placing a basic Pokémon from hand generates
/// one action per empty bench slot (slot 0, 1, 2). All three are strategically
/// identical in PTCGP — which slot a Pokémon occupies doesn't affect gameplay.
/// We collapse them to just one action (the first available slot). This can
/// reduce the action count from ~15 to ~10 for a typical hand, giving MCTS
/// proportionally more simulations per meaningful decision.
///
/// Note: items that target a bench slot (e.g. Potion on bench[0] vs bench[1])
/// ARE kept as distinct actions — those targets are meaningful choices.
fn legal_for_phase(state: &GameState, db: &CardDb, player_idx: usize) -> Vec<Action> {
    let raw = match state.phase {
        GamePhase::Setup => {
            if state.players[player_idx].active.is_some() {
                get_legal_setup_bench_placements(state, db, player_idx)
            } else {
                get_legal_setup_placements(state, db, player_idx)
            }
        }
        GamePhase::AwaitingBenchPromotion => get_legal_promotions(state, player_idx),
        GamePhase::GameOver => return Vec::new(),
        GamePhase::Main => get_legal_actions(state, db),
    };

    if state.phase != GamePhase::Main {
        return raw;
    }

    // Dedup basic-Pokémon bench placements. For each hand card that is a
    // basic Pokémon, keep only the first bench-targeting PlayCard action.
    // Items/Supporters with bench targets are distinct choices and kept as-is.
    let hand = &state.players[player_idx].hand;
    let mut seen_basic_bench: std::collections::HashSet<usize> = Default::default();
    raw.into_iter()
        .filter(|a| {
            if a.kind != ActionKind::PlayCard {
                return true;
            }
            let Some(hi) = a.hand_index else {
                return true;
            };
            let Some(target) = a.target else {
                return true;
            };
            // Only deduplicate bench targets owned by the current player.
            if !target.is_bench() || target.player as usize != player_idx {
                return true;
            }
            // Only collapse if the card is a Basic Pokémon.
            let Some(&card_idx) = hand.get(hi) else {
                return true;
            };
            let card = db.get_by_idx(card_idx);
            if card.kind == CardKind::Pokemon && card.stage == Some(Stage::Basic) {
                seen_basic_bench.insert(hi) // false on 2nd+ occurrence → filtered out
            } else {
                true // non-Pokémon card targeting a bench slot: meaningful choice, keep
            }
        })
        .collect()
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
/// Apply an action to the game state and run any necessary post-action
/// bookkeeping (KO checks, turn advance, etc.).
///
/// Mirrors the logic in `runner::run_main_loop` (around the Attack branch)
/// so MCTS plays states forward consistently with real games.
///
/// Setup phase: `mutations::apply_action` doesn't handle Setup active
/// selection (PlayCard with no bench target). Route those through
/// `setup::apply_setup_placement` instead.
fn apply_and_settle(state: &mut GameState, db: &CardDb, action: &Action) {
    // Setup active-selection: PlayCard with no target places a Basic as active.
    // Must use setup::apply_setup_placement instead of mutations::apply_action.
    if state.phase == GamePhase::Setup
        && action.kind == ActionKind::PlayCard
        && action.target.is_none()
    {
        let pi = state.current_player;
        if let Some(hi) = action.hand_index {
            if hi < state.players[pi].hand.len() {
                setup::apply_setup_placement(state, db, pi, hi, &[]);
            }
        }
        // Setup doesn't advance to Main here — advance_through_setup in
        // rollout() will finalize once both players have an active.
        return;
    }

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
