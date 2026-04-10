use criterion::{criterion_group, criterion_main, Criterion, Throughput};
use std::sync::Arc;
use ptcgp::agents::RandomAgent;
use ptcgp::batch::run_batch_fixed_decks;
use ptcgp::card::CardDb;
use ptcgp::types::{CardKind, Element, Stage};

fn load_db() -> CardDb {
    CardDb::load_from_dir(
        std::path::Path::new("../assets/cards")
    )
}

fn make_deck(db: &CardDb) -> (Vec<u16>, Vec<Element>) {
    let basics: Vec<u16> = db.cards.iter()
        .enumerate()
        .filter(|(_, c)| matches!(c.kind, CardKind::Pokemon) && c.stage == Some(Stage::Basic) && c.hp > 0)
        .map(|(i, _)| i as u16)
        .take(10)
        .flat_map(|i| [i, i])
        .collect();
    (basics, vec![Element::Fire, Element::Water])
}

fn bench_single_game(c: &mut Criterion) {
    let db = load_db();
    let (deck0, e0) = make_deck(&db);
    let (deck1, e1) = make_deck(&db);
    let agent = RandomAgent;

    c.bench_function("single_game_random", |b| {
        b.iter(|| {
            ptcgp::runner::run_game(
                &db, deck0.clone(), deck1.clone(), e0.clone(), e1.clone(),
                &agent, &agent, 42,
            )
        })
    });
}

fn bench_batch_parallel(c: &mut Criterion) {
    let db = Arc::new(load_db());
    let (deck0, e0) = make_deck(&db);
    let (deck1, e1) = make_deck(&db);
    let agent0 = Arc::new(RandomAgent);
    let agent1 = Arc::new(RandomAgent);

    let mut group = c.benchmark_group("batch");
    group.throughput(Throughput::Elements(1000));
    group.bench_function("1000_games_parallel", |b| {
        b.iter(|| {
            run_batch_fixed_decks(
                db.clone(), deck0.clone(), deck1.clone(),
                e0.clone(), e1.clone(),
                agent0.clone(), agent1.clone(),
                1000, 0,
            )
        })
    });
    group.finish();
}

criterion_group!(benches, bench_single_game, bench_batch_parallel);
criterion_main!(benches);
