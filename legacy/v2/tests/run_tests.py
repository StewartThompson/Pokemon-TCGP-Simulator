#!/usr/bin/env python3
"""
Simple test runner for JSON Card Importer tests

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit-only        # Run only unit tests
    python run_tests.py --integration-only # Run only integration tests
    python run_tests.py --quick            # Run quick smoke test
"""

import sys
import argparse
import os

# Add the v2 directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def run_quick_smoke_test():
    """Run a quick smoke test to verify basic functionality"""
    print("🚀 Running Quick Smoke Test...")
    
    try:
        from import_files.json_card_importer import JsonCardImporter
        
        # Test basic instantiation
        importer = JsonCardImporter()
        print("✅ JsonCardImporter instantiation successful")
        
        # Test energy mapping
        test_energies = ["Fire", "Water", "Lightning", "Colorless"]
        cost = importer.parse_energy_cost(test_energies)
        print("✅ Energy parsing successful")
        
        # Test sample card creation
        sample_pokemon_data = {
            "id": "smoke_test_001",
            "name": "Test Pokemon",
            "type": "pokemon",
            "subtype": "Basic",
            "element": "Fire",
            "health": 60,
            "set": "test",
            "pack": "test",
            "attacks": [],
            "abilities": []
        }
        
        pokemon = importer.create_pokemon(sample_pokemon_data)
        print("✅ Pokemon creation successful")
        
        print("\n🎉 Quick smoke test PASSED! All basic functionality working.")
        return True
        
    except Exception as e:
        print(f"❌ Quick smoke test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Run JSON Card Importer tests")
    parser.add_argument("--unit-only", action="store_true", 
                       help="Run only unit tests")
    parser.add_argument("--integration-only", action="store_true",
                       help="Run only integration tests")
    parser.add_argument("--quick", action="store_true",
                       help="Run quick smoke test only")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    if args.quick:
        success = run_quick_smoke_test()
        sys.exit(0 if success else 1)
    
    # Import the test module
    try:
        from test_json_card_importer import run_comprehensive_test, run_integration_test
    except ImportError as e:
        print(f"❌ Failed to import test module: {e}")
        print("Make sure you're running from the tests directory and all dependencies are available.")
        sys.exit(1)
    
    success = True
    
    if args.unit_only:
        print("Running unit tests only...")
        success = run_comprehensive_test()
        
    elif args.integration_only:
        print("Running integration tests only...")
        success = run_integration_test()
        
    else:
        # Run both unit and integration tests
        print("Running all tests...")
        unit_success = run_comprehensive_test()
        integration_success = run_integration_test()
        success = unit_success and integration_success
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 