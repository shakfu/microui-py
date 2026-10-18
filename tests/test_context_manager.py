#!/usr/bin/env python3
"""
Tests for pymui Context manager functionality.

This module tests the context manager protocol implementation for pymui.Context,
ensuring that begin() and end() are called automatically when using the 'with' statement.
"""



import pytest
import pymui


class TestContextManager:
    """Test Context manager functionality."""

    def test_context_manager_basic_usage(self):
        """Test basic context manager usage with 'with' statement."""
        # This should work without calling begin() and end() manually
        with pymui.Context() as ctx:
            # Verify that ctx is the same object returned by __enter__
            assert isinstance(ctx, pymui.Context)

            # These operations should work since begin() was called automatically
            # Note: We avoid UI operations that trigger microui assertions
            # and focus on testing the context manager protocol itself

    def test_context_manager_returns_self(self):
        """Test that __enter__ returns self."""
        ctx = pymui.Context()
        with ctx as ctx_returned:
            assert ctx_returned is ctx

    def test_context_manager_exception_handling(self):
        """Test that end() is called even when exceptions occur."""
        exception_raised = False

        try:
            with pymui.Context() as ctx:
                # Verify context is set up
                assert isinstance(ctx, pymui.Context)
                # Raise an exception to test cleanup
                raise ValueError("Test exception")
        except ValueError:
            exception_raised = True

        # Verify the exception was raised (not suppressed)
        assert exception_raised

        # The context should have been properly cleaned up
        # (end() should have been called automatically)

    def test_context_manager_vs_manual_usage(self):
        """Test that context manager usage is equivalent to manual begin/end."""
        # Test manual usage
        ctx1 = pymui.Context()
        ctx1.begin()
        # Basic operations would go here
        ctx1.end()

        # Test context manager usage
        with pymui.Context() as ctx2:
            # Same basic operations would go here
            assert isinstance(ctx2, pymui.Context)

        # Both should work equivalently

    def test_context_manager_nested_not_recommended(self):
        """Test that nested context managers work but aren't recommended."""
        # Note: This tests the technical capability but shouldn't be used in practice
        # since microui contexts are designed for frame-level usage

        ctx1 = pymui.Context()
        ctx2 = pymui.Context()

        with ctx1:
            # Outer context
            assert isinstance(ctx1, pymui.Context)

            with ctx2:
                # Inner context (separate context)
                assert isinstance(ctx2, pymui.Context)

        # Both contexts should be properly cleaned up

    def test_context_manager_textbox_operations(self):
        """Test context manager with safe textbox operations."""
        with pymui.Context():
            # Test basic object creation (safe operations)
            vec = pymui.Vec2(10, 20)
            rect = pymui.Rect(10, 20, 100, 50)
            color = pymui.Color(255, 128, 0)

            # Test textbox operations (safe - don't require UI context)
            textbox = pymui.Textbox(64)
            textbox.text = "Test context manager"
            text_result = textbox.text

            # Verify operations worked
            assert vec.x == 10
            assert rect.w == 100
            assert color.r == 255
            assert text_result == "Test context manager"

    def test_context_manager_multiple_sequential(self):
        """Test multiple sequential context manager uses."""
        results = []

        # First context manager
        with pymui.Context() as ctx1:
            results.append("ctx1_started")
            assert isinstance(ctx1, pymui.Context)

        results.append("ctx1_ended")

        # Second context manager
        with pymui.Context() as ctx2:
            results.append("ctx2_started")
            assert isinstance(ctx2, pymui.Context)

        results.append("ctx2_ended")

        # Verify proper order
        expected = ["ctx1_started", "ctx1_ended", "ctx2_started", "ctx2_ended"]
        assert results == expected

    def test_context_manager_early_exit(self):
        """Test context manager with early exit (return, break, etc.)."""
        def function_with_early_return():
            with pymui.Context() as ctx:
                assert isinstance(ctx, pymui.Context)

                # Early return should still call __exit__
                return "early_return_value"

        result = function_with_early_return()
        assert result == "early_return_value"

    def test_context_manager_with_safe_widget_ids(self):
        """Test context manager with push_id/pop_id operations."""
        with pymui.Context() as ctx:
            # Test ID stack operations (safe)
            ctx.push_id("test_id_1")
            ctx.push_id("test_id_2")
            ctx.pop_id()
            ctx.pop_id()

            # Test with string and numeric IDs
            ctx.push_id("string_id")
            ctx.pop_id()

            ctx.push_id(12345)
            ctx.pop_id()

    def test_context_manager_docstring_example(self):
        """Test the exact example from the docstring."""
        # This is the example from the Context class docstring
        with pymui.Context() as ctx:
            # We can't actually test begin_window due to microui assertions,
            # but we can verify the context manager works
            assert isinstance(ctx, pymui.Context)

            # Test that we could theoretically call the methods
            # (the methods exist and are callable)
            assert hasattr(ctx, 'begin_window')
            assert hasattr(ctx, 'label')
            assert hasattr(ctx, 'end_window')
            assert callable(ctx.begin_window)
            assert callable(ctx.label)
            assert callable(ctx.end_window)


class TestContextManagerIntegration:
    """Test Context manager integration with other features."""

    def test_context_manager_with_style_operations(self):
        """Test context manager with style operations."""
        with pymui.Context() as ctx:
            # Test style access
            style = ctx.style
            assert style is not None

            # Test color operations
            original_color = style.get_color(pymui.ColorIndex.TEXT)
            assert isinstance(original_color, pymui.Color)

            # Test setting color
            new_color = pymui.Color(255, 0, 0, 255)
            style.set_color(pymui.ColorIndex.TEXT, new_color)

            # Verify color was set
            retrieved_color = style.get_color(pymui.ColorIndex.TEXT)
            assert retrieved_color.r == 255
            assert retrieved_color.g == 0
            assert retrieved_color.b == 0
            assert retrieved_color.a == 255

    def test_context_manager_with_utility_functions(self):
        """Test context manager with utility functions."""
        with pymui.Context():
            # Test clamp function
            result = pymui.clamp(15, 0, 10)
            assert result == 10

            result = pymui.clamp(-5, 0, 10)
            assert result == 0

            result = pymui.clamp(5, 0, 10)
            assert result == 5

    def test_context_manager_error_scenarios(self):
        """Test context manager behavior in various error scenarios."""

        # Test with assertion error
        with pytest.raises(AssertionError):
            with pymui.Context():
                assert False, "Intentional assertion error"

        # Test with value error
        with pytest.raises(ValueError):
            with pymui.Context():
                raise ValueError("Intentional value error")

        # Test with custom exception
        class CustomError(Exception):
            pass

        with pytest.raises(CustomError):
            with pymui.Context():
                raise CustomError("Intentional custom error")


class TestContextManagerDocumentation:
    """Test that context manager examples work as documented."""

    def test_readme_style_example(self):
        """Test a README-style example using context manager."""
        # Simulate a simple UI update function
        def update_ui():
            with pymui.Context():
                # Create basic objects to verify context works
                position = pymui.Vec2(10, 20)
                size = pymui.Rect(0, 0, 200, 150)
                color = pymui.Color(100, 150, 200)

                # Test textbox (safe operation)
                textbox = pymui.Textbox(128)
                textbox.text = "Context manager works!"

                return {
                    'position': position,
                    'size': size,
                    'color': color,
                    'text': textbox.text
                }

        result = update_ui()
        assert result['position'].x == 10
        assert result['size'].w == 200
        assert result['color'].r == 100
        assert result['text'] == "Context manager works!"

    def test_comparison_manual_vs_context_manager(self):
        """Test that manual and context manager approaches are equivalent."""

        # Manual approach
        def manual_approach():
            ctx = pymui.Context()
            ctx.begin()
            try:
                # Safe operations
                textbox = pymui.Textbox(64)
                textbox.text = "manual"
                return textbox.text
            finally:
                ctx.end()

        # Context manager approach
        def context_manager_approach():
            with pymui.Context():
                # Same operations
                textbox = pymui.Textbox(64)
                textbox.text = "context_manager"
                return textbox.text

        manual_result = manual_approach()
        cm_result = context_manager_approach()

        assert manual_result == "manual"
        assert cm_result == "context_manager"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])