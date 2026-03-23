# Create test file: tests/test_step1_imports.py
import sys
sys.path.insert(0, '.')

def test_imports():
    """Test that all imports work"""
    try:
        from v3.models.match.player import Player
        from v3.models.match.match import Match
        from v3.models.match.battle_engine import BattleEngine
        from v3.models.cards.pokemon import Pokemon
        from v3.models.cards.card import Card
        from v3.models.cards.energy import Energy
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)

