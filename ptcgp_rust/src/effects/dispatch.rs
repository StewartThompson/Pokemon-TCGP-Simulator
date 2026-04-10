use crate::card::CardDb;
use crate::effects::{EffectKind, EffectContext};
use crate::state::GameState;

/// Apply a list of effects to the game state.
/// During Wave 4, this is a no-op stub. Wave 6 tasks will fill this in.
pub fn apply_effects(
    state: &mut GameState,
    db: &CardDb,
    effects: &[EffectKind],
    ctx: &EffectContext,
) {
    for effect in effects {
        apply_effect(state, db, effect, ctx);
    }
}

/// Dispatch a single effect. All arms are stubs (no-ops) until Wave 6.
pub fn apply_effect(
    state: &mut GameState,
    db: &CardDb,
    effect: &EffectKind,
    ctx: &EffectContext,
) {
    // Stub: all effects are no-ops until Wave 6 fills them in.
    // This allows the rest of the engine to compile and run.
    let _ = (state, db, effect, ctx);
}

/// Compute the damage modifier for an attack effect.
/// Returns (final_damage, skip_damage, extra_map)
/// Stub until Wave 6 T19 implements the real logic.
pub fn compute_damage_modifier(
    state: &GameState,
    db: &CardDb,
    base_damage: i16,
    _effects: &[EffectKind],
    _ctx: &EffectContext,
) -> (i16, bool, std::collections::HashMap<String, i32>) {
    let _ = (state, db);
    (base_damage, false, std::collections::HashMap::new())
}
