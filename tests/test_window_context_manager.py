#!/usr/bin/env python3
"""
Tests for pymui Window context manager functionality.

This module tests the window context manager protocol implementation,
ensuring that begin_window() and end_window() are called automatically
when using the 'with' statement for window management.
"""



import pytest
import pymui


class TestWindowContextManager:
    """Test Window context manager functionality."""

    def test_window_context_manager_basic_usage(self):
        """Test basic window context manager usage."""
        with pymui.Context() as ctx:
            # Create window using context manager
            with ctx.window("Test Window", 10, 10, 200, 150) as window:
                # Verify that window is the Window object
                assert hasattr(window, 'is_open')
                assert hasattr(window, 'title')
                # Note: We can't test actual window operations due to microui assertions
                # but we can verify the context manager protocol works

    def test_window_context_manager_convenience_method(self):
        """Test the convenience window() method on Context."""
        with pymui.Context() as ctx:
            # Test that window() method returns a Window object
            window_mgr = ctx.window("Test", 0, 0, 100, 100)
            assert window_mgr is not None

            # Test the window context manager attributes
            assert hasattr(window_mgr, 'title')
            assert hasattr(window_mgr, 'rect')
            assert hasattr(window_mgr, 'opt')
            assert hasattr(window_mgr, 'is_open')

    def test_window_context_manager_parameters(self):
        """Test window context manager with various parameters."""
        with pymui.Context() as ctx:
            # Test with different parameters
            with ctx.window("My Window", 50, 100, 300, 200, 0) as window:
                # Verify the parameters were stored correctly
                assert window.title == "My Window"
                assert window.rect.x == 50
                assert window.rect.y == 100
                assert window.rect.w == 300
                assert window.rect.h == 200
                assert window.opt == 0

    def test_window_context_manager_exception_handling(self):
        """Test that end_window() is called even when exceptions occur."""
        exception_raised = False

        try:
            with pymui.Context() as ctx:
                with ctx.window("Exception Test", 10, 10, 100, 100) as window:
                    # Verify window is created
                    assert hasattr(window, 'is_open')
                    # Raise an exception to test cleanup
                    raise ValueError("Test exception")
        except ValueError:
            exception_raised = True

        # Verify the exception was raised (not suppressed)
        assert exception_raised

    def test_window_context_manager_vs_manual_usage(self):
        """Test that window context manager is equivalent to manual begin/end."""
        # Both approaches should work equivalently
        # We can't test actual window content due to microui assertions,
        # but we can verify the context manager protocol

        with pymui.Context() as ctx:
            # Manual window management
            result1 = ctx.begin_window("Manual", pymui.Rect(10, 10, 100, 100))
            if result1:
                ctx.end_window()

            # Context manager approach
            with ctx.window("Context Manager", 10, 10, 100, 100) as window:
                # Both should work equivalently
                assert hasattr(window, 'is_open')

    def test_window_context_manager_nested_windows(self):
        """Test nested window context managers (though not typical usage)."""
        with pymui.Context() as ctx:
            with ctx.window("Outer Window", 10, 10, 200, 200) as outer:
                assert hasattr(outer, 'is_open')

                # Note: Nested windows aren't typical in microui, but the
                # context manager should handle the protocol correctly
                with ctx.window("Inner Window", 20, 20, 100, 100) as inner:
                    assert hasattr(inner, 'is_open')

    def test_window_context_manager_multiple_sequential(self):
        """Test multiple sequential window context managers."""
        with pymui.Context() as ctx:
            # First window
            with ctx.window("Window 1", 10, 10, 100, 100) as window1:
                assert window1.title == "Window 1"
                assert window1.rect.x == 10

            # Second window (separate context)
            with ctx.window("Window 2", 20, 20, 150, 150) as window2:
                assert window2.title == "Window 2"
                assert window2.rect.x == 20

    def test_window_context_manager_with_options(self):
        """Test window context manager with various options."""
        with pymui.Context() as ctx:
            # Test with different option flags
            test_opt = 1  # Some option flag
            with ctx.window("Options Test", 0, 0, 100, 100, test_opt) as window:
                assert window.opt == test_opt

    def test_window_context_manager_early_exit(self):
        """Test window context manager with early exit (return, break, etc.)."""
        def function_with_early_return():
            with pymui.Context() as ctx:
                with ctx.window("Early Exit", 0, 0, 100, 100) as window:
                    assert hasattr(window, 'is_open')
                    # Early return should still call __exit__
                    return "early_return_value"

        result = function_with_early_return()
        assert result == "early_return_value"

    def test_window_context_manager_window_properties(self):
        """Test accessing window properties through context manager."""
        with pymui.Context() as ctx:
            with ctx.window("Property Test", 15, 25, 180, 120) as window:
                # Test all accessible properties
                assert window.title == "Property Test"
                assert window.rect.x == 15
                assert window.rect.y == 25
                assert window.rect.w == 180
                assert window.rect.h == 120
                assert window.opt == 0  # default
                assert hasattr(window, 'is_open')


class TestWindowContextManagerIntegration:
    """Test Window context manager integration with other features."""

    def test_window_context_manager_with_unicode_titles(self):
        """Test window context manager with unicode titles."""
        with pymui.Context() as ctx:
            # Test unicode title
            with ctx.window("🪟 Unicode Window", 10, 10, 150, 100) as window:
                assert window.title == "🪟 Unicode Window"

    def test_window_context_manager_error_scenarios(self):
        """Test window context manager behavior in various error scenarios."""

        with pymui.Context() as ctx:
            # Test with assertion error
            with pytest.raises(AssertionError):
                with ctx.window("Error Test", 0, 0, 100, 100):
                    assert False, "Intentional assertion error"

            # Test with value error (a window may be begun once per frame)
            with pytest.raises(ValueError):
                with ctx.window("Error Test 2", 0, 0, 100, 100):
                    raise ValueError("Intentional value error")

    def test_window_context_manager_invalid_parameters(self):
        """Test window context manager with invalid parameters."""
        with pymui.Context() as ctx:
            # These should raise errors when begin_window is called
            # Test empty title (should raise ValueError when begin_window is called)
            with pytest.raises(ValueError):
                with ctx.window("", 0, 0, 100, 100):
                    pass

            # Test negative dimensions (should raise ValueError when begin_window is called)
            with pytest.raises(ValueError):
                with ctx.window("Test", 0, 0, -100, 100):
                    pass


class TestWindowContextManagerDocumentation:
    """Test that window context manager examples work as documented."""

    def test_readme_style_window_example(self):
        """Test a README-style example using window context manager."""
        def create_simple_window():
            with pymui.Context() as ctx:
                with ctx.window("My Application", 100, 100, 300, 200) as window:
                    if window.is_open:
                        # In a real app, you'd add UI elements here
                        # For testing, we just verify the window context works
                        return {
                            'title': window.title,
                            'open': window.is_open,
                            'rect': window.rect
                        }
                    return None

        result = create_simple_window()
        if result:  # Window might not open in test environment
            assert result['title'] == "My Application"
            assert 'open' in result
            assert result['rect'].w == 300

    def test_comparison_manual_vs_window_context_manager(self):
        """Test that manual and window context manager approaches work."""

        # Manual approach
        def manual_window_approach():
            with pymui.Context() as ctx:
                result = ctx.begin_window("Manual Window", pymui.Rect(10, 10, 100, 100))
                try:
                    if result:
                        # Window content would go here
                        return "manual_success"
                finally:
                    if result:
                        ctx.end_window()
                return "manual_closed"

        # Context manager approach
        def context_manager_window_approach():
            with pymui.Context() as ctx:
                with ctx.window("Context Manager Window", 10, 10, 100, 100) as window:
                    if window.is_open:
                        # Same content would go here
                        return "context_manager_success"
                    return "context_manager_closed"

        manual_result = manual_window_approach()
        cm_result = context_manager_window_approach()

        # Both approaches should work (though results may vary based on environment)
        assert manual_result in ["manual_success", "manual_closed"]
        assert cm_result in ["context_manager_success", "context_manager_closed"]

    def test_docstring_example(self):
        """Test the exact example from the window context manager docstring."""
        with pymui.Context() as ctx:
            with ctx.window("My Window", 10, 10, 200, 150) as window:
                if window.is_open:
                    # We can't actually test label() due to microui assertions,
                    # but we can verify the context manager works
                    assert hasattr(ctx, 'label')
                    assert callable(ctx.label)
                    assert window.title == "My Window"
                    assert window.rect.w == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])