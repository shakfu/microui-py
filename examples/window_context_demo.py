#!/usr/bin/env python3
"""
Window Context Manager Demo for PyMUI

This script demonstrates the window context manager functionality,
showing how to use pymui.Context.window() for automatic window management.
"""

import sys
from pathlib import Path

# Add src to path for imports
ROOTDIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(ROOTDIR))

import pymui  # noqa: E402


def basic_window_demo():
    """Demonstrate basic window context manager usage."""
    print("Basic Window Context Manager Demo:")
    print("=" * 40)

    with pymui.Context() as ctx:
        # Using window context manager - automatic begin/end
        with ctx.window("Basic Window", 10, 10, 300, 200) as window:
            if window.is_open:
                print(f"✅ Window opened: '{window.title}'")
                print(f"✅ Position: ({window.rect.x}, {window.rect.y})")
                print(f"✅ Size: {window.rect.w}x{window.rect.h}")
                print(f"✅ Options: {window.opt}")

                # In a real app, you'd add UI elements here:
                # ctx.label("Hello, World!")
                # if ctx.button("Click me"):
                #     print("Button clicked!")
            else:
                print("❌ Window did not open (expected in test environment)")

    print("✅ Window automatically closed via context manager")
    print()


def comparison_demo():
    """Compare manual vs context manager approaches."""
    print("Manual vs Context Manager Comparison:")
    print("=" * 40)

    # Manual approach
    print("Manual approach:")
    with pymui.Context() as ctx:
        result = ctx.begin_window("Manual Window", pymui.Rect(20, 20, 250, 150))
        try:
            if result:
                print("✅ Manual window opened")
                # Window content would go here
            else:
                print("❌ Manual window did not open")
        finally:
            if result:
                ctx.end_window()
                print("✅ Manual window closed with end_window()")

    print()

    # Context manager approach
    print("Context manager approach:")
    with pymui.Context() as ctx:
        with ctx.window("Context Manager Window", 20, 20, 250, 150) as window:
            if window.is_open:
                print("✅ Context manager window opened")
                # Same window content would go here
            else:
                print("❌ Context manager window did not open")
        # end_window() called automatically

    print("✅ Context manager window closed automatically")
    print()


def multiple_windows_demo():
    """Demonstrate multiple sequential windows."""
    print("Multiple Sequential Windows Demo:")
    print("=" * 40)

    with pymui.Context() as ctx:
        # First window
        with ctx.window("Window 1", 50, 50, 200, 100) as window1:
            print(f"✅ {window1.title} - open: {window1.is_open}")

        # Second window (completely separate)
        with ctx.window("Window 2", 100, 100, 250, 120) as window2:
            print(f"✅ {window2.title} - open: {window2.is_open}")

        # Third window with options
        with ctx.window("Window 3", 150, 150, 300, 140, 1) as window3:
            print(f"✅ {window3.title} - open: {window3.is_open}, options: {window3.opt}")

    print("✅ All windows closed automatically")
    print()


def exception_handling_demo():
    """Demonstrate exception safety with window context manager."""
    print("Exception Handling Demo:")
    print("=" * 40)

    try:
        with pymui.Context() as ctx:
            with ctx.window("Exception Test", 10, 10, 200, 100) as window:
                if window.is_open:
                    print(f"✅ Window opened: {window.title}")

                print("🔥 Raising intentional exception...")
                raise ValueError("Test exception in window context")

    except ValueError as e:
        print(f"✅ Exception caught: {e}")
        print("✅ Window was automatically closed despite exception")

    print()


def property_access_demo():
    """Demonstrate accessing window properties."""
    print("Window Property Access Demo:")
    print("=" * 40)

    with pymui.Context() as ctx:
        with ctx.window("Property Demo", 100, 200, 350, 250, 42) as window:
            # Access all window properties
            print(f"✅ Title: '{window.title}'")
            print(f"✅ Rectangle: x={window.rect.x}, y={window.rect.y}, w={window.rect.w}, h={window.rect.h}")
            print(f"✅ Options: {window.opt}")
            print(f"✅ Is Open: {window.is_open}")

            # Properties are read-only (stored from creation time)
            assert window.title == "Property Demo"
            assert window.rect.x == 100
            assert window.rect.y == 200
            assert window.rect.w == 350
            assert window.rect.h == 250
            assert window.opt == 42

    print()


def main():
    """Run all window context manager demos."""
    print("PyMUI Window Context Manager Demonstration")
    print("🪟🐍 Showcasing automatic window management")
    print("=" * 50)
    print()

    # Run all demos
    basic_window_demo()
    comparison_demo()
    multiple_windows_demo()
    exception_handling_demo()
    property_access_demo()

    print("🎉 All Window Context Manager Demos Completed Successfully!")
    print()
    print("Key Benefits Demonstrated:")
    print("• 🔒 Automatic window cleanup (begin_window/end_window pairs)")
    print("• 🛡️  Exception safety (end_window called on errors)")
    print("• 🧹 Cleaner code (no manual window management)")
    print("• 🐍 Pythonic (follows Python context manager idiom)")
    print("• 📝 Clear window state (is_open property)")
    print("• 🎯 Convenient API (ctx.window() method)")


if __name__ == "__main__":
    main()