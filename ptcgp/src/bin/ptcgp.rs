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
use ptcgp::decks::get_sample_deck;
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
}

#[derive(Args)]
struct SimulateArgs {
    #[arg(long, default_value_t = 100, help = "Number of games to simulate")]
    games: usize,
    #[arg(long, default_value = "grass", help = "Deck for player 1 (grass|fire|mewtwo|nihilego|celebi|mew|dragonite|rampardos|greninja|guzzlord|test)")]
    deck1: String,
    #[arg(long, default_value = "fire", help = "Deck for player 2 (grass|fire|mewtwo|nihilego|celebi|mew|dragonite|rampardos|greninja|guzzlord|test)")]
    deck2: String,
    #[arg(long, default_value = "heuristic", help = "Agent for player 1 (random|heuristic)")]
    agent1: String,
    #[arg(long, default_value = "heuristic", help = "Agent for player 2 (random|heuristic)")]
    agent2: String,
    #[arg(long, help = "Base random seed (default: random; printed for replay)")]
    seed: Option<u64>,
    #[arg(long, help = "Parallel Rayon workers (default: CPU count)")]
    workers: Option<usize>,
}

#[derive(Args)]
struct PlayArgs {
    #[arg(long, default_value = "grass", help = "Your deck (grass|fire|mewtwo|nihilego|celebi|mew|dragonite|rampardos|greninja|guzzlord|test)")]
    deck: String,
    #[arg(long, default_value = "fire", help = "Opponent's deck (grass|fire|mewtwo|nihilego|celebi|mew|dragonite|rampardos|greninja|guzzlord|test)")]
    opponent: String,
    #[arg(long, help = "Random seed (default: random; printed for replay)")]
    seed: Option<u64>,
}

#[derive(Args)]
struct DecksArgs {
    #[arg(long, default_value_t = 100, help = "Number of games per matchup")]
    games: usize,
    #[arg(long, default_value = "heuristic", help = "Agent for both players (random|heuristic)")]
    agent: String,
    #[arg(long, help = "Parallel Rayon workers (default: CPU count)")]
    workers: Option<usize>,
}

#[derive(Args)]
struct ProfileArgs {
    #[arg(long, default_value_t = 1000, help = "Number of games to run")]
    games: usize,
    #[arg(long, default_value = "grass", help = "Deck for player 1 (grass|fire|mewtwo|nihilego|celebi|mew|dragonite|rampardos|greninja|guzzlord|test)")]
    deck1: String,
    #[arg(long, default_value = "fire", help = "Deck for player 2 (grass|fire|mewtwo|nihilego|celebi|mew|dragonite|rampardos|greninja|guzzlord|test)")]
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

fn make_agent(name: &str) -> Arc<dyn Agent> {
    match name.trim().to_lowercase().as_str() {
        "random" => Arc::new(RandomAgent),
        _        => Arc::new(HeuristicAgent),
    }
}

/// Resolve a named deck to `(Vec<u16>, Vec<Element>)` using the CardDb.
fn resolve_deck(db: &CardDb, name: &str) -> Result<(Vec<u16>, Vec<Element>), String> {
    let (ids, energy) = get_sample_deck(name)
        .ok_or_else(|| format!("Unknown deck '{}'. Available: grass, fire, mewtwo, nihilego, celebi, mew, dragonite, rampardos, greninja", name))?;

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

    let agent1 = make_agent(&args.agent1);
    let agent2 = make_agent(&args.agent2);

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

    println!("Starting game: {} deck vs {} deck (AI)", args.deck, args.opponent);
    println!("seed={} (re-run with --seed {} to replay this exact game)", seed, seed);
    println!("Enter the number of your chosen action when prompted.\n");

    let human = HumanAgent::new(0);
    let ai    = HeuristicAgent;

    let result = run_game(
        &db,
        deck_human,
        deck_opp,
        energy_human,
        energy_opp,
        &human,
        &ai,
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

const ALL_DECKS: &[&str] = &[
    "grass", "fire", "mewtwo", "nihilego", "celebi",
    "mew", "dragonite", "rampardos", "greninja", "guzzlord",
    "baxcalibur", "greninja2", "test",
];

fn cmd_decks(args: DecksArgs) {
    if let Some(w) = args.workers {
        let _ = rayon::ThreadPoolBuilder::new()
            .num_threads(w)
            .build_global();
    }

    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));
    let seed = random_seed();
    let n = ALL_DECKS.len();
    let agent = make_agent(&args.agent);
    let total_matchups = n * (n - 1);

    println!(
        "Round-robin tournament: {} decks × {} games/matchup = {} total games",
        n,
        args.games,
        total_matchups * args.games,
    );
    println!("Agent: {}  |  seed={}", args.agent, seed);
    println!();

    // win_rates[i][j] = win % of deck i when playing as player 1 vs deck j
    // (i == j entries stay 0.0 / unused)
    let mut win_rates = vec![vec![f64::NAN; n]; n];
    let mut done = 0usize;

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
                Arc::clone(&agent),
                Arc::clone(&agent),
                args.games,
                seed.wrapping_add((i * n + j) as u64),
            );

            win_rates[i][j] = result.win_rate_player0 * 100.0;
            done += 1;
            eprint!("\r  [{}/{}] {} vs {} … {:.1}% win rate", done, total_matchups, ALL_DECKS[i], ALL_DECKS[j], win_rates[i][j]);
        }
    }
    eprintln!(); // finish progress line

    print_tournament_table(ALL_DECKS, &win_rates, args.games);
}

fn print_tournament_table(names: &[&str], win_rates: &[Vec<f64>], games_per_matchup: usize) {
    let n = names.len();

    // Column widths — each deck name, minimum 6
    let col_w: Vec<usize> = names.iter().map(|n| n.len().max(6)).collect();
    let row_label_w = names.iter().map(|n| n.len()).max().unwrap_or(8);

    println!("\n{}", "=".repeat(80));
    println!("WIN RATE MATRIX  (row deck vs column deck, row deck as Player 1)");
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

    let a1 = make_agent(&args.agent1);
    let a2 = make_agent(&args.agent2);

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
    }
}
