"""Test Step 32: Complete JSON Importer for All Card Types"""
import sys
sys.path.insert(0, '.')

from v3.importers.json_card_importer import JsonCardImporter

def test_json_importer():
    """Test JSON importer for all card types"""
    importer = JsonCardImporter()
    importer.import_from_json()
    
    # Check Pokemon loaded
    assert len(importer.pokemon) > 0, f"No Pokemon loaded, got {len(importer.pokemon)}"
    
    # Check at least one Pokemon has attacks
    pokemon_with_attacks = [p for p in importer.pokemon.values() if p.attacks]
    assert len(pokemon_with_attacks) > 0, "No Pokemon with attacks"
    
    # Check attack effects are created
    pokemon_with_effects = [p for p in importer.pokemon.values() 
                           if any(a.ability and a.ability.effect for a in p.attacks)]
    assert len(pokemon_with_effects) > 0, "No Pokemon with attack effects"
    
    # Check abilities are loaded
    pokemon_with_abilities = [p for p in importer.pokemon.values() if p.abilities]
    assert len(pokemon_with_abilities) > 0, "No Pokemon with abilities"
    
    # Check Venusaur ex has heal effect
    venusaur = importer.pokemon.get("a1-004")
    if venusaur:
        giant_bloom = [a for a in venusaur.attacks if a.name == "Giant Bloom"]
        if giant_bloom:
            assert giant_bloom[0].ability is not None, "Giant Bloom should have effect"
            assert "Heal" in giant_bloom[0].ability.effect, f"Giant Bloom should heal, got {giant_bloom[0].ability.effect}"
    
    # Check Butterfree has Powder Heal ability
    butterfree = importer.pokemon.get("a1-007")
    if butterfree:
        assert len(butterfree.abilities) > 0, f"Butterfree should have abilities, got {len(butterfree.abilities)}"
        powder_heal = [a for a in butterfree.abilities if a.name == "Powder Heal"]
        assert len(powder_heal) > 0, "Butterfree should have Powder Heal"
    
    print("✓ JSON importer tests passed")
    return True

if __name__ == "__main__":
    success = test_json_importer()
    exit(0 if success else 1)

