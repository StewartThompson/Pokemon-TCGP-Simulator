"""Run all tests with proper reporting"""
import sys
import os
import subprocess
from pathlib import Path

def run_all_tests():
    """Run all test files in tests directory"""
    tests_dir = Path(__file__).parent
    test_files = sorted(tests_dir.glob("test_step*.py"))
    
    print("=" * 60)
    print("RUNNING ALL TESTS")
    print("=" * 60)
    
    results = {}
    for test_file in test_files:
        print(f"\nRunning {test_file.name}...")
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True
        )
        success = result.returncode == 0
        results[test_file.name] = success
        
        if success:
            print(f"✅ {test_file.name} PASSED")
        else:
            print(f"❌ {test_file.name} FAILED")
            print(result.stdout)
            print(result.stderr)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    return all(results.values())

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

