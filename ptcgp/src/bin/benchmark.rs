use std::path::PathBuf;

/// Locate the assets/cards directory.
///
/// Search order:
/// 1. `PTCGP_ASSETS` environment variable
/// 2. `assets/cards` relative to current working directory
/// 3. Walk up from the current executable looking for `assets/cards`
/// 4. Fall back to `../assets/cards` (sibling directory)
fn find_assets_dir() -> PathBuf {
    if let Ok(p) = std::env::var("PTCGP_ASSETS") {
        return PathBuf::from(p);
    }
    let cwd_candidate = PathBuf::from("assets/cards");
    if cwd_candidate.is_dir() {
        return cwd_candidate;
    }
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
    PathBuf::from("../assets/cards")
}

fn main() {
    use std::sync::Arc;
    use std::time::Instant;
    use ptcgp::agents::RandomAgent;
    use ptcgp::batch::run_batch_fixed_decks;
    use ptcgp::card::CardDb;
    use ptcgp::types::{Element, CardKind, Stage};

    let db = Arc::new(CardDb::load_from_dir(&find_assets_dir()));

    // Build a deck where the energy matches the cards' attack costs.
    // Group basic Pokemon by their element and pick whichever has the most cards.
    let mut by_element: std::collections::HashMap<Option<Element>, Vec<u16>> =
        std::collections::HashMap::new();
    for (i, c) in db.cards.iter().enumerate() {
        if matches!(c.kind, CardKind::Pokemon) && c.stage == Some(Stage::Basic) && c.hp > 0 {
            by_element.entry(c.element).or_default().push(i as u16);
        }
    }
    // Pick the element group with the most cards.
    let (best_element, card_ids) = by_element
        .into_iter()
        .max_by_key(|(_, v)| v.len())
        .expect("No basic Pokemon found");
    let energy_element = best_element.unwrap_or(Element::Grass);
    let basics: Vec<u16> = card_ids.into_iter()
        .take(10)
        .flat_map(|i| [i, i])
        .collect();
    let energy = vec![energy_element];

    let n_games = 10_000;
    let agent = Arc::new(RandomAgent);

    println!("Rayon threads: {}", rayon::current_num_threads());

    // Warmup
    run_batch_fixed_decks(db.clone(), basics.clone(), basics.clone(),
        energy.clone(), energy.clone(), agent.clone(), agent.clone(), 100, 0);

    let start = Instant::now();
    let result = run_batch_fixed_decks(
        db.clone(), basics.clone(), basics.clone(),
        energy.clone(), energy.clone(),
        agent.clone(), agent.clone(),
        n_games, 42,
    );
    let elapsed = start.elapsed();
    let games_per_sec = n_games as f64 / elapsed.as_secs_f64();

    println!("=== PTCGP Rust Engine Benchmark ===");
    println!("Games:        {}", n_games);
    println!("Time:         {:.3}s", elapsed.as_secs_f64());
    println!("Throughput:   {:.0} games/sec", games_per_sec);
    println!("P0 win rate:  {:.1}%", result.win_rate_player0 * 100.0);
    println!("P1 win rate:  {:.1}%", result.win_rate_player1 * 100.0);
    println!("Avg turns:    {:.1}", result.avg_turns);
    println!();
    if games_per_sec >= 50_000.0 {
        println!("TARGET MET: {:.0} >= 50,000 games/sec", games_per_sec);
    } else {
        println!("Below target: {:.0} < 50,000 games/sec", games_per_sec);
    }
}
