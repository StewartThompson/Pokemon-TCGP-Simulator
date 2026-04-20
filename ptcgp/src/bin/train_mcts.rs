//! Training CLI for the MCTS + value-net self-learning bot.
//!
//! ```text
//! Usage:
//!   ptcgp-train \
//!       --checkpoint-dir ./checkpoints \
//!       --games-per-gen 200 \
//!       --mcts-sims 240 \
//!       --deck-pool fire \
//!       --generations 5 \
//!       [--resume]
//! ```
//!
//! Each generation:
//!   1. Run `games_per_gen` self-play games in parallel (rayon). The
//!      focal agent is an `MctsAgent` using the current `ValueNet` at
//!      its MCTS leaves. The opponent is, for Wave 3, also a self-mirror
//!      (league mixing is a Wave 4 upgrade).
//!   2. Push every recorded decision into the replay buffer.
//!   3. Run a training epoch (AdamW, Huber loss, multi-head).
//!   4. Eval: play a short batch vs previous gen + vs heuristic baseline,
//!      print win rates with 95 % CI.
//!   5. Save `gen_{N+1}/` with weights + optimizer-less checkpoint + meta.

use candle_core::Device;
use clap::Parser;
use rand::SeedableRng;
use rand::rngs::SmallRng;
use rayon::prelude::*;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Instant;

use ptcgp::agents::{Agent, HeuristicAgent};
use ptcgp::batch::run_batch_fixed_decks;
use ptcgp::card::CardDb;
use ptcgp::decks::get_sample_deck;
use ptcgp::ml::{
    best_device, is_metal,
    card_embed::build_embed_cache,
    checkpoint::{latest_generation, list_generations, load_generation, save_generation, Meta},
    features::FEATURE_DIM,
    league::{pick_opponent, Opponent},
    net::make_optimizer,
    play_training_game, train_epoch, InferenceNet, LeafValue, MctsAgent, MctsConfig, ReplayBuffer,
    ValueNet,
};
use ptcgp::agents::Agent as AgentTrait;
use ptcgp::types::Element;

// ------------------------------------------------------------------ //
// CLI
// ------------------------------------------------------------------ //

#[derive(Parser, Debug)]
#[command(
    name = "ptcgp-train",
    about = "Train the MCTS + value-net bot via self-play"
)]
struct Args {
    /// Directory where generation checkpoints live (one subdir per gen).
    #[arg(long, default_value = "./checkpoints")]
    checkpoint_dir: PathBuf,
    /// Self-play games per generation.
    #[arg(long, default_value_t = 200)]
    games_per_gen: usize,
    /// MCTS simulations per move during self-play.
    #[arg(long, default_value_t = 240)]
    mcts_sims: usize,
    /// Comma-separated deck pool. Each game picks one uniformly.
    #[arg(long, default_value = "charizard")]
    deck_pool: String,
    /// Number of new generations to train this run.
    #[arg(long, default_value_t = 3)]
    generations: u32,
    /// Batch size per training step.
    #[arg(long, default_value_t = 128)]
    batch_size: usize,
    /// Training steps (minibatches) per generation.
    #[arg(long, default_value_t = 200)]
    train_steps: usize,
    /// AdamW learning rate.
    #[arg(long, default_value_t = 1e-3)]
    lr: f64,
    /// Replay buffer capacity (samples).
    #[arg(long, default_value_t = 50_000)]
    replay_cap: usize,
    /// Resume from the latest gen in `checkpoint_dir`. Without this, we
    /// always start from a freshly-initialized gen 0.
    #[arg(long, default_value_t = false)]
    resume: bool,
    /// Base seed.
    #[arg(long, default_value_t = 42)]
    seed: u64,
    /// Evaluation games vs Heuristic at end of each gen.
    #[arg(long, default_value_t = 40)]
    eval_games: usize,
    /// Parallel rayon workers during self-play (default: CPU count).
    #[arg(long)]
    workers: Option<usize>,
    /// Enable league self-play mixing: 60% self-mirror, 30% random past gen,
    /// 10% heuristic. Without this we play 100% self-mirror (simpler but
    /// prone to drift / rock-paper-scissors collapse over many gens).
    #[arg(long, default_value_t = true)]
    league: bool,
    /// MCTS sim count for league *opponents* (past-gen agents). Defaults to
    /// half of --mcts-sims. Lower values speed up the 30% of league games
    /// where both sides run MCTS, with negligible training quality impact
    /// (past-gen opponents exist to prevent forgetting, not to be maximally
    /// strong).
    #[arg(long)]
    league_opp_sims: Option<usize>,
    /// Hybrid leaf-eval weight for the value net: 0.0 = pure rollouts, 1.0
    /// = pure NN. In between blends both. Original-AlphaGo–style; guards
    /// against the NN being wrong on out-of-distribution states. Default
    /// 0.5 is a safe start — NN contributes meaningfully but can't solo
    /// the decision when the rollout strongly disagrees.
    #[arg(long, default_value_t = 0.5)]
    hybrid_weight: f32,
    /// Max rollout plies when hybrid_weight < 1.0. 25 is roughly half a
    /// full PTCGP game — enough to see tactical outcomes.
    #[arg(long, default_value_t = 25)]
    hybrid_rollout_depth: u32,
    /// Use the heuristic agent (not random) for leaf rollouts.
    ///
    /// Random rollouts produce near-zero signal in PTCGP because random vs
    /// random is ~50/50 from any state. Heuristic rollouts play sensibly so
    /// the tree gets real win/loss signal. Essential before the NN is trained
    /// well enough to replace rollouts entirely.
    ///
    /// Rule of thumb:
    ///   Phase 1 (gen 1-10):  --heuristic-rollouts  (strong signal, MCTS > heuristic)
    ///   Phase 2 (gen 11+):   --hybrid-weight 0.2   (blend NN + heuristic rollout)
    ///   Phase 3 (gen 20+):   --hybrid-weight 0.5+  (NN starts to lead)
    #[arg(long, default_value_t = false)]
    heuristic_rollouts: bool,
    /// Rollout depth cap for heuristic rollouts (default 40). Heuristic play
    /// is slower per ply than random, but games typically resolve much faster,
    /// so 40 plies gives a clean win/loss most of the time.
    #[arg(long, default_value_t = 40)]
    heuristic_rollout_depth: u32,
    /// Who to evaluate the current gen against at the end of each generation.
    ///
    /// Accepted values:
    ///   first             — play vs the earliest checkpoint in the dir (default)
    ///   heuristic         — play vs HeuristicAgent
    ///   gen:<N>           — play vs the MCTS bot from checkpoint gen_<N>
    ///   prev:<K>          — play vs the bot from K generations ago (e.g. prev:5)
    ///
    /// Examples:
    ///   --eval-opponent first      (always vs the oldest checkpoint — tracks absolute progress)
    ///   --eval-opponent gen:5      (always vs gen 5)
    ///   --eval-opponent prev:5     (vs whichever gen is 5 behind current)
    ///   --eval-opponent heuristic  (vs HeuristicAgent)
    #[arg(long, default_value = "first")]
    eval_opponent: String,
}

// ------------------------------------------------------------------ //
// Setup helpers
// ------------------------------------------------------------------ //

fn find_assets_dir() -> PathBuf {
    if let Ok(p) = std::env::var("PTCGP_ASSETS") {
        return PathBuf::from(p);
    }
    let cwd = PathBuf::from("assets/cards");
    if cwd.is_dir() {
        return cwd;
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(|p| p.to_path_buf()).unwrap_or_default();
        for _ in 0..6 {
            let c = dir.join("assets/cards");
            if c.is_dir() {
                return c;
            }
            match dir.parent() {
                Some(p) => dir = p.to_path_buf(),
                None => break,
            }
        }
    }
    PathBuf::from("../assets/cards")
}

type DeckPair = (Vec<u16>, Vec<Element>);

/// Transfer a net's weights to a different device by round-tripping through
/// a temporary safetensors file. Used to move between Metal (training) and
/// CPU (parallel inference in rayon workers).
fn transfer_device(net: &ValueNet, target: &Device) -> candle_core::Result<ValueNet> {
    let tmp = std::env::temp_dir().join("ptcgp_device_transfer.safetensors");
    net.save(&tmp)
        .map_err(|e| candle_core::Error::Msg(format!("transfer save: {e}")))?;
    let result = ValueNet::load(&tmp, target.clone())
        .map_err(|e| candle_core::Error::Msg(format!("transfer load: {e}")))?;
    let _ = std::fs::remove_file(&tmp);
    Ok(result)
}

fn resolve_deck_pool(db: &CardDb, spec: &str) -> Vec<DeckPair> {
    spec.split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .filter_map(|name| {
            let (ids, energy) = get_sample_deck(name)?;
            let indices: Vec<u16> = ids
                .iter()
                .filter_map(|id| db.get_idx_by_id(id))
                .collect();
            if indices.is_empty() {
                None
            } else {
                Some((indices, energy.to_vec()))
            }
        })
        .collect()
}

// ------------------------------------------------------------------ //
// Main training loop
// ------------------------------------------------------------------ //

fn main() -> candle_core::Result<()> {
    let args = Args::parse();

    if let Some(w) = args.workers {
        let _ = rayon::ThreadPoolBuilder::new().num_threads(w).build_global();
    }

    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));
    let deck_pool = resolve_deck_pool(&db, &args.deck_pool);
    if deck_pool.is_empty() {
        eprintln!("Error: deck-pool `{}` resolved to 0 valid decks", args.deck_pool);
        std::process::exit(1);
    }
    let embed_cache = Arc::new(build_embed_cache(&db));
    // Metal is NOT thread-safe for concurrent inference across rayon workers.
    // We use two devices:
    //   train_device — Metal (single-threaded gradient computation)
    //   infer_device — always CPU  (rayon-parallel MCTS leaf evaluation)
    // Weights are transferred between them via a temp safetensors file.
    let train_device = best_device();
    let infer_device = Device::Cpu;
    println!(
        "Compute device: training={}, inference=CPU (rayon parallel)",
        if is_metal(&train_device) { "Metal (Apple GPU) 🍎" } else { "CPU" }
    );

    // Make the checkpoint dir exist regardless of branch.
    std::fs::create_dir_all(&args.checkpoint_dir).unwrap_or_else(|e| {
        eprintln!("Warning: couldn't create {}: {}", args.checkpoint_dir.display(), e);
    });

    // --- Bootstrap: always load/init on infer_device (CPU) for parallel inference ---
    // Also track games_played_base so metadata stays accurate on resume.
    let (current_net, mut buffer, start_gen, games_played_base) = if args.resume {
        if let Some(latest) = latest_generation(&args.checkpoint_dir) {
            println!("Resuming from gen_{:03}/", latest);
            let (net, meta, buf) = load_generation(
                &args.checkpoint_dir,
                latest,
                infer_device.clone(),
                args.replay_cap,
            )
            .map_err(|e| candle_core::Error::Msg(format!("load gen: {e}")))?;
            println!(
                "  loaded gen={}  replay_size={}  total_games={}  wall={:.1}s",
                meta.generation,
                buf.len(),
                meta.games_played,
                meta.wall_time_s,
            );
            let gp = meta.games_played;
            (net, buf, latest, gp)
        } else {
            println!("--resume but no checkpoint found; starting from gen 0");
            let net = ValueNet::new(infer_device.clone())?;
            let meta = Meta::new(0);
            save_generation(&args.checkpoint_dir, 0, &net, None, &meta)
                .map_err(|e| candle_core::Error::Msg(format!("save gen 0: {e}")))?;
            (net, ReplayBuffer::new(args.replay_cap), 0, 0u64)
        }
    } else {
        println!("Initializing fresh gen_000/ (random weights)");
        let net = ValueNet::new(infer_device.clone())?;
        let meta = Meta::new(0);
        save_generation(&args.checkpoint_dir, 0, &net, None, &meta)
            .map_err(|e| candle_core::Error::Msg(format!("save gen 0: {e}")))?;
        (net, ReplayBuffer::new(args.replay_cap), 0, 0u64)
    };

    // net_arc is ALWAYS on infer_device (CPU). Rayon workers share it safely.
    let mut net_arc: Arc<ValueNet> = Arc::new(current_net);

    let mut rng = SmallRng::seed_from_u64(args.seed);

    for gen_offset in 0..args.generations {
        let gen = start_gen + 1 + gen_offset;
        let t0 = Instant::now();

        println!(
            "\n================ GEN {} ================  ({} self-play games, {} MCTS sims/move)",
            gen, args.games_per_gen, args.mcts_sims,
        );

        // --- 1. Self-play ---
        // Load past-gen nets for league opponent mixing on infer_device (CPU),
        // so they're safe to share across rayon workers.
        let all_past: Vec<u32> = list_generations(&args.checkpoint_dir)
            .into_iter()
            .filter(|&g| g < gen)
            .collect();
        let recent_past: Vec<u32> = all_past.iter().rev().take(5).copied().collect();
        let mut past_map: std::collections::HashMap<u32, Arc<ValueNet>> =
            std::collections::HashMap::new();
        if args.league {
            for &g in &recent_past {
                match load_generation(&args.checkpoint_dir, g, infer_device.clone(), 0) {
                    Ok((pnet, _, _)) => {
                        past_map.insert(g, Arc::new(pnet));
                    }
                    Err(e) => eprintln!("  warning: couldn't load gen_{:03}: {}", g, e),
                }
            }
        }
        let past_arc = Arc::new(past_map);

        // Build InferenceNet from current net (pure-Rust weights, zero-alloc
        // leaf eval — eliminates all Candle tensor overhead during self-play).
        let inet = Arc::new(
            net_arc
                .to_inference_net()
                .map_err(|e| candle_core::Error::Msg(format!("to_inference_net: {e}")))?,
        );
        // Build InferenceNets for each past-gen net so league opponents also
        // benefit from zero-alloc leaf eval.
        let past_inet_map: std::collections::HashMap<u32, Arc<InferenceNet>> = past_arc
            .iter()
            .filter_map(|(&g, pnet)| {
                pnet.to_inference_net()
                    .ok()
                    .map(|pi| (g, Arc::new(pi)))
            })
            .collect();
        let past_inets_arc = Arc::new(past_inet_map);

        // League opponents use fewer sims to keep league-game overhead low.
        // Past-gen agents exist for anti-forgetting diversity, not max strength.
        let league_opp_sims = args.league_opp_sims.unwrap_or(args.mcts_sims / 2);

        let sp_t = Instant::now();
        let self_play_samples = collect_selfplay_samples(
            &db,
            &embed_cache,
            net_arc.clone(),     // CPU net — safe for rayon
            inet.clone(),
            &past_arc,
            &past_inets_arc,
            &deck_pool,
            args.games_per_gen,
            args.mcts_sims,
            league_opp_sims,
            args.seed.wrapping_add(gen as u64 * 1_000_003),
            args.league,
            args.hybrid_weight,
            args.hybrid_rollout_depth,
            args.heuristic_rollouts,
            args.heuristic_rollout_depth,
        );
        let sp_elapsed = sp_t.elapsed();
        println!(
            "  self-play: {} samples from {} games in {:.1}s ({:.1} games/s)",
            self_play_samples.len(),
            args.games_per_gen,
            sp_elapsed.as_secs_f64(),
            args.games_per_gen as f64 / sp_elapsed.as_secs_f64(),
        );
        buffer.push_many(self_play_samples);

        // --- 2. Train ---
        // Unwrap the CPU net (self-play finished, no other Arc holders).
        // Transfer to train_device (Metal) for gradient computation, then
        // transfer back to CPU for the next gen's self-play.
        let net_cpu =
            Arc::try_unwrap(net_arc).map_err(|_| candle_core::Error::Msg(
                "net Arc still held by another thread — cannot train".to_string(),
            ))?;
        let net_train = if is_metal(&train_device) {
            transfer_device(&net_cpu, &train_device)?
        } else {
            net_cpu
        };
        let mut opt = make_optimizer(&net_train, args.lr)?;
        let train_t = Instant::now();
        let stats = train_epoch(
            &net_train,
            &mut opt,
            &buffer,
            args.batch_size,
            args.train_steps,
            &mut rng,
        )?;
        let train_elapsed = train_t.elapsed();
        println!(
            "  train:     batches={}  loss_win={:.4}  loss_prize={:.4}  loss_hp={:.4}  ({:.1}s)",
            stats.batches,
            stats.loss_win,
            stats.loss_prize,
            stats.loss_hp,
            train_elapsed.as_secs_f64(),
        );

        // Transfer trained weights back to CPU for eval + next gen self-play.
        let net_after_train = if is_metal(&train_device) {
            transfer_device(&net_train, &infer_device)?
        } else {
            net_train
        };

        // --- 3. Eval ---
        // Resolve the eval opponent (may load a past-gen checkpoint).
        let eval_t = Instant::now();
        let (opp_label, opp_agent) = resolve_eval_opponent(
            &args.eval_opponent,
            gen,
            &args.checkpoint_dir,
            &db,
            &infer_device,
            args.mcts_sims,
            args.hybrid_weight,
            args.hybrid_rollout_depth,
            args.heuristic_rollouts,
            args.heuristic_rollout_depth,
        );
        let (wr, net_back) = eval_vs_agent(
            &db,
            Arc::new(net_after_train),
            opp_agent,
            &deck_pool,
            args.eval_games,
            args.mcts_sims,
            args.seed.wrapping_add(0xEEDA_F00D).wrapping_add(gen as u64),
            args.hybrid_weight,
            args.hybrid_rollout_depth,
            args.heuristic_rollouts,
            args.heuristic_rollout_depth,
            &infer_device,
        );
        println!(
            "  eval:      vs_{} = {:.1}% score  ({} games, {:.1}s)",
            opp_label,
            wr * 100.0,
            args.eval_games,
            eval_t.elapsed().as_secs_f64(),
        );

        // --- 4. Save gen ---
        let meta = Meta {
            generation: gen,
            feature_version: ptcgp::ml::features::FEATURE_VERSION,
            games_played: games_played_base + (gen_offset as u64 + 1) * args.games_per_gen as u64,
            wall_time_s: t0.elapsed().as_secs_f64(),
            notes: format!(
                "loss_win={:.4}, vs_{}_score={:.1}%",
                stats.loss_win,
                opp_label,
                wr * 100.0
            ),
        };
        save_generation(
            &args.checkpoint_dir,
            gen,
            &net_back,
            Some(&buffer),
            &meta,
        )
        .map_err(|e| candle_core::Error::Msg(format!("save gen {}: {}", gen, e)))?;
        println!(
            "  saved:     {}/gen_{:03}/  (replay_size={})",
            args.checkpoint_dir.display(),
            gen,
            buffer.len(),
        );

        // Loop back with net wrapped in Arc for next gen.
        net_arc = Arc::new(net_back);
    }

    println!("\nDone — {} generations trained.", args.generations);
    println!("Compare generations with:  ptcgp eval --a <gen_A> --b <gen_B> --games 500");
    Ok(())
}

// ------------------------------------------------------------------ //
// Self-play collection (parallel)
// ------------------------------------------------------------------ //

/// Play `games` self-play games in parallel. Each game uses MCTS with
/// the current value net as the focal agent; the opponent is sampled
/// from the league distribution (self-mirror / past gen / heuristic).
/// Returns all focal-player samples concatenated.
///
/// `inet` and `past_inets` are pure-Rust inference copies of the current
/// and past-gen nets respectively, built once before the parallel loop so
/// all rayon workers share the same allocations without duplication.
fn collect_selfplay_samples(
    db: &Arc<CardDb>,
    embed_cache: &Arc<Vec<[f32; ptcgp::ml::card_embed::CARD_EMBED_DIM]>>,
    net: Arc<ValueNet>,
    inet: Arc<InferenceNet>,
    past_nets: &Arc<std::collections::HashMap<u32, Arc<ValueNet>>>,
    past_inets: &Arc<std::collections::HashMap<u32, Arc<InferenceNet>>>,
    deck_pool: &[DeckPair],
    games: usize,
    mcts_sims: usize,
    league_opp_sims: usize,
    base_seed: u64,
    use_league: bool,
    hybrid_weight: f32,
    hybrid_rollout_depth: u32,
    heuristic_rollouts: bool,
    heuristic_rollout_depth: u32,
) -> Vec<ptcgp::ml::Sample> {
    let past_gens: Vec<u32> = past_nets.keys().copied().collect();

    (0..games)
        .into_par_iter()
        .flat_map(|i| {
            // Leaf evaluation strategy priority:
            //  1. --heuristic-rollouts → HeuristicRollout (best signal before NN is trained)
            //  2. hybrid_weight ≈ 1.0  → pure ValueNet leaf (fast, use once NN is reliable)
            //  3. hybrid_weight ≈ 0.0  → RandomRollout full-depth (fallback, weak signal)
            //  4. otherwise            → Hybrid NN + short random rollout (AlphaGo style)
            let (leaf_value, depth_cap) = if heuristic_rollouts {
                (LeafValue::HeuristicRollout, heuristic_rollout_depth)
            } else if hybrid_weight >= 0.999 {
                (LeafValue::ValueNet, 200)
            } else if hybrid_weight <= 0.001 {
                (LeafValue::RandomRollout, 200)
            } else {
                (LeafValue::HybridValueRollout {
                    net_weight: hybrid_weight,
                    rollout_depth: hybrid_rollout_depth,
                }, 200)
            };
            let config = MctsConfig {
                total_sims: mcts_sims,
                leaf_value_source: leaf_value,
                rollout_depth_cap: depth_cap,
                temperature: 1.0, // sample visits (exploration) during self-play
                use_dirichlet: true, // Dirichlet root noise for exploration diversity
                ..Default::default()
            };
            // Focal agent: share embed_cache + inference_net to avoid per-agent allocs.
            let focal = MctsAgent::new(config.clone(), db.clone())
                .with_net(net.clone())
                .with_inference_net(inet.clone())
                .with_embed_cache(embed_cache.clone())
                .with_seed(base_seed.wrapping_add(i as u64 * 101));

            // Pick opponent type via league (if enabled), else always self-mirror.
            let mut rng = SmallRng::seed_from_u64(base_seed.wrapping_add(i as u64 * 2003));
            let opp_kind = if use_league {
                pick_opponent(&mut rng, &past_gens)
            } else {
                Opponent::SelfMirror
            };
            // Build the opponent agent. Opponents never need Dirichlet noise
            // (that's exploration for the focal agent only — samples come from
            // the focal player's perspective). Disabling it saves ~1 random
            // sample + sort per MCTS root expansion.
            let opp_base_config = MctsConfig {
                use_dirichlet: false,
                temperature: 0.0, // deterministic opponent play
                ..config.clone()
            };
            let opp_seed = base_seed.wrapping_add(i as u64 * 101 + 37);
            let opp: Box<dyn AgentTrait + Send + Sync> = match opp_kind {
                Opponent::SelfMirror => Box::new(
                    MctsAgent::new(opp_base_config, db.clone())
                        .with_net(net.clone())
                        .with_inference_net(inet.clone())
                        .with_embed_cache(embed_cache.clone())
                        .with_seed(opp_seed),
                ),
                Opponent::PastGen(g) => {
                    let opp_config = MctsConfig {
                        total_sims: league_opp_sims,
                        ..opp_base_config.clone()
                    };
                    match (past_nets.get(&g), past_inets.get(&g)) {
                        (Some(pnet), Some(pinet)) => Box::new(
                            MctsAgent::new(opp_config, db.clone())
                                .with_net(pnet.clone())
                                .with_inference_net(pinet.clone())
                                .with_embed_cache(embed_cache.clone())
                                .with_seed(opp_seed),
                        ),
                        (Some(pnet), None) => Box::new(
                            MctsAgent::new(opp_config, db.clone())
                                .with_net(pnet.clone())
                                .with_embed_cache(embed_cache.clone())
                                .with_seed(opp_seed),
                        ),
                        _ => {
                            // Shouldn't happen — pick_opponent only returns gens
                            // from past_gens — but fall back to self-mirror.
                            Box::new(
                                MctsAgent::new(opp_base_config, db.clone())
                                    .with_net(net.clone())
                                    .with_inference_net(inet.clone())
                                    .with_embed_cache(embed_cache.clone())
                                    .with_seed(opp_seed),
                            )
                        }
                    }
                }
                Opponent::Heuristic => Box::new(ptcgp::agents::HeuristicAgent),
            };

            // Assign decks: focal gets deck[i % n], opponent gets a
            // *different* deck (deck[(i + n/2) % n]).  Asymmetric matchups
            // (e.g. pikachu vs charizard) give more decisive games, expose
            // the agent to diverse opponents, and reduce draw rates vs
            // mirror-match self-play on slow/healing-heavy decks.
            let n = deck_pool.len();
            let (focal_deck, focal_energy) = &deck_pool[i % n];
            let opp_deck_idx = if n > 1 { (i + n / 2) % n } else { 0 };
            let (opp_deck, opp_energy) = &deck_pool[opp_deck_idx];

            play_training_game(
                db.as_ref(),
                &focal,
                opp.as_ref(),
                focal_deck.clone(),
                opp_deck.clone(),
                focal_energy.clone(),
                opp_energy.clone(),
                base_seed.wrapping_add(i as u64),
                embed_cache.as_slice(),
            )
        })
        .collect()
}

// ------------------------------------------------------------------ //
// Evaluation vs HeuristicAgent
// ------------------------------------------------------------------ //

// ------------------------------------------------------------------ //
// Flexible eval-opponent resolution
// ------------------------------------------------------------------ //

/// Resolve an `--eval-opponent` spec to a label string and a concrete agent.
///
/// Specs:
///   `first`              → oldest checkpoint in the dir (trained net)
///   `heuristic`          → simple rule-based HeuristicAgent (weak baseline)
///   `mcts-raw`           → pure MCTS with heuristic rollouts, no net (honest baseline)
///   `mcts-raw:<sims>`    → pure MCTS with N sims (e.g. `mcts-raw:240`)
///   `gen:<N>`            → MCTS bot from gen_<N>
///   `prev:<K>`           → MCTS bot from (current_gen - K)
///
/// `mcts-raw` is the best eval opponent: it's a strong fixed baseline that never
/// gets easier. Any increase in win rate vs it means the net genuinely improved.
///
/// Falls back to HeuristicAgent with a warning if the checkpoint can't be loaded.
fn resolve_eval_opponent(
    spec: &str,
    current_gen: u32,
    checkpoint_dir: &std::path::Path,
    db: &Arc<CardDb>,
    device: &Device,
    mcts_sims: usize,
    hybrid_weight: f32,
    hybrid_rollout_depth: u32,
    heuristic_rollouts: bool,
    heuristic_rollout_depth: u32,
) -> (String, Arc<dyn Agent>) {
    // Handle mcts-raw[:sims] — pure MCTS with heuristic rollouts, no learned net.
    // This is the best eval baseline: fixed strength, honest benchmark.
    if spec == "mcts-raw" || spec.starts_with("mcts-raw:") {
        let sims = spec
            .strip_prefix("mcts-raw:")
            .and_then(|s| s.parse::<usize>().ok())
            .unwrap_or(mcts_sims);
        let config = MctsConfig {
            total_sims: sims,
            leaf_value_source: LeafValue::HeuristicRollout,
            rollout_depth_cap: heuristic_rollout_depth,
            temperature: 0.0,
            ..Default::default()
        };
        let label = format!("mcts-raw:{}", sims);
        return (label, Arc::new(MctsAgent::new(config, db.clone())) as Arc<dyn Agent>);
    }

    // Resolve spec → Option<gen_number>.
    let target_gen: Option<u32> = if spec == "heuristic" {
        None // handled separately below
    } else if spec == "first" {
        let gens = list_generations(checkpoint_dir);
        // Skip gen 0 (random weights) if there's anything better.
        gens.into_iter().find(|&g| g > 0).or(Some(0))
    } else if let Some(rest) = spec.strip_prefix("gen:") {
        rest.parse::<u32>().ok()
    } else if let Some(rest) = spec.strip_prefix("prev:") {
        let k = rest.parse::<u32>().unwrap_or(5);
        if current_gen > k { Some(current_gen - k) } else { Some(0) }
    } else {
        eprintln!("  warning: unknown eval-opponent spec '{}', falling back to heuristic", spec);
        None
    };

    match target_gen {
        None => {
            // heuristic
            ("heuristic".to_string(), Arc::new(HeuristicAgent) as Arc<dyn Agent>)
        }
        Some(g) => {
            match load_generation(checkpoint_dir, g, device.clone(), 0) {
                Ok((net, _, _)) => {
                    let (leaf_value, depth_cap) = if heuristic_rollouts {
                        (LeafValue::HeuristicRollout, heuristic_rollout_depth)
                    } else if hybrid_weight >= 0.999 {
                        (LeafValue::ValueNet, 200)
                    } else if hybrid_weight <= 0.001 {
                        (LeafValue::RandomRollout, 200)
                    } else {
                        (LeafValue::HybridValueRollout {
                            net_weight: hybrid_weight,
                            rollout_depth: hybrid_rollout_depth,
                        }, 200)
                    };
                    let config = MctsConfig {
                        total_sims: mcts_sims,
                        leaf_value_source: leaf_value,
                        rollout_depth_cap: depth_cap,
                        temperature: 0.0,
                        ..Default::default()
                    };
                    let agent = MctsAgent::new(config, db.clone()).with_net(Arc::new(net));
                    (format!("gen_{:03}", g), Arc::new(agent) as Arc<dyn Agent>)
                }
                Err(e) => {
                    eprintln!(
                        "  warning: couldn't load gen_{:03} for eval ({}); falling back to heuristic",
                        g, e
                    );
                    ("heuristic(fallback)".to_string(), Arc::new(HeuristicAgent) as Arc<dyn Agent>)
                }
            }
        }
    }
}

/// Head-to-head eval of `net` vs any `Arc<dyn Agent>` opponent.
/// Returns `(win_rate_of_net_agent, net_returned)`.
fn eval_vs_agent(
    db: &Arc<CardDb>,
    net: Arc<ValueNet>,
    opp_agent: Arc<dyn Agent>,
    deck_pool: &[DeckPair],
    games: usize,
    mcts_sims: usize,
    seed: u64,
    hybrid_weight: f32,
    hybrid_rollout_depth: u32,
    heuristic_rollouts: bool,
    heuristic_rollout_depth: u32,
    device: &Device,
) -> (f64, ValueNet) {
    let (leaf_value, depth_cap) = if heuristic_rollouts {
        (LeafValue::HeuristicRollout, heuristic_rollout_depth)
    } else if hybrid_weight >= 0.999 {
        (LeafValue::ValueNet, 200)
    } else if hybrid_weight <= 0.001 {
        (LeafValue::RandomRollout, 200)
    } else {
        (LeafValue::HybridValueRollout {
            net_weight: hybrid_weight,
            rollout_depth: hybrid_rollout_depth,
        }, 200)
    };
    let config = MctsConfig {
        total_sims: mcts_sims,
        leaf_value_source: leaf_value,
        rollout_depth_cap: depth_cap,
        temperature: 0.0,
        ..Default::default()
    };
    let mcts_agent: Arc<dyn Agent> =
        Arc::new(MctsAgent::new(config, db.clone()).with_net(net.clone()));

    let mut total_games: usize = 0;
    let mut mcts_wins: usize = 0;
    let mut mcts_draws: usize = 0;
    let games_per_deck = (games / deck_pool.len().max(1)).max(2);
    for (di, (deck, energy)) in deck_pool.iter().enumerate() {
        let d_seed = seed.wrapping_add(di as u64 * 99_991);
        let r1 = run_batch_fixed_decks(
            db.clone(),
            deck.clone(),
            deck.clone(),
            energy.clone(),
            energy.clone(),
            mcts_agent.clone(),
            opp_agent.clone(),
            games_per_deck / 2,
            d_seed,
        );
        let r2 = run_batch_fixed_decks(
            db.clone(),
            deck.clone(),
            deck.clone(),
            energy.clone(),
            energy.clone(),
            opp_agent.clone(),
            mcts_agent.clone(),
            games_per_deck - games_per_deck / 2,
            d_seed ^ 0xABCD_1234,
        );
        total_games += r1.total_games + r2.total_games;
        mcts_wins += r1.player0_wins + r2.player1_wins;
        mcts_draws += r1.draws + r2.draws;
    }
    // Use score = (wins + 0.5*draws) / total instead of raw wins.
    // Raw win rate is misleading on slow decks where draws are frequent
    // (venusaur/mewtwo can hit 65-70% draws vs MCTS, so raw win rate looks
    // terrible even when the agent is actually stronger than the opponent).
    let wr = if total_games > 0 {
        (mcts_wins as f64 + 0.5 * mcts_draws as f64) / total_games as f64
    } else {
        0.0
    };

    drop(mcts_agent);
    drop(opp_agent);
    let net_back = Arc::try_unwrap(net).unwrap_or_else(|arc| {
        let tmp = std::env::temp_dir().join("ptcgp_net_recover2.safetensors");
        arc.save(&tmp).expect("recover save");
        let n = ValueNet::load(&tmp, device.clone()).expect("recover load");
        let _ = std::fs::remove_file(&tmp);
        n
    });

    let _ = FEATURE_DIM;
    (wr, net_back)
}
