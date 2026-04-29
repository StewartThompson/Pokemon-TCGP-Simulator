//! Pokemon TCG Pocket Battle Simulator — Rust CLI
//!
//! Commands:
//!   ptcgp simulate   — batch bot-vs-bot games in parallel
//!   ptcgp play       — interactive game vs heuristic AI
//!   ptcgp profile    — timing benchmark over N single-threaded games

use clap::{Args, Parser, Subcommand};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use ptcgp::agents::human::HumanAgent;
use ptcgp::agents::{Agent, HeuristicAgent, RandomAgent};
use ptcgp::batch::run_batch_fixed_decks;
use ptcgp::card::CardDb;
use ptcgp::decks::{get_sample_deck, ALL_DECK_NAMES};
use ptcgp::ml::{
    checkpoint::{latest_generation, load_generation, Meta},
    LeafValue, MctsAgent, MctsConfig, NnGreedyAgent,
};
use ptcgp::runner::run_game;
use ptcgp::types::Element;

// ------------------------------------------------------------------ //
// CLI definition
// ------------------------------------------------------------------ //

#[derive(Parser)]
#[command(
    name = "ptcgp",
    about = "Pokemon TCG Pocket Battle Simulator",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Simulate N bot-vs-bot games in parallel and print win rates
    Simulate(SimulateArgs),
    /// Play an interactive game against the heuristic AI
    Play(PlayArgs),
    /// Profile N single-threaded games and report timing
    Profile(ProfileArgs),
    /// Run a round-robin tournament across all built-in decks
    Decks(DecksArgs),
    /// Evaluate two agents head-to-head (supports paired-seed matchups)
    Eval(EvalArgs),
}

#[derive(Args)]
struct SimulateArgs {
    #[arg(long, default_value_t = 100, help = "Number of games to simulate")]
    games: usize,
    #[arg(long, default_value = "venusaur", help = "Deck for player 1 (venusaur|charizard|mewtwo|nihilego|celebi|mew|dragonite|rampardos|gyarados|guzzlord|pikachu|magnezone|suicune|megacharizard|test)")]
    deck1: String,
    #[arg(long, default_value = "charizard", help = "Deck for player 2 (venusaur|charizard|mewtwo|nihilego|celebi|mew|dragonite|rampardos|gyarados|guzzlord|pikachu|magnezone|suicune|megacharizard|test)")]
    deck2: String,
    #[arg(
        long,
        default_value = "heuristic",
        help = "Agent for player 1. Accepts: ai (latest trained bot) | \
                random | heuristic | mcts-raw[:sims] | mcts-raw-heur[:sims] | \
                mcts:<gen>[:sims] | mcts-hybrid:<gen>[:sims[:weight[:depth]]]"
    )]
    agent1: String,
    #[arg(
        long,
        default_value = "heuristic",
        help = "Agent for player 2 (same spec options as --agent1)"
    )]
    agent2: String,
    #[arg(long, help = "Base random seed (default: random; printed for replay)")]
    seed: Option<u64>,
    #[arg(long, help = "Parallel Rayon workers (default: CPU count)")]
    workers: Option<usize>,
}

#[derive(Args)]
struct PlayArgs {
    #[arg(long, default_value = "venusaur", help = "Your deck (venusaur|charizard|mewtwo|nihilego|celebi|mew|dragonite|rampardos|gyarados|guzzlord|pikachu|magnezone|suicune|megacharizard|test)")]
    deck: String,
    #[arg(long, default_value = "charizard", help = "Opponent's deck (venusaur|charizard|mewtwo|nihilego|celebi|mew|dragonite|rampardos|gyarados|guzzlord|pikachu|magnezone|suicune|megacharizard|test)")]
    opponent: String,
    #[arg(long, default_value = "ai", help = "Opponent AI: ai (trained bot, default) | heuristic | random | mcts-raw[:sims] | mcts-raw-heur[:sims] | mcts:<gen>[:sims] | mcts-hybrid:<gen>[:sims[:weight[:depth]]]")]
    ai: String,
    #[arg(long, help = "Random seed (default: random; printed for replay)")]
    seed: Option<u64>,
}

#[derive(Args)]
struct DecksArgs {
    #[arg(long, default_value_t = 100, help = "Number of games per matchup")]
    games: usize,
    #[arg(
        long,
        default_value = "heuristic",
        help = "Agent for both players (symmetric). Accepts: ai (latest \
                trained bot) | random | heuristic | mcts-raw[:sims] | \
                mcts-raw-heur[:sims] | mcts:<gen>[:sims] | \
                mcts-hybrid:<gen>[:sims[:weight[:depth]]]. Overridden by \
                --agent1/--agent2 when those are set."
    )]
    agent: String,
    /// Override the player-1 (row) agent. Same spec options as --agent.
    /// If set (together with or without --agent2), the tournament becomes
    /// asymmetric: --agent1 pilots the row deck, --agent2 pilots the
    /// column deck. Use this for AI-vs-Heuristic style comparisons.
    #[arg(long)]
    agent1: Option<String>,
    /// Override the player-2 (column) agent. Same spec options as --agent.
    #[arg(long)]
    agent2: Option<String>,
    #[arg(long, help = "Parallel Rayon workers (default: CPU count)")]
    workers: Option<usize>,
}

#[derive(Args)]
struct EvalArgs {
    /// Agent A (random | heuristic | mcts-raw:<sims> | mcts-raw-heur:<sims>)
    #[arg(long, default_value = "mcts-raw:500")]
    a: String,
    /// Agent B
    #[arg(long, default_value = "heuristic")]
    b: String,
    /// Total games to play.  In paired mode this counts pairs — each pair is
    /// two games (A as P0 + B as P0) with the same seed for variance reduction.
    #[arg(long, default_value_t = 500)]
    games: usize,
    /// Deck for agent A (also used for both in mirror mode).
    #[arg(long, default_value = "charizard")]
    deck1: String,
    /// Deck for agent B.
    #[arg(long, default_value = "charizard")]
    deck2: String,
    /// Paired-seed mode: each logical game is played twice (agents swap sides)
    /// with identical RNG seeds. Halves variance in head-to-head eval.
    #[arg(long, default_value_t = true)]
    paired: bool,
    /// Base random seed (default: random).
    #[arg(long)]
    seed: Option<u64>,
    /// Parallel rayon workers (default: CPU count).
    #[arg(long)]
    workers: Option<usize>,
}

#[derive(Args)]
struct ProfileArgs {
    #[arg(long, default_value_t = 1000, help = "Number of games to run")]
    games: usize,
    #[arg(long, default_value = "venusaur", help = "Deck for player 1 (venusaur|charizard|mewtwo|nihilego|celebi|mew|dragonite|rampardos|gyarados|guzzlord|pikachu|magnezone|suicune|megacharizard|test)")]
    deck1: String,
    #[arg(long, default_value = "charizard", help = "Deck for player 2 (venusaur|charizard|mewtwo|nihilego|celebi|mew|dragonite|rampardos|gyarados|guzzlord|pikachu|magnezone|suicune|megacharizard|test)")]
    deck2: String,
    #[arg(long, default_value = "heuristic", help = "Agent for player 1 (random|heuristic)")]
    agent1: String,
    #[arg(long, default_value = "heuristic", help = "Agent for player 2 (random|heuristic)")]
    agent2: String,
    #[arg(long, default_value_t = 42, help = "Base random seed")]
    seed: u64,
}

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //

/// Locate the assets/cards directory.
///
/// Search order:
/// 1. `PTCGP_ASSETS` environment variable
/// 2. Walk up from the current executable looking for `assets/cards`
/// 3. Fall back to `../assets/cards` (works with `cargo run` from workspace root)
fn find_assets_dir() -> PathBuf {
    // 1. Explicit env var override
    if let Ok(p) = std::env::var("PTCGP_ASSETS") {
        return PathBuf::from(p);
    }
    // 2. assets/cards relative to current working directory (most common case)
    let cwd_candidate = PathBuf::from("assets/cards");
    if cwd_candidate.is_dir() {
        return cwd_candidate;
    }
    // 3. Walk up from the current executable (covers cargo run from ptcgp/)
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(|p| p.to_path_buf()).unwrap_or_default();
        for _ in 0..6 {
            let candidate = dir.join("assets/cards");
            if candidate.is_dir() {
                return candidate;
            }
            match dir.parent() {
                Some(p) => dir = p.to_path_buf(),
                None => break,
            }
        }
    }
    // 4. Last resort: sibling directory (cargo run from ptcgp/ subdirectory)
    PathBuf::from("../assets/cards")
}

fn random_seed() -> u64 {
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    t.as_secs().wrapping_mul(0x9e3779b97f4a7c15) ^ t.subsec_nanos() as u64
}

/// Parse an agent spec into a concrete agent. Accepted forms:
///
/// * `random`                   — [`RandomAgent`]
/// * `heuristic`                — [`HeuristicAgent`]
/// * `ai`                       — shorthand for `mcts-hybrid:latest:240:0.35:25`
///                                 (strongest, ~13 games/s)
/// * `ai-fast`                  — shorthand for `mcts-hybrid:latest:80:0.35:15`
///                                 (~3× faster, slightly weaker)
/// * `nn[:<gen>]`               — pure value-net action scorer. No tree
///                                 search — for each legal action, apply
///                                 it and let the NN score the resulting
///                                 state. Picks the max. Orders of magnitude
///                                 faster than MCTS; noticeably weaker.
/// * `mcts-raw[:<sims>]`        — pure MCTS with random rollouts
/// * `mcts-raw-heur[:<sims>]`   — MCTS with heuristic rollouts
/// * `mcts:<gen>[:<sims>]`      — MCTS with value-net leaves, no rollout
/// * `mcts-hybrid:<gen>[:<sims>[:<weight>[:<depth>]]]` — blended NN + rollout
///
/// Read the eval_spec from the latest checkpoint's meta.json.
/// Returns e.g. "240:0.50:25". Falls back to a safe default if unset.
fn latest_eval_spec() -> String {
    let ckpt_dir = std::env::var("PTCGP_CHECKPOINTS")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::path::PathBuf::from("./checkpoints"));
    if let Some(gen) = latest_generation(&ckpt_dir) {
        let meta_path = ckpt_dir
            .join(format!("gen_{:03}", gen))
            .join("meta.json");
        if let Ok(s) = std::fs::read_to_string(&meta_path) {
            if let Ok(meta) = serde_json::from_str::<Meta>(&s) {
                if let Some(spec) = meta.eval_spec {
                    return spec;
                }
            }
        }
    }
    // Fallback for checkpoints that predate eval_spec.
    "240:0.50:25".to_string()
}

/// Unknown values fall back to [`HeuristicAgent`].
fn make_agent(name: &str, db: &Arc<CardDb>) -> Arc<dyn Agent> {
    let mut name = name.trim().to_lowercase();
    // "ai" and "ai-fast" dynamically resolve to the latest checkpoint,
    // using whatever eval parameters were recorded in its meta.json.
    if name == "ai" {
        name = format!("mcts-hybrid:latest:{}", latest_eval_spec());
    } else if name == "ai-fast" {
        // Same model, fewer sims for speed.
        let spec = latest_eval_spec();
        let parts: Vec<&str> = spec.splitn(3, ':').collect();
        let weight_depth = if parts.len() >= 3 {
            format!("{}:{}", parts[1], parts[2])
        } else {
            "0.50:25".to_string()
        };
        name = format!("mcts-hybrid:latest:80:{}", weight_depth);
    }
    // Note: mcts-raw-heur must be checked before mcts-raw since the latter
    // is a prefix of the former. Using else-if makes the ordering explicit.
    if let Some(rest) = name.strip_prefix("mcts-raw-heur") {
        let sims = parse_sims(rest).unwrap_or(500);
        let config = MctsConfig {
            total_sims: sims,
            leaf_value_source: LeafValue::HeuristicRollout,
            ..Default::default()
        };
        return Arc::new(MctsAgent::new(config, db.clone()));
    } else if let Some(rest) = name.strip_prefix("mcts-raw") {
        let sims = parse_sims(rest).unwrap_or(500);
        let config = MctsConfig {
            total_sims: sims,
            leaf_value_source: LeafValue::RandomRollout,
            ..Default::default()
        };
        return Arc::new(MctsAgent::new(config, db.clone()));
    }
    // Pure value-net greedy scorer. No tree search.
    //   "nn"          — latest gen
    //   "nn:<gen>"    — specific gen
    if name == "nn" || name.starts_with("nn:") {
        let gen_str = if name == "nn" {
            "latest"
        } else {
            &name["nn:".len()..]
        };
        let net = load_gen_net(gen_str);
        return Arc::new(NnGreedyAgent::new(Arc::new(net), db));
    }

    // "mcts-hybrid:<gen>[:<sims>[:<net_weight>[:<rollout_depth>[:<determinizations>]]]]"
    if let Some(rest) = name.strip_prefix("mcts-hybrid:") {
        let mut parts = rest.split(':');
        let gen_str = parts.next().unwrap_or("latest");
        let sims: usize = parts.next().and_then(|s| s.parse().ok()).unwrap_or(240);
        let net_weight: f32 = parts.next().and_then(|s| s.parse().ok()).unwrap_or(0.5);
        let rollout_depth: u32 = parts.next().and_then(|s| s.parse().ok()).unwrap_or(25);
        let determinizations: usize = parts.next().and_then(|s| s.parse().ok()).unwrap_or(1);
        let net = load_gen_net(gen_str);
        let config = MctsConfig {
            total_sims: sims,
            determinizations,
            leaf_value_source: LeafValue::HybridValueRollout {
                net_weight,
                rollout_depth,
            },
            temperature: 0.0,
            ..Default::default()
        };
        let agent = MctsAgent::new(config, db.clone()).with_net(Arc::new(net));
        return Arc::new(agent);
    }
    if let Some(rest) = name.strip_prefix("mcts:") {
        // Formats: "mcts:<gen>[:<sims>[:<determinizations>]]"
        let mut parts = rest.split(':');
        let gen_str = parts.next().unwrap_or("latest");
        let sims: usize = parts
            .next()
            .and_then(|s| s.parse().ok())
            .unwrap_or(240);
        let determinizations: usize = parts.next().and_then(|s| s.parse().ok()).unwrap_or(1);
        let net = load_gen_net(gen_str);
        let config = MctsConfig {
            total_sims: sims,
            determinizations,
            leaf_value_source: LeafValue::ValueNet,
            temperature: 0.0,
            ..Default::default()
        };
        let agent = MctsAgent::new(config, db.clone())
            .with_net(Arc::new(net));
        return Arc::new(agent);
    }
    match name.as_str() {
        "random" => Arc::new(RandomAgent),
        _ => Arc::new(HeuristicAgent),
    }
}

/// Parse the `:<N>` suffix used by MCTS agent specs. Empty → None; otherwise
/// returns the numeric suffix (None on parse error so caller can use default).
fn parse_sims(rest: &str) -> Option<usize> {
    let s = rest.trim_start_matches(':');
    if s.is_empty() {
        return None;
    }
    s.parse::<usize>().ok()
}

/// Load a value net from checkpoint. Accepts "latest" or an integer gen.
/// Fatals out with a clear message on any failure — the caller can't
/// meaningfully continue without a net.
fn load_gen_net(gen_str: &str) -> ptcgp::ml::ValueNet {
    let ckpt_dir = std::env::var("PTCGP_CHECKPOINTS")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::path::PathBuf::from("./checkpoints"));
    let gen_num: u32 = if gen_str == "latest" {
        match latest_generation(&ckpt_dir) {
            Some(g) => g,
            None => {
                eprintln!(
                    "Error: no checkpoints found in {}\n\
                     \n\
                     To use --agent ai you need a trained model. Fixes:\n\
                       1. Point to an existing trained dir:\n\
                          export PTCGP_CHECKPOINTS=<path-to-checkpoints-dir>\n\
                       2. Or train a new model:\n\
                          ptcgp-train --checkpoint-dir ./checkpoints \\\n\
                                      --deck-pool fire,grass,mewtwo \\\n\
                                      --generations 10 --hybrid-weight 0.35",
                    ckpt_dir.display()
                );
                std::process::exit(1);
            }
        }
    } else {
        match gen_str.parse() {
            Ok(g) => g,
            Err(_) => {
                eprintln!("Error: couldn't parse generation number '{}'", gen_str);
                std::process::exit(1);
            }
        }
    };
    let (net, _meta, _buffer) =
        match load_generation(&ckpt_dir, gen_num, candle_core::Device::Cpu, 1) {
            Ok(x) => x,
            Err(e) => {
                eprintln!(
                    "Error: load gen {} from {}: {}",
                    gen_num,
                    ckpt_dir.display(),
                    e
                );
                std::process::exit(1);
            }
        };
    net
}

/// Resolve a named deck to `(Vec<u16>, Vec<Element>)` using the CardDb.
fn resolve_deck(db: &CardDb, name: &str) -> Result<(Vec<u16>, Vec<Element>), String> {
    let (ids, energy) = get_sample_deck(name)
        .ok_or_else(|| format!("Unknown deck '{}'. Available: {}", name, ALL_DECK_NAMES.join(", ")))?;

    let indices: Vec<u16> = ids
        .iter()
        .filter_map(|&id| {
            match db.get_idx_by_id(id) {
                Some(idx) => Some(idx),
                None => {
                    eprintln!("Warning: card '{}' not found in database — skipping", id);
                    None
                }
            }
        })
        .collect();

    if indices.is_empty() {
        return Err(format!(
            "Deck '{}' resolved to 0 cards. Check that PTCGP_ASSETS points to the correct directory.",
            name
        ));
    }

    Ok((indices, energy.to_vec()))
}

// ------------------------------------------------------------------ //
// simulate
// ------------------------------------------------------------------ //

fn cmd_simulate(args: SimulateArgs) {
    if let Some(w) = args.workers {
        let _ = rayon::ThreadPoolBuilder::new()
            .num_threads(w)
            .build_global();
    }

    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));
    let seed = args.seed.unwrap_or_else(random_seed);

    let (deck1, e1) = match resolve_deck(&db, &args.deck1) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };
    let (deck2, e2) = match resolve_deck(&db, &args.deck2) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };

    let agent1 = make_agent(&args.agent1, &db);
    let agent2 = make_agent(&args.agent2, &db);

    println!(
        "Simulating {} games ({}/{} vs {}/{}) seed={} workers={}",
        args.games,
        args.deck1, args.agent1,
        args.deck2, args.agent2,
        seed,
        args.workers.map(|n| n.to_string()).unwrap_or_else(|| "auto".to_string()),
    );

    let result = run_batch_fixed_decks(
        db, deck1, deck2, e1, e2,
        agent1, agent2,
        args.games,
        seed,
    );

    println!("\nResults after {} games:", result.total_games);
    println!(
        "  Player 1 ({}/{}): {} wins ({:.1}%)",
        args.deck1, args.agent1,
        result.player0_wins,
        result.win_rate_player0 * 100.0,
    );
    println!(
        "  Player 2 ({}/{}): {} wins ({:.1}%)",
        args.deck2, args.agent2,
        result.player1_wins,
        result.win_rate_player1 * 100.0,
    );
    println!(
        "  Draws: {} ({:.1}%)",
        result.draws,
        result.draws as f64 / result.total_games as f64 * 100.0,
    );
    println!("  Avg turns: {:.1}", result.avg_turns);
}

// ------------------------------------------------------------------ //
// play
// ------------------------------------------------------------------ //

fn cmd_play(args: PlayArgs) {
    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));
    let seed = args.seed.unwrap_or_else(random_seed);

    let (deck_human, energy_human) = match resolve_deck(&db, &args.deck) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };
    let (deck_opp, energy_opp) = match resolve_deck(&db, &args.opponent) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };

    println!("Starting game: {} deck vs {} deck ({})", args.deck, args.opponent, args.ai);
    println!("seed={} (re-run with --seed {} to replay this exact game)", seed, seed);
    println!("Enter the number of your chosen action when prompted.\n");

    let human = HumanAgent::new(0);
    let ai = make_agent(&args.ai, &db);

    let result = run_game(
        &db,
        deck_human,
        deck_opp,
        energy_human,
        energy_opp,
        &human,
        ai.as_ref(),
        seed,
        Some(0), // human is player 0 — narrate opponent's actions
    );

    println!("\n{}", "=".repeat(60));
    println!("GAME OVER");
    println!("{}", "=".repeat(60));
    match result.winner {
        Some(0) => println!("*** YOU WIN! ***"),
        Some(1) => println!("*** YOU LOSE ***"),
        _       => println!("*** DRAW ***"),
    }
    println!(
        "Final score: YOU {} | OPPONENT {}",
        result.player0_points, result.player1_points
    );
    println!("Total turns: {}", result.turns);
    println!("\nRe-run with: ptcgp play --deck {} --opponent {} --seed {}", args.deck, args.opponent, seed);
}

// ------------------------------------------------------------------ //
// decks (round-robin tournament)
// ------------------------------------------------------------------ //

// Tournament deck list — uses the single source of truth from
// `decks::ALL_DECK_NAMES` (re-exported as a local alias) so adding a deck
// there automatically picks it up here too.
const ALL_DECKS: &[&str] = ALL_DECK_NAMES;

fn cmd_decks(args: DecksArgs) {
    if let Some(w) = args.workers {
        let _ = rayon::ThreadPoolBuilder::new()
            .num_threads(w)
            .build_global();
    }

    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));
    let seed = random_seed();
    let n = ALL_DECKS.len();

    // If the user set --agent1 or --agent2, we go asymmetric.  Otherwise
    // both sides use the single --agent value (classic symmetric mode).
    let (a1_spec, a2_spec) = match (&args.agent1, &args.agent2) {
        (Some(a), Some(b)) => (a.clone(), b.clone()),
        (Some(a), None) => (a.clone(), args.agent.clone()),
        (None, Some(b)) => (args.agent.clone(), b.clone()),
        (None, None) => (args.agent.clone(), args.agent.clone()),
    };
    let symmetric = a1_spec == a2_spec;

    let agent1 = make_agent(&a1_spec, &db);
    let agent2 = if symmetric { Arc::clone(&agent1) } else { make_agent(&a2_spec, &db) };

    let total_matchups = n * (n - 1);
    let total_games = total_matchups * args.games;

    // Time estimate: dominated by whichever side is slowest. Measured on
    // this MacBook Pro running with rayon across CPU cores. Heuristic +
    // random are negligible; nn adds a forward-pass per legal action
    // (still fast); ai-fast is MCTS with 80 sims; ai is MCTS with 240 sims.
    let speed_of = |s: &str| -> f64 {
        let l = s.trim().to_lowercase();
        if l == "random" || l == "heuristic" {
            5000.0
        } else if l == "nn" || l.starts_with("nn:") {
            800.0
        } else if l == "ai-fast" {
            40.0
        } else if l == "ai" || l.starts_with("mcts") {
            13.0
        } else {
            5000.0
        }
    };
    let est_games_per_sec: f64 = speed_of(&a1_spec).min(speed_of(&a2_spec));
    let est_seconds = total_games as f64 / est_games_per_sec;

    println!(
        "Round-robin tournament: {} decks × {} games/matchup = {} total games",
        n,
        args.games,
        total_games,
    );
    if symmetric {
        println!(
            "Agent: {}  |  seed={}  |  ~{:.0}s estimated ({:.1} games/s)",
            a1_spec, seed, est_seconds, est_games_per_sec,
        );
    } else {
        println!(
            "P1 agent: {}  |  P2 agent: {}  |  seed={}  |  ~{:.0}s estimated ({:.1} games/s)",
            a1_spec, a2_spec, seed, est_seconds, est_games_per_sec,
        );
    }
    println!();

    // win_rates[i][j] = win % of deck i when playing as player 1 vs deck j
    // (i == j entries stay 0.0 / unused)
    let mut win_rates = vec![vec![f64::NAN; n]; n];
    let mut done = 0usize;

    // Agent-level totals across the full round-robin. Agent 1 always
    // plays player 0 (the "row" side); agent 2 always plays player 1.
    let mut agent1_wins: usize = 0;
    let mut agent2_wins: usize = 0;
    let mut draws_total: usize = 0;
    let mut games_total: usize = 0;

    for i in 0..n {
        for j in 0..n {
            if i == j {
                continue;
            }
            let (deck_i, e_i) = match resolve_deck(&db, ALL_DECKS[i]) {
                Ok(d) => d,
                Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
            };
            let (deck_j, e_j) = match resolve_deck(&db, ALL_DECKS[j]) {
                Ok(d) => d,
                Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
            };

            let result = run_batch_fixed_decks(
                Arc::clone(&db),
                deck_i, deck_j,
                e_i, e_j,
                Arc::clone(&agent1),
                Arc::clone(&agent2),
                args.games,
                seed.wrapping_add((i * n + j) as u64),
            );

            win_rates[i][j] = result.win_rate_player0 * 100.0;
            agent1_wins += result.player0_wins;
            agent2_wins += result.player1_wins;
            draws_total += result.draws;
            games_total += result.total_games;
            done += 1;
            eprint!("\r  [{}/{}] {} vs {} … {:.1}% win rate", done, total_matchups, ALL_DECKS[i], ALL_DECKS[j], win_rates[i][j]);
        }
    }
    eprintln!(); // finish progress line

    // Agent-level aggregate FIRST — this is the headline: "which agent is
    // stronger overall". In symmetric mode it's ~50/50 (sanity check);
    // in asymmetric mode it's the main answer.
    print_agent_summary(
        &a1_spec,
        &a2_spec,
        agent1_wins,
        agent2_wins,
        draws_total,
        games_total,
    );

    // Deck matrix below: "which deck is best, and where does each agent
    // shine or struggle".
    print_tournament_table(
        ALL_DECKS,
        &win_rates,
        args.games,
        if symmetric { None } else { Some((a1_spec.as_str(), a2_spec.as_str())) },
    );
}

fn print_agent_summary(
    a1: &str,
    a2: &str,
    a1_wins: usize,
    a2_wins: usize,
    draws: usize,
    total: usize,
) {
    if total == 0 {
        return;
    }
    let decisive = a1_wins + a2_wins;
    let wr1 = a1_wins as f64 / total as f64 * 100.0;
    let wr2 = a2_wins as f64 / total as f64 * 100.0;
    let dr = draws as f64 / total as f64 * 100.0;
    // Score = wins + 0.5·draws — the canonical "who's ahead" metric.
    let score1 = (a1_wins as f64 + draws as f64 * 0.5) / total as f64 * 100.0;
    let score2 = (a2_wins as f64 + draws as f64 * 0.5) / total as f64 * 100.0;
    // Wilson 95% CI on the score rate (same formula as `ptcgp eval`).
    let se = (score1 / 100.0 * (1.0 - score1 / 100.0) / total as f64).sqrt();
    let ci95 = 1.96 * se * 100.0;
    // Decisive-game win rate — ignores draws.
    let dec1 = if decisive > 0 { a1_wins as f64 / decisive as f64 * 100.0 } else { 0.0 };
    let dec2 = if decisive > 0 { a2_wins as f64 / decisive as f64 * 100.0 } else { 0.0 };

    println!();
    println!("{}", "=".repeat(80));
    println!("AGENT SUMMARY  (all {} games, across all deck matchups)", total);
    println!("{}", "-".repeat(80));
    println!(
        "  Agent 1 ({}):  {} wins  ({:.1}%)",
        a1, a1_wins, wr1
    );
    println!(
        "  Agent 2 ({}):  {} wins  ({:.1}%)",
        a2, a2_wins, wr2
    );
    println!(
        "  Draws:          {}  ({:.1}%)",
        draws, dr
    );
    println!("{}", "-".repeat(80));
    println!(
        "  Agent 1 score:   {:.1}% ± {:.1}%  (wins + 0.5·draws)",
        score1, ci95
    );
    println!(
        "  Agent 2 score:   {:.1}%",
        score2
    );
    if decisive > 0 {
        println!(
            "  Decisive split:  Agent 1 = {:.1}%   Agent 2 = {:.1}%   ({} decisive games)",
            dec1, dec2, decisive
        );
    }
    // Verdict (only meaningful in asymmetric mode).
    if a1 != a2 {
        let low = score1 - ci95;
        let high = score1 + ci95;
        if low > 50.0 {
            println!(
                "  ✓ Agent 1 is stronger overall  (score lower-CI {:.1}% > 50%)",
                low
            );
        } else if high < 50.0 {
            println!(
                "  ✗ Agent 2 is stronger overall  (score upper-CI {:.1}% < 50%)",
                high
            );
        } else {
            println!(
                "  ~ No clear winner within 95% CI ({:.1}%-{:.1}%). Run more games.",
                low, high
            );
        }
    } else {
        println!("  (symmetric self-play — expected near 50/50, any skew = P0/P1 bias)");
    }
    println!("{}", "=".repeat(80));
}

fn print_tournament_table(
    names: &[&str],
    win_rates: &[Vec<f64>],
    games_per_matchup: usize,
    asymmetric: Option<(&str, &str)>,
) {
    let n = names.len();

    // Column widths — each deck name, minimum 6
    let col_w: Vec<usize> = names.iter().map(|n| n.len().max(6)).collect();
    let row_label_w = names.iter().map(|n| n.len()).max().unwrap_or(8);

    println!("\n{}", "=".repeat(80));
    match asymmetric {
        None => {
            println!("WIN RATE MATRIX  (row deck vs column deck, row deck as Player 1)");
        }
        Some((a1, a2)) => {
            println!(
                "WIN RATE MATRIX  (row={} on row-deck vs col={} on col-deck)",
                a1, a2,
            );
            println!("Cell = row-agent's win% on row-deck vs col-agent's col-deck.");
        }
    }
    println!("Games per matchup: {}", games_per_matchup);
    println!("{}", "=".repeat(80));

    // Header row
    print!("{:>width$}  ", "", width = row_label_w);
    for (j, name) in names.iter().enumerate() {
        print!("{:>width$}  ", name, width = col_w[j]);
    }
    println!("  Avg Win%  Rank");

    // Separator
    println!("{}", "-".repeat(row_label_w + 2 + col_w.iter().map(|w| w + 2).sum::<usize>() + 20));

    // Compute average win rate for each deck (excluding self-matchups)
    let avg_wins: Vec<f64> = (0..n).map(|i| {
        let sum: f64 = (0..n).filter(|&j| j != i).map(|j| win_rates[i][j]).sum();
        sum / (n - 1) as f64
    }).collect();

    // Rank by average win rate
    let mut ranking: Vec<usize> = (0..n).collect();
    ranking.sort_by(|&a, &b| avg_wins[b].partial_cmp(&avg_wins[a]).unwrap());
    let mut rank_of = vec![0usize; n];
    for (rank, &idx) in ranking.iter().enumerate() {
        rank_of[idx] = rank + 1;
    }

    // Data rows
    for i in 0..n {
        print!("{:>width$}  ", names[i], width = row_label_w);
        for j in 0..n {
            if i == j {
                print!("{:>width$}  ", "---", width = col_w[j]);
            } else {
                print!("{:>width$.1}  ", win_rates[i][j], width = col_w[j]);
            }
        }
        println!("  {:>7.1}%  #{}", avg_wins[i], rank_of[i]);
    }

    // Rankings summary
    println!("\n{}", "─".repeat(50));
    println!("RANKINGS (by avg win rate across all opponents):");
    for (rank, &idx) in ranking.iter().enumerate() {
        println!("  #{:>2}  {:>10}   {:.1}%", rank + 1, names[idx], avg_wins[idx]);
    }
    println!("{}", "=".repeat(80));
}

// ------------------------------------------------------------------ //
// profile
// ------------------------------------------------------------------ //

fn cmd_profile(args: ProfileArgs) {
    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));

    let (deck1, e1) = match resolve_deck(&db, &args.deck1) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };
    let (deck2, e2) = match resolve_deck(&db, &args.deck2) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };

    let a1 = make_agent(&args.agent1, &db);
    let a2 = make_agent(&args.agent2, &db);

    println!(
        "Profiling {} games ({}/{} vs {}/{}) single-threaded seed={}",
        args.games,
        args.deck1, args.agent1,
        args.deck2, args.agent2,
        args.seed,
    );

    let mut wins = [0usize; 2];
    let mut draws = 0usize;
    let mut total_turns = 0u64;

    let t0 = Instant::now();

    for i in 0..args.games {
        let result = run_game(
            &db,
            deck1.clone(),
            deck2.clone(),
            e1.clone(),
            e2.clone(),
            a1.as_ref(),
            a2.as_ref(),
            args.seed.wrapping_add(i as u64),
            None, // simulation — no narration
        );
        match result.winner {
            Some(0) => wins[0] += 1,
            Some(1) => wins[1] += 1,
            _       => draws  += 1,
        }
        total_turns += result.turns as u64;
    }

    let elapsed = t0.elapsed();
    let elapsed_s = elapsed.as_secs_f64();
    let games_per_sec = args.games as f64 / elapsed_s;
    let ms_per_game = elapsed_s * 1000.0 / args.games as f64;
    let avg_turns = total_turns as f64 / args.games as f64;

    let completed = wins[0] + wins[1];
    let p1_rate = if completed > 0 { wins[0] as f64 / completed as f64 } else { 0.0 };
    let p2_rate = if completed > 0 { wins[1] as f64 / completed as f64 } else { 0.0 };

    println!("\nResults:");
    println!(
        "  Player 1 ({}/{}): {} wins ({:.1}%)",
        args.deck1, args.agent1, wins[0], p1_rate * 100.0
    );
    println!(
        "  Player 2 ({}/{}): {} wins ({:.1}%)",
        args.deck2, args.agent2, wins[1], p2_rate * 100.0
    );
    println!("  Draws: {}", draws);
    println!("  Avg turns: {:.1}", avg_turns);
    println!("\nTiming:");
    println!("  Total:        {:.3}s", elapsed_s);
    println!("  Games/sec:    {:.0}", games_per_sec);
    println!("  ms/game:      {:.3}", ms_per_game);
}

// ------------------------------------------------------------------ //
// main
// ------------------------------------------------------------------ //

fn main() {
    let cli = Cli::parse();
    match cli.command {
        Commands::Simulate(args) => cmd_simulate(args),
        Commands::Play(args)     => cmd_play(args),
        Commands::Profile(args)  => cmd_profile(args),
        Commands::Decks(args)    => cmd_decks(args),
        Commands::Eval(args)     => cmd_eval(args),
    }
}

// ------------------------------------------------------------------ //
// eval — head-to-head agent benchmark
// ------------------------------------------------------------------ //

/// Agent A vs Agent B benchmark. Supports paired-seed mode (each logical
/// game is played twice with sides swapped, identical RNG) to halve
/// variance — the Wave 1 strength gate uses this.
fn cmd_eval(args: EvalArgs) {
    if let Some(w) = args.workers {
        let _ = rayon::ThreadPoolBuilder::new()
            .num_threads(w)
            .build_global();
    }

    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));
    let seed = args.seed.unwrap_or_else(random_seed);

    let (deck1, e1) = match resolve_deck(&db, &args.deck1) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };
    let (deck2, e2) = match resolve_deck(&db, &args.deck2) {
        Ok(d) => d,
        Err(e) => { eprintln!("Error: {}", e); std::process::exit(1); }
    };

    let agent_a = make_agent(&args.a, &db);
    let agent_b = make_agent(&args.b, &db);

    let total_games = if args.paired { args.games * 2 } else { args.games };
    println!(
        "Eval: A={} vs B={}  |  decks={}/{}  |  {} logical games ({} plays){}  |  seed={}",
        args.a, args.b,
        args.deck1, args.deck2,
        args.games, total_games,
        if args.paired { ", paired" } else { "" },
        seed,
    );

    let t0 = Instant::now();

    // We count wins for A specifically (across both side assignments in paired mode).
    let mut a_wins = 0usize;
    let mut b_wins = 0usize;
    let mut draws = 0usize;

    if args.paired {
        // Two batches: A-as-P0 then B-as-P0. Same seed per pair → same RNG
        // path for both plays; bot skill is the only variable.
        let r1 = run_batch_fixed_decks(
            Arc::clone(&db),
            deck1.clone(), deck2.clone(), e1.clone(), e2.clone(),
            Arc::clone(&agent_a), Arc::clone(&agent_b),
            args.games, seed,
        );
        a_wins += r1.player0_wins;
        b_wins += r1.player1_wins;
        draws += r1.draws;

        let r2 = run_batch_fixed_decks(
            Arc::clone(&db),
            deck2.clone(), deck1.clone(), e2.clone(), e1.clone(),
            Arc::clone(&agent_b), Arc::clone(&agent_a),
            args.games, seed,
        );
        // In r2, player 0 is B and player 1 is A — so A wins = r2.player1_wins.
        a_wins += r2.player1_wins;
        b_wins += r2.player0_wins;
        draws += r2.draws;
    } else {
        let r = run_batch_fixed_decks(
            Arc::clone(&db),
            deck1, deck2, e1, e2,
            Arc::clone(&agent_a), Arc::clone(&agent_b),
            args.games, seed,
        );
        a_wins = r.player0_wins;
        b_wins = r.player1_wins;
        draws = r.draws;
    }

    let elapsed = t0.elapsed().as_secs_f64();
    let wr_a = a_wins as f64 / total_games as f64;
    let wr_b = b_wins as f64 / total_games as f64;
    // Wilson 95% CI for A's win rate counting draws as 0.5 (standard for
    // "score" calculations).  This gives a more informative verdict when
    // many games time out in draws.
    let score_a = a_wins as f64 + draws as f64 * 0.5;
    let score_rate = score_a / total_games.max(1) as f64;
    let se = (score_rate * (1.0 - score_rate) / total_games.max(1) as f64).sqrt();
    let ci95 = 1.96 * se;
    // Win rate among DECISIVE games (excluding draws) — often the more
    // interesting metric when both agents are very defensive.
    let decisive = a_wins + b_wins;
    let wr_a_decisive = if decisive > 0 { a_wins as f64 / decisive as f64 } else { 0.0 };

    println!("\n{}", "=".repeat(70));
    println!("Results");
    println!("{}", "-".repeat(70));
    println!("  Agent A ({}):  {} wins  ({:.1}%)", args.a, a_wins, wr_a * 100.0);
    println!("  Agent B ({}):  {} wins  ({:.1}%)", args.b, b_wins, wr_b * 100.0);
    println!("  Draws:          {} ({:.1}%)", draws, draws as f64 / total_games as f64 * 100.0);
    println!("  A score:        {:.1}%  (wins + 0.5·draws)  ± {:.1}%", score_rate * 100.0, ci95 * 100.0);
    if decisive > 0 {
        println!(
            "  A decisive WR:  {:.1}%  ({}/{} decisive games)",
            wr_a_decisive * 100.0, a_wins, decisive
        );
    }
    println!("  Wall time:      {:.1}s  ({:.1} games/s)", elapsed, total_games as f64 / elapsed);
    println!("{}", "=".repeat(70));
    if score_rate - ci95 > 0.5 {
        println!("✓ A is stronger than B  (score lower-CI {:.1}% > 50%)", (score_rate - ci95) * 100.0);
    } else if score_rate + ci95 < 0.5 {
        println!("✗ B is stronger than A  (score upper-CI {:.1}% < 50%)", (score_rate + ci95) * 100.0);
    } else {
        println!(
            "~ No clear winner within 95% CI ({:.1}%-{:.1}%). Run more games.",
            (score_rate - ci95) * 100.0,
            (score_rate + ci95) * 100.0
        );
    }
}
