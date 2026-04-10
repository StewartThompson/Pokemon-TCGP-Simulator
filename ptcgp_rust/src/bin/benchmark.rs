fn main() {
    use std::sync::Arc;
    use std::time::Instant;
    use ptcgp_rust::agents::RandomAgent;
    use ptcgp_rust::batch::run_batch_fixed_decks;
    use ptcgp_rust::card::CardDb;
    use ptcgp_rust::types::{Element, CardKind, Stage};

    let db = Arc::new(CardDb::load_from_dir(
        std::path::Path::new("../assets/cards")
    ));

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
