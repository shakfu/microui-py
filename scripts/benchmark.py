#!/usr/bin/env python3
"""
Performance benchmarking script for pymui.

Usage:
    python scripts/benchmark.py                    # Run benchmarks
    python scripts/benchmark.py --save-baseline   # Save current results as baseline
    python scripts/benchmark.py --compare         # Compare with saved baseline
"""

import sys
import argparse
from pathlib import Path

# Add test directory to path
TESTDIR = Path(__file__).parent.parent / "tests"
sys.path.insert(0, str(TESTDIR))

from test_performance import PerformanceBenchmarks  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run pymui performance benchmarks")
    parser.add_argument("--save-baseline", action="store_true",
                        help="Save current results as performance baseline")
    parser.add_argument("--compare", action="store_true",
                        help="Compare results with saved baseline")
    parser.add_argument("--baseline-file", default="performance_baseline.txt",
                        help="Baseline file path (default: performance_baseline.txt)")

    args = parser.parse_args()

    print("PyMUI Performance Benchmarking Tool")
    print("=" * 40)

    suite = PerformanceBenchmarks()
    results = suite.run_all_benchmarks()

    if args.save_baseline:
        suite.save_baseline(args.baseline_file)

    if args.compare:
        suite.compare_with_baseline(args.baseline_file)

    # Performance regression detection
    failed_checks = 0
    print("\nPerformance Regression Checks:")
    print("-" * 40)

    for name, result in results.items():
        if 'error' not in result:
            # Check for reasonable performance thresholds
            mean_ms = result['mean'] * 1000

            if name == "Context Creation" and mean_ms > 5.0:
                print(f"❌ {name}: {mean_ms:.2f}ms (threshold: 5.0ms)")
                failed_checks += 1
            elif name == "Basic Objects" and mean_ms > 1.0:
                print(f"❌ {name}: {mean_ms:.2f}ms (threshold: 1.0ms)")
                failed_checks += 1
            elif name == "Frame Cycle" and mean_ms > 0.5:
                print(f"❌ {name}: {mean_ms:.2f}ms (threshold: 0.5ms)")
                failed_checks += 1
            elif name == "Simple Window" and mean_ms > 2.0:
                print(f"❌ {name}: {mean_ms:.2f}ms (threshold: 2.0ms)")
                failed_checks += 1
            elif name == "Widget Creation" and mean_ms > 5.0:
                print(f"❌ {name}: {mean_ms:.2f}ms (threshold: 5.0ms)")
                failed_checks += 1
            else:
                print(f"✅ {name}: {mean_ms:.2f}ms")

    if failed_checks > 0:
        print(f"\n⚠️  {failed_checks} performance checks failed!")
        return 1
    else:
        print("\n✅ All performance checks passed!")
        return 0


if __name__ == "__main__":
    exit(main())