use pyo3::prelude::*;
use std::sync::Arc;

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

// ------------------------------------------------------------------ //
// PyCardDb
// ------------------------------------------------------------------ //

/// Python-accessible wrapper for CardDb
#[pyclass(name = "CardDb")]
struct PyCardDb {
    inner: Arc<crate::card::CardDb>,
}

#[pymethods]
impl PyCardDb {
    #[staticmethod]
    fn load_from_dir(path: &str) -> PyResult<Self> {
        let db = crate::card::CardDb::load_from_dir(std::path::Path::new(path));
        Ok(PyCardDb { inner: Arc::new(db) })
    }

    fn card_count(&self) -> usize {
        self.inner.len()
    }

    fn __repr__(&self) -> String {
        format!("CardDb({} cards)", self.inner.len())
    }
}

// ------------------------------------------------------------------ //
// PyGameResult
// ------------------------------------------------------------------ //

/// Python-accessible game result
#[pyclass(name = "GameResult")]
#[derive(Clone)]
struct PyGameResult {
    #[pyo3(get)]
    winner: Option<usize>,
    #[pyo3(get)]
    turns: u32,
    #[pyo3(get)]
    player0_points: u8,
    #[pyo3(get)]
    player1_points: u8,
}

#[pymethods]
impl PyGameResult {
    fn __repr__(&self) -> String {
        format!(
            "GameResult(winner={:?}, turns={}, p0_pts={}, p1_pts={})",
            self.winner, self.turns, self.player0_points, self.player1_points
        )
    }
}

// ------------------------------------------------------------------ //
// PyBatchResult
// ------------------------------------------------------------------ //

/// Python-accessible batch result
#[pyclass(name = "BatchResult")]
#[derive(Clone)]
struct PyBatchResult {
    #[pyo3(get)]
    total_games: usize,
    #[pyo3(get)]
    player0_wins: usize,
    #[pyo3(get)]
    player1_wins: usize,
    #[pyo3(get)]
    draws: usize,
    #[pyo3(get)]
    avg_turns: f64,
    #[pyo3(get)]
    win_rate_player0: f64,
    #[pyo3(get)]
    win_rate_player1: f64,
}

#[pymethods]
impl PyBatchResult {
    fn __repr__(&self) -> String {
        format!(
            "BatchResult(games={}, p0_wr={:.1}%, p1_wr={:.1}%, avg_turns={:.1})",
            self.total_games,
            self.win_rate_player0 * 100.0,
            self.win_rate_player1 * 100.0,
            self.avg_turns
        )
    }
}

// ------------------------------------------------------------------ //
// Helper functions
// ------------------------------------------------------------------ //

fn parse_elements(names: &[String]) -> PyResult<Vec<crate::types::Element>> {
    names
        .iter()
        .map(|s| {
            crate::types::Element::from_str(s).ok_or_else(|| {
                pyo3::exceptions::PyValueError::new_err(format!("Unknown element: {s}"))
            })
        })
        .collect()
}

fn make_agent(name: &str) -> Box<dyn crate::agents::Agent> {
    match name {
        "heuristic" => Box::new(crate::agents::HeuristicAgent),
        _ => Box::new(crate::agents::RandomAgent),
    }
}

fn make_agent_arc(name: &str) -> Arc<dyn crate::agents::Agent> {
    match name {
        "heuristic" => Arc::new(crate::agents::HeuristicAgent),
        _ => Arc::new(crate::agents::RandomAgent),
    }
}

// ------------------------------------------------------------------ //
// Python functions
// ------------------------------------------------------------------ //

#[pyfunction]
fn run_game(
    py: Python<'_>,
    db: &PyCardDb,
    deck0: Vec<u16>,
    deck1: Vec<u16>,
    energy0: Vec<String>,
    energy1: Vec<String>,
    agent0: &str,
    agent1: &str,
    seed: u64,
) -> PyResult<PyGameResult> {
    let e0 = parse_elements(&energy0)?;
    let e1 = parse_elements(&energy1)?;
    let a0 = make_agent(agent0);
    let a1 = make_agent(agent1);
    let db_inner = db.inner.clone();

    py.allow_threads(move || {
        let result = crate::runner::run_game(
            &db_inner,
            deck0,
            deck1,
            e0,
            e1,
            a0.as_ref(),
            a1.as_ref(),
            seed,
        );
        Ok(PyGameResult {
            winner: result.winner,
            turns: result.turns,
            player0_points: result.player0_points,
            player1_points: result.player1_points,
        })
    })
}

#[pyfunction]
fn run_batch(
    py: Python<'_>,
    db: &PyCardDb,
    deck0: Vec<u16>,
    deck1: Vec<u16>,
    energy0: Vec<String>,
    energy1: Vec<String>,
    agent0: &str,
    agent1: &str,
    n_games: usize,
    seed: u64,
) -> PyResult<PyBatchResult> {
    let e0 = parse_elements(&energy0)?;
    let e1 = parse_elements(&energy1)?;
    let a0: Arc<dyn crate::agents::Agent> = make_agent_arc(agent0);
    let a1: Arc<dyn crate::agents::Agent> = make_agent_arc(agent1);
    let db_arc = db.inner.clone();

    py.allow_threads(move || {
        let result = crate::batch::run_batch_fixed_decks(
            db_arc, deck0, deck1, e0, e1, a0, a1, n_games, seed,
        );
        Ok(PyBatchResult {
            total_games: result.total_games,
            player0_wins: result.player0_wins,
            player1_wins: result.player1_wins,
            draws: result.draws,
            avg_turns: result.avg_turns,
            win_rate_player0: result.win_rate_player0,
            win_rate_player1: result.win_rate_player1,
        })
    })
}

// ------------------------------------------------------------------ //
// Module registration
// ------------------------------------------------------------------ //

#[pymodule]
fn ptcgp_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyCardDb>()?;
    m.add_class::<PyGameResult>()?;
    m.add_class::<PyBatchResult>()?;
    m.add_function(wrap_pyfunction!(run_game, m)?)?;
    m.add_function(wrap_pyfunction!(run_batch, m)?)?;
    Ok(())
}
