#!/usr/bin/env python3
"""
Performance benchmarks for pymui.

This module provides benchmarks to ensure performance doesn't regress
as new features are added or code is refactored.
"""

import time
import statistics
import sys


try:
    from pymui import pymui
except ImportError:
    import pymui


def benchmark(func, iterations=1000, warmup=10):
    """Benchmark a function with multiple iterations.

    Args:
        func: Function to benchmark
        iterations: Number of timing iterations
        warmup: Number of warmup iterations

    Returns:
        dict: Benchmark results with timing statistics
    """
    # Warmup iterations
    for _ in range(warmup):
        func()

    # Actual timing
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
        'iterations': iterations
    }


class PerformanceBenchmarks:
    """Performance benchmark suite for pymui."""

    def __init__(self):
        self.ctx = pymui.Context()
        self.results = {}

    def benchmark_context_creation(self):
        """Benchmark Context creation and destruction."""
        def create_destroy():
            ctx = pymui.Context()
            del ctx

        return benchmark(create_destroy, iterations=100)

    def benchmark_basic_objects(self):
        """Benchmark creation of basic objects (Vec2, Rect, Color)."""
        def create_objects():
            v = pymui.Vec2(10, 20)
            r = pymui.Rect(0, 0, 100, 50)
            c = pymui.Color(255, 128, 64, 255)
            # Access properties to ensure they're not optimized away
            _ = v.x + r.w + c.r

        return benchmark(create_objects)

    def benchmark_frame_cycle(self):
        """Benchmark complete frame begin/end cycle."""
        def frame_cycle():
            self.ctx.begin()
            self.ctx.end()

        return benchmark(frame_cycle)

    def benchmark_simple_window(self):
        """Benchmark simple window creation."""
        def simple_window():
            self.ctx.begin()
            if self.ctx.begin_window("Benchmark", pymui.rect(10, 10, 200, 100)):
                self.ctx.end_window()
            self.ctx.end()

        return benchmark(simple_window, iterations=500)

    def benchmark_widget_creation(self):
        """Benchmark widget creation performance."""
        def create_widgets():
            self.ctx.begin()
            if self.ctx.begin_window("Widgets", pymui.rect(10, 10, 300, 200)):
                self.ctx.label("Test Label")
                self.ctx.button("Test Button")
                result, state = self.ctx.checkbox("Test Checkbox", False)
                result, value = self.ctx.slider(50.0, 0.0, 100.0)
                self.ctx.text("Some text content")
                self.ctx.end_window()
            self.ctx.end()

        return benchmark(create_widgets, iterations=200)

    def benchmark_layout_operations(self):
        """Benchmark layout operations."""
        def layout_ops():
            self.ctx.begin()
            if self.ctx.begin_window("Layout", pymui.rect(10, 10, 400, 300)):
                self.ctx.layout_row([100, 150, -1], 25)
                self.ctx.layout_begin_column()
                self.ctx.layout_width(200)
                self.ctx.layout_height(30)
                self.ctx.layout_next()
                self.ctx.layout_end_column()
                self.ctx.end_window()
            self.ctx.end()

        return benchmark(layout_ops, iterations=300)

    def benchmark_text_encoding(self):
        """Benchmark text encoding operations."""
        test_strings = [
            "Simple ASCII text",
            "Unicode: café, naïve, résumé",
            "Mixed: Hello 世界 🌍",
            "Long text: " + "A" * 100,
            "Special chars: !@#$%^&*()[]{}|\\:;\"'<>,.?/~`"
        ]

        def text_encoding():
            self.ctx.begin()
            if self.ctx.begin_window("Text", pymui.rect(10, 10, 400, 300)):
                for text in test_strings:
                    self.ctx.label(text)
                    self.ctx.text(text)
                self.ctx.end_window()
            self.ctx.end()

        return benchmark(text_encoding, iterations=100)

    def benchmark_memory_operations(self):
        """Benchmark memory-intensive operations."""
        def memory_ops():
            # Test textbox with various buffer sizes
            tb_small = pymui.Textbox(64)
            tb_medium = pymui.Textbox(256)
            tb_large = pymui.Textbox(1024)

            # Set and get text
            tb_small.text = "Small buffer test"
            tb_medium.text = "Medium buffer test with more content"
            tb_large.text = "Large buffer test " * 20

            # Access text properties
            _ = tb_small.text + tb_medium.text + tb_large.text

        return benchmark(memory_ops, iterations=500)

    def benchmark_complex_ui(self):
        """Benchmark complex UI with multiple widgets."""
        def complex_ui():
            self.ctx.begin()

            # Multiple windows
            for i in range(3):
                if self.ctx.begin_window(f"Window {i}", pymui.rect(i*150, i*100, 200, 150)):
                    self.ctx.layout_row([80, -1], 0)

                    # Multiple widgets per window
                    for j in range(5):
                        self.ctx.label(f"Label {j}")
                        if j % 2 == 0:
                            self.ctx.button(f"Button {j}")
                        else:
                            result, val = self.ctx.slider(float(j * 20), 0.0, 100.0)

                    self.ctx.end_window()

            self.ctx.end()

        return benchmark(complex_ui, iterations=50)

    def run_all_benchmarks(self):
        """Run all performance benchmarks."""
        benchmarks = [
            ("Context Creation", self.benchmark_context_creation),
            ("Basic Objects", self.benchmark_basic_objects),
            ("Frame Cycle", self.benchmark_frame_cycle),
            ("Simple Window", self.benchmark_simple_window),
            ("Widget Creation", self.benchmark_widget_creation),
            ("Layout Operations", self.benchmark_layout_operations),
            ("Text Encoding", self.benchmark_text_encoding),
            ("Memory Operations", self.benchmark_memory_operations),
            ("Complex UI", self.benchmark_complex_ui),
        ]

        print("PyMUI Performance Benchmarks")
        print("=" * 50)

        for name, benchmark_func in benchmarks:
            print(f"\nRunning {name}...")
            try:
                result = benchmark_func()
                self.results[name] = result

                print(f"  Mean: {result['mean']*1000:.3f}ms")
                print(f"  Median: {result['median']*1000:.3f}ms")
                print(f"  Min: {result['min']*1000:.3f}ms")
                print(f"  Max: {result['max']*1000:.3f}ms")
                print(f"  StdDev: {result['stdev']*1000:.3f}ms")
                print(f"  Iterations: {result['iterations']}")

            except Exception as e:
                print(f"  ERROR: {e}")
                self.results[name] = {"error": str(e)}

        return self.results

    def save_baseline(self, filename="performance_baseline.txt"):
        """Save current results as performance baseline."""
        import json
        import datetime

        baseline_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "results": self.results
        }

        with open(filename, 'w') as f:
            json.dump(baseline_data, f, indent=2)

        print(f"\nBaseline saved to {filename}")

    def compare_with_baseline(self, filename="performance_baseline.txt"):
        """Compare current results with saved baseline."""
        try:
            import json
            with open(filename, 'r') as f:
                baseline = json.load(f)

            print(f"\nComparison with baseline from {baseline['timestamp']}")
            print("=" * 60)

            baseline_results = baseline['results']

            for name, current in self.results.items():
                if name in baseline_results and 'error' not in current and 'error' not in baseline_results[name]:
                    baseline_mean = baseline_results[name]['mean']
                    current_mean = current['mean']

                    if baseline_mean > 0:
                        change_percent = ((current_mean - baseline_mean) / baseline_mean) * 100
                        change_str = f"{change_percent:+.1f}%"

                        if abs(change_percent) > 10:  # Significant change threshold
                            status = "⚠️  SIGNIFICANT" if change_percent > 0 else "✅ IMPROVED"
                        else:
                            status = "✓ OK"

                        print(f"{name:20} {current_mean*1000:6.2f}ms vs {baseline_mean*1000:6.2f}ms ({change_str:8}) {status}")
                    else:
                        print(f"{name:20} {current_mean*1000:6.2f}ms vs {baseline_mean*1000:6.2f}ms (baseline invalid)")
                else:
                    print(f"{name:20} No baseline comparison available")

        except FileNotFoundError:
            print(f"No baseline file found: {filename}")
        except Exception as e:
            print(f"Error comparing with baseline: {e}")


def test_performance_benchmarks():
    """Run performance benchmarks as a test."""
    suite = PerformanceBenchmarks()
    results = suite.run_all_benchmarks()

    errors = {name: r["error"] for name, r in results.items() if "error" in r}
    assert not errors, f"benchmarks raised: {errors}"

    # Mean only: dispersion of microsecond timings measures scheduler noise.
    for name, result in results.items():
        assert result["mean"] < 0.01, f"{name} is too slow: {result['mean'] * 1000:.3f}ms"

if __name__ == "__main__":
    suite = PerformanceBenchmarks()
    suite.run_all_benchmarks()

    # Optionally save as baseline or compare
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--save-baseline":
            suite.save_baseline()
        elif sys.argv[1] == "--compare":
            suite.compare_with_baseline()