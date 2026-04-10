"""Shared test fixtures for the PTCGP battle simulator test suite."""
import pytest


# ---------------------------------------------------------------------------
# Card DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def card_db():
    """Return the populated card database loaded from a1-genetic-apex.json."""
    from ptcgp.cards.database import clear_db, load_defaults, get_all_cards
    clear_db()
    load_defaults()
    return get_all_cards()


@pytest.fixture(scope="session")
def a1_cards(card_db):
    """Dict of a1-* and related cards from the default loaded set."""
    return {cid: card for cid, card in card_db.items()}


# ---------------------------------------------------------------------------
# Sample deck fixtures (populated after Phase 1 / sample_decks.py exists)
# ---------------------------------------------------------------------------

@pytest.fixture
def grass_deck_ids():
    """Card IDs for a minimal valid grass deck (2× each basic, fillers)."""
    # Populated in Phase 4 once sample_decks.py is written
    return []


@pytest.fixture
def fire_deck_ids():
    """Card IDs for a minimal valid fire deck."""
    return []
