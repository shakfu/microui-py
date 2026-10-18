#!/usr/bin/env python3
"""
Context Manager Demo for PyMUI

This script demonstrates the context manager functionality of pymui.Context,
showing both manual and automatic frame management approaches.
"""

import sys
from pathlib import Path

# Add src to path for imports
ROOTDIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(ROOTDIR))

import pymui  # noqa: E402


def manual_approach_demo():
    """Demonstrate manual frame management."""
    print("Manual Approach Demo:")
    print("=" * 30)

    ctx = pymui.Context()

    # Manual begin/end with proper exception handling
    ctx.begin()
    try:
        # Create some basic objects
        position = pymui.Vec2(10, 20)
        size = pymui.Rect(0, 0, 200, 150)
        color = pymui.Color(100, 150, 200)

        # Test textbox (safe operation)
        textbox = pymui.Textbox(128)
        textbox.text = "Manual approach works!"

        print(f"✅ Position: ({position.x}, {position.y})")
        print(f"✅ Size: {size.w}x{size.h}")
        print(f"✅ Color: RGB({color.r}, {color.g}, {color.b})")
        print(f"✅ Text: '{textbox.text}'")

    finally:
        ctx.end()  # Always called, even on exceptions

    print("✅ Manual approach completed successfully")
    print()


def context_manager_demo():
    """Demonstrate context manager approach."""
    print("Context Manager Demo:")
    print("=" * 30)

    # Context manager automatically handles begin/end
    with pymui.Context():
        # Create the same objects
        position = pymui.Vec2(30, 40)
        size = pymui.Rect(0, 0, 300, 200)
        color = pymui.Color(200, 100, 50)

        # Test textbox
        textbox = pymui.Textbox(128)
        textbox.text = "Context manager is cleaner!"

        print(f"✅ Position: ({position.x}, {position.y})")
        print(f"✅ Size: {size.w}x{size.h}")
        print(f"✅ Color: RGB({color.r}, {color.g}, {color.b})")
        print(f"✅ Text: '{textbox.text}'")

    # ctx.end() was called automatically
    print("✅ Context manager completed successfully")
    print()


def exception_handling_demo():
    """Demonstrate exception handling with context manager."""
    print("Exception Handling Demo:")
    print("=" * 30)

    # Test that cleanup happens even with exceptions
    try:
        with pymui.Context():
            # Create some objects
            textbox = pymui.Textbox(64)
            textbox.text = "About to raise exception..."

            print(f"✅ Created textbox with: '{textbox.text}'")
            print("🔥 Raising intentional exception...")

            raise ValueError("Intentional test exception")

    except ValueError as e:
        print(f"✅ Exception caught: {e}")
        print("✅ Context was automatically cleaned up")

    print("✅ Exception handling demo completed")
    print()


def nested_context_demo():
    """Demonstrate multiple sequential contexts."""
    print("Multiple Sequential Contexts Demo:")
    print("=" * 30)

    # First context
    with pymui.Context():
        tb1 = pymui.Textbox(64)
        tb1.text = "First context"
        print(f"✅ Context 1: '{tb1.text}'")

    # Second context (completely separate)
    with pymui.Context():
        tb2 = pymui.Textbox(64)
        tb2.text = "Second context"
        print(f"✅ Context 2: '{tb2.text}'")

    print("✅ Multiple contexts completed successfully")
    print()


def real_world_example():
    """Demonstrate a real-world usage pattern."""
    print("Real-World Usage Example:")
    print("=" * 30)

    class SimpleApp:
        def __init__(self):
            self.counter = 0
            self.message = "Hello, PyMUI!"
            self.enabled = True

        def update_frame(self):
            """Simulate one frame update."""
            with pymui.Context():
                # In a real app, you'd have window operations here
                # For demo, we'll just show state management

                # Simulate button press
                if self.enabled and self.counter < 3:
                    self.counter += 1
                    print(f"✅ Frame {self.counter}: Button would be pressed")

                # Simulate checkbox toggle
                if self.counter == 2:
                    self.enabled = False
                    print("✅ Checkbox would be disabled")

                # Update message
                self.message = f"Frame {self.counter} processed!"

                # In real usage, you'd have UI operations like:
                # if ctx.begin_window("App", pymui.rect(10, 10, 300, 200)):
                #     ctx.label(f"Count: {self.counter}")
                #     if ctx.button("Click me"):
                #         self.counter += 1
                #     result, self.enabled = ctx.checkbox("Enabled", self.enabled)
                #     ctx.end_window()

                return self.counter < 3  # Continue simulation

    app = SimpleApp()
    frame = 0

    while app.update_frame() and frame < 5:
        frame += 1

    print(f"✅ Simulated {frame} frames successfully")
    print(f"✅ Final state: counter={app.counter}, enabled={app.enabled}")
    print()


def style_operations_demo():
    """Demonstrate style operations with context manager."""
    print("Style Operations Demo:")
    print("=" * 30)

    with pymui.Context() as ctx:
        # Get style
        style = ctx.style

        # Read current colors
        text_color = style.get_color(pymui.ColorIndex.TEXT)
        button_color = style.get_color(pymui.ColorIndex.BUTTON)

        print(f"✅ Original text color: RGB({text_color.r}, {text_color.g}, {text_color.b})")
        print(f"✅ Original button color: RGB({button_color.r}, {button_color.g}, {button_color.b})")

        # Modify colors
        new_text_color = pymui.Color(255, 255, 0)  # Yellow
        new_button_color = pymui.Color(0, 255, 255)  # Cyan

        style.set_color(pymui.ColorIndex.TEXT, new_text_color)
        style.set_color(pymui.ColorIndex.BUTTON, new_button_color)

        # Verify changes
        updated_text = style.get_color(pymui.ColorIndex.TEXT)
        updated_button = style.get_color(pymui.ColorIndex.BUTTON)

        print(f"✅ Updated text color: RGB({updated_text.r}, {updated_text.g}, {updated_text.b})")
        print(f"✅ Updated button color: RGB({updated_button.r}, {updated_button.g}, {updated_button.b})")

    print("✅ Style operations completed successfully")
    print()


def main():
    """Run all demos."""
    print("PyMUI Context Manager Demonstration")
    print("🎨🐍 Showcasing automatic frame management")
    print("=" * 50)
    print()

    # Run all demos
    manual_approach_demo()
    context_manager_demo()
    exception_handling_demo()
    nested_context_demo()
    real_world_example()
    style_operations_demo()

    print("🎉 All Context Manager Demos Completed Successfully!")
    print()
    print("Key Benefits Demonstrated:")
    print("• 🔒 Automatic cleanup (begin/end pairs)")
    print("• 🛡️  Exception safety (cleanup on errors)")
    print("• 🧹 Cleaner code (no manual frame management)")
    print("• 🐍 Pythonic (follows Python context manager idiom)")


if __name__ == "__main__":
    main()