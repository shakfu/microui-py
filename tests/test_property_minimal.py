#!/usr/bin/env python3
"""
Minimal property-based tests for pymui.

This focuses on data structure properties without complex UI operations
to avoid crashes while still providing comprehensive edge case testing.
"""



try:
    from hypothesis import given
    from hypothesis.strategies import integers
except ImportError:
    import pytest
    pytest.skip("Hypothesis not available", allow_module_level=True)

try:
    from pymui import pymui
except ImportError:
    import pymui


class TestDataStructureProperties:
    """Property-based tests for basic data structures."""

    @given(x=integers(min_value=-10000, max_value=10000),
           y=integers(min_value=-10000, max_value=10000))
    def test_vec2_invariants(self, x, y):
        """Test Vec2 invariants and properties."""
        vec = pymui.Vec2(x, y)

        # Basic properties
        assert vec.x == x
        assert vec.y == y

        # Mutation should work
        new_x, new_y = x + 1, y - 1
        vec.x = new_x
        vec.y = new_y
        assert vec.x == new_x
        assert vec.y == new_y

        # String representation should be reasonable
        repr_str = repr(vec)
        assert "Vec2" in repr_str
        assert isinstance(repr_str, str)
        assert len(repr_str) > 0

    @given(x=integers(min_value=-10000, max_value=10000),
           y=integers(min_value=-10000, max_value=10000),
           w=integers(min_value=0, max_value=10000),
           h=integers(min_value=0, max_value=10000))
    def test_rect_invariants(self, x, y, w, h):
        """Test Rect invariants and properties."""
        rect = pymui.Rect(x, y, w, h)

        # Basic properties
        assert rect.x == x
        assert rect.y == y
        assert rect.w == w
        assert rect.h == h

        # String representation should be reasonable
        repr_str = repr(rect)
        assert "Rect" in repr_str
        assert isinstance(repr_str, str)

    @given(r=integers(min_value=0, max_value=255),
           g=integers(min_value=0, max_value=255),
           b=integers(min_value=0, max_value=255),
           a=integers(min_value=0, max_value=255))
    def test_color_invariants(self, r, g, b, a):
        """Test Color invariants and properties."""
        color = pymui.Color(r, g, b, a)

        # Basic properties
        assert color.r == r
        assert color.g == g
        assert color.b == b
        assert color.a == a

        # Components should stay in valid range
        assert 0 <= color.r <= 255
        assert 0 <= color.g <= 255
        assert 0 <= color.b <= 255
        assert 0 <= color.a <= 255

    @given(r=integers(min_value=0, max_value=255),
           g=integers(min_value=0, max_value=255),
           b=integers(min_value=0, max_value=255))
    def test_color_default_alpha_consistency(self, r, g, b):
        """Test that default alpha is consistently applied."""
        color = pymui.Color(r, g, b)
        assert color.a == 255

    @given(buffer_size=integers(min_value=2, max_value=1024))
    def test_textbox_creation_properties(self, buffer_size):
        """Test Textbox creation properties."""
        textbox = pymui.Textbox(buffer_size)

        # Initial state should be empty
        assert textbox.text == ""

        # Should be able to set and get text
        textbox.text = "test"
        result = textbox.text
        # For very small buffers, text may be truncated
        if buffer_size >= len("test".encode('utf-8')) + 1:
            assert result == "test"
        else:
            # Text was truncated but should not crash
            assert isinstance(result, str)

    def test_clamp_basic_properties(self):
        """Test basic properties of clamp function with simple values."""
        # Test with integers to avoid floating point issues
        assert pymui.clamp(5, 0, 10) == 5      # Within range
        assert pymui.clamp(-1, 0, 10) == 0     # Below range
        assert pymui.clamp(15, 0, 10) == 10    # Above range
        assert pymui.clamp(5, 5, 5) == 5       # Equal bounds

        # Test with floats at safe values
        assert pymui.clamp(5.5, 0.0, 10.0) == 5.5


class TestGlobalFunctionProperties:
    """Property-based tests for global convenience functions."""

    @given(x=integers(min_value=-1000, max_value=1000),
           y=integers(min_value=-1000, max_value=1000))
    def test_vec2_function_consistency(self, x, y):
        """Global vec2() should be consistent with Vec2() constructor."""
        direct = pymui.Vec2(x, y)
        via_function = pymui.vec2(x, y)

        assert direct.x == via_function.x
        assert direct.y == via_function.y

    @given(x=integers(min_value=-1000, max_value=1000),
           y=integers(min_value=-1000, max_value=1000),
           w=integers(min_value=0, max_value=1000),
           h=integers(min_value=0, max_value=1000))
    def test_rect_function_consistency(self, x, y, w, h):
        """Global rect() should be consistent with Rect() constructor."""
        direct = pymui.Rect(x, y, w, h)
        via_function = pymui.rect(x, y, w, h)

        assert direct.x == via_function.x
        assert direct.y == via_function.y
        assert direct.w == via_function.w
        assert direct.h == via_function.h

    @given(r=integers(min_value=0, max_value=255),
           g=integers(min_value=0, max_value=255),
           b=integers(min_value=0, max_value=255),
           a=integers(min_value=0, max_value=255))
    def test_color_function_consistency(self, r, g, b, a):
        """Global color() should be consistent with Color() constructor."""
        direct = pymui.Color(r, g, b, a)
        via_function = pymui.color(r, g, b, a)

        assert direct.r == via_function.r
        assert direct.g == via_function.g
        assert direct.b == via_function.b
        assert direct.a == via_function.a


class TestMemorySafetyProperties:
    """Property-based tests for memory safety."""

    @given(text_length=integers(min_value=0, max_value=100))
    def test_textbox_buffer_safety(self, text_length):
        """Test that textbox operations are memory safe."""
        buffer_size = 50
        textbox = pymui.Textbox(buffer_size)

        # Create text of specified length
        test_text = "A" * text_length

        # This should not crash regardless of text length
        textbox.text = test_text
        result = textbox.text

        # Result should be a string
        assert isinstance(result, str)

        # Result should not exceed buffer capacity
        assert len(result.encode('utf-8')) < buffer_size

    @given(iterations=integers(min_value=1, max_value=20))
    def test_repeated_context_creation(self, iterations):
        """Test that repeated Context creation/destruction is stable."""
        contexts = []

        # Create multiple contexts
        for _ in range(iterations):
            ctx = pymui.Context()
            contexts.append(ctx)

        # All should be valid
        for ctx in contexts:
            assert isinstance(ctx, pymui.Context)

        # Clean up (destructors should handle this safely)
        del contexts


class TestEdgeCaseRegression:
    """Tests for specific edge cases that have been problematic."""

    def test_zero_dimensions(self):
        """Test zero dimensions are handled safely."""
        # Zero-size rect
        rect = pymui.Rect(0, 0, 0, 0)
        assert rect.w == 0
        assert rect.h == 0

        # Zero position
        vec = pymui.Vec2(0, 0)
        assert vec.x == 0
        assert vec.y == 0

    def test_boundary_values(self):
        """Test boundary values for all types."""
        # Color boundaries
        black = pymui.Color(0, 0, 0, 0)
        white = pymui.Color(255, 255, 255, 255)
        assert black.r == 0 and white.r == 255

        # Minimum textbox
        textbox = pymui.Textbox(2)  # Minimum size
        textbox.text = ""
        assert textbox.text == ""

    def test_large_values(self):
        """Test large but reasonable values."""
        # Large coordinates
        big_vec = pymui.Vec2(1000000, -1000000)
        assert big_vec.x == 1000000
        assert big_vec.y == -1000000

        # Large rect
        big_rect = pymui.Rect(-100000, -100000, 200000, 200000)
        assert big_rect.w == 200000
        assert big_rect.h == 200000


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])