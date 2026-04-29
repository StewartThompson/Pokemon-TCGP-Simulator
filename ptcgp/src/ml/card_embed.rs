//! Fixed per-card feature vectors.
//!
//! PTCGP has hundreds of unique cards — a learned embedding table would
//! balloon parameter count for a tiny benefit. Instead we extract a small
//! set of hand-picked numeric attributes per card, cache them once at
//! `CardDb` load time, and index them by `card_idx` at feature-encoding
//! time. Cheap, deterministic, and good enough for a value net.
//!
//! Layout: see [`CARD_EMBED_DIM`] below for the exact float layout.

use crate::card::{Card, CardDb};
use crate::types::{CardKind, Element, Stage};

/// Number of floats per card. Keep this small — it multiplies by 8 slots +
/// any hand-identity features.
pub const CARD_EMBED_DIM: usize = 15;

/// Build a per-card feature cache indexed by `card.idx`.
///
/// Returns a `Vec` that has exactly one `[f32; CARD_EMBED_DIM]` per card in
/// the database. An extra sentinel row of zeros is appended so
/// [`empty_embed`] can return a reference with the same lifetime.
pub fn build_embed_cache(db: &CardDb) -> Vec<[f32; CARD_EMBED_DIM]> {
    let mut cache = Vec::with_capacity(db.cards.len() + 1);
    for card in &db.cards {
        cache.push(embed_card(card));
    }
    // Sentinel for "no card" slots (cache.len() - 1 == db.cards.len()).
    cache.push([0.0; CARD_EMBED_DIM]);
    cache
}

/// Zero embedding — use for empty/missing slots.
#[inline]
pub fn empty_embed() -> [f32; CARD_EMBED_DIM] {
    [0.0; CARD_EMBED_DIM]
}

/// Convert one [`Card`] to its fixed feature vector.
///
/// Layout (15 floats):
/// ```text
///   [0]     hp / 300.0              (typical HP 50-200, 300 is soft ceiling)
///   [1]     retreat_cost / 4.0      (typical 0-3, 4 is ceiling)
///   [2..10] element one-hot         (Grass, Fire, Water, Lightning, Psychic,
///                                    Fighting, Darkness, Metal) — 8 slots
///   [10]    stage (0=Basic, 0.5=Stage1, 1.0=Stage2; 0 for non-Pokemon)
///   [11]    is_ex (0 or 1)
///   [12]    max attack damage / 200.0
///   [13]    has_ability (0 or 1)
///   [14]    ko_points / 3.0
/// ```
fn embed_card(card: &Card) -> [f32; CARD_EMBED_DIM] {
    let mut v = [0.0f32; CARD_EMBED_DIM];
    v[0] = card.hp as f32 / 300.0;
    v[1] = card.retreat_cost as f32 / 4.0;

    if let Some(el) = card.element {
        let idx = match el {
            Element::Grass => 2,
            Element::Fire => 3,
            Element::Water => 4,
            Element::Lightning => 5,
            Element::Psychic => 6,
            Element::Fighting => 7,
            Element::Darkness => 8,
            Element::Metal => 9,
        };
        v[idx] = 1.0;
    }

    v[10] = match card.stage {
        Some(Stage::Basic) => 0.0,
        Some(Stage::Stage1) => 0.5,
        Some(Stage::Stage2) => 1.0,
        None => 0.0, // Non-Pokemon cards don't have a stage.
    };

    v[11] = if card.is_ex { 1.0 } else { 0.0 };

    let max_dmg = card
        .attacks
        .iter()
        .map(|a| a.damage)
        .max()
        .unwrap_or(0) as f32;
    v[12] = max_dmg / 200.0;

    v[13] = if card.ability.is_some() { 1.0 } else { 0.0 };

    v[14] = card.ko_points as f32 / 3.0;

    // Non-Pokemon cards carry element=None so v[2..10] stays zero. Those
    // rows (items/supporters/tools) instead distinguish themselves via
    // ko_points=0, hp=0, and max_dmg=0 which the net can pick up.
    let _ = CardKind::Pokemon; // quiet unused-import warning if grown later

    v
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn assets_dir() -> PathBuf {
        let mut d = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        d.pop();
        d.push("assets/cards");
        d
    }

    #[test]
    fn build_cache_has_one_row_per_card_plus_sentinel() {
        let db = CardDb::load_from_dir(&assets_dir());
        let cache = build_embed_cache(&db);
        assert_eq!(cache.len(), db.cards.len() + 1);
        // Sentinel is all zeros.
        assert_eq!(cache[db.cards.len()], [0.0; CARD_EMBED_DIM]);
    }

    #[test]
    fn bulbasaur_embed_sane() {
        let db = CardDb::load_from_dir(&assets_dir());
        let bulb = db.get_by_id("a1-001").expect("a1-001 (Bulbasaur) not found");
        let cache = build_embed_cache(&db);
        let emb = cache[bulb.idx as usize];

        // HP 70 / 300 ≈ 0.233
        assert!((emb[0] - 70.0 / 300.0).abs() < 1e-4);
        // Grass = v[2]
        assert!((emb[2] - 1.0).abs() < 1e-4);
        // Basic stage → v[10] == 0
        assert_eq!(emb[10], 0.0);
        // Not ex
        assert_eq!(emb[11], 0.0);
    }
}
