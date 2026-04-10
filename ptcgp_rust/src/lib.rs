use pyo3::prelude::*;

pub mod types;
pub mod constants;
pub mod card;
pub mod state;
pub mod actions;
pub mod engine;
pub mod effects;
pub mod agents;
pub mod runner;
pub mod batch;

#[pymodule]
fn ptcgp_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}
