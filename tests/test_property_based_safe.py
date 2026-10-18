#!/usr/bin/env python3
"""
Safe property-based tests for pymui using Hypothesis.

This module focuses on property-based testing that avoids known issues
while still providing comprehensive edge case coverage.
"""

import pytest

try:
    from hypothesis import given
    from hypothesis.strategies import integers, floats
except ImportError:
    pytest.skip("Hypothesis not available", allow_module_level=True)

try:
    from pymui import pymui
except ImportError:
    import pymui


def begin_in_window(ctx):
    """Start a frame with one window open; widgets need a window's layout."""
    ctx.begin()
    assert ctx.begin_window("Property test", pymui.Rect(0, 0, 400, 300))


def end_in_window(ctx):
    ctx.end_window()
    ctx.end()


class TestBasicDataStructures:
    """Property-based tests for basic data structures (Vec2, Rect, Color)."""

    @given(x=integers(min_value=-10000, max_value=10000),
           y=integers(min_value=-10000, max_value=10000))
    def test_vec2_roundtrip(self, x, y):
        """Vec2 values should roundtrip through creation and property access."""
        vec = pymui.Vec2(x, y)
        assert vec.x == x
        assert vec.y == y

        # Test property modification
        new_x, new_y = x + 1, y + 1
        vec.x = new_x
        vec.y = new_y
        assert vec.x == new_x
        assert vec.y == new_y

    @given(x=integers(min_value=-10000, max_value=10000),
           y=integers(min_value=-10000, max_value=10000),
           w=integers(min_value=0, max_value=10000),
           h=integers(min_value=0, max_value=10000))
    def test_rect_roundtrip(self, x, y, w, h):
        """Rect values should roundtrip through creation and property access."""
        rect = pymui.Rect(x, y, w, h)
        assert rect.x == x
        assert rect.y == y
        assert rect.w == w
        assert rect.h == h

    @given(r=integers(min_value=0, max_value=255),
           g=integers(min_value=0, max_value=255),
           b=integers(min_value=0, max_value=255),
           a=integers(min_value=0, max_value=255))
    def test_color_roundtrip(self, r, g, b, a):
        """Color values should roundtrip through creation and property access."""
        color = pymui.Color(r, g, b, a)
        assert color.r == r
        assert color.g == g
        assert color.b == b
        assert color.a == a

    @given(r=integers(min_value=0, max_value=255),
           g=integers(min_value=0, max_value=255),
           b=integers(min_value=0, max_value=255))
    def test_color_default_alpha_property(self, r, g, b):
        """Color should consistently use default alpha value."""
        color = pymui.Color(r, g, b)
        assert color.a == 255


class TestTextboxMemorySafety:
    """Property-based tests for Textbox memory safety."""

    @given(buffer_size=integers(min_value=2, max_value=512))
    def test_textbox_buffer_sizes(self, buffer_size):
        """Textbox should handle various buffer sizes safely."""
        textbox = pymui.Textbox(buffer_size)
        assert textbox.text == ""

        # Test setting empty text
        textbox.text = ""
        assert textbox.text == ""

    @given(buffer_size=integers(min_value=8, max_value=128))
    def test_textbox_ascii_text(self, buffer_size):
        """Textbox should handle ASCII text safely."""
        textbox = pymui.Textbox(buffer_size)

        # Test with ASCII text of various lengths
        test_texts = [
            "",
            "a",
            "hello",
            "Hello World!",
            "A" * (buffer_size // 2),  # Half buffer
            "B" * (buffer_size - 2),   # Nearly full buffer
        ]

        for test_text in test_texts:
            textbox.text = test_text
            result_text = textbox.text

            # Text should never be longer than what the buffer can hold
            encoded_len = len(test_text.encode('utf-8'))
            if encoded_len < buffer_size - 1:
                assert result_text == test_text
            else:
                # May be truncated but should not crash
                assert len(result_text) <= len(test_text)

    @given(buffer_size=integers(min_value=10, max_value=100),
           text_length=integers(min_value=0, max_value=200))
    def test_textbox_text_length_boundaries(self, buffer_size, text_length):
        """Textbox should handle text length boundaries safely."""
        textbox = pymui.Textbox(buffer_size)

        # Create text of specified length with safe ASCII characters
        test_text = "A" * text_length

        textbox.text = test_text
        result_text = textbox.text

        # Result should never exceed buffer capacity
        assert len(result_text.encode('utf-8')) < buffer_size


class TestUtilityFunctions:
    """Property-based tests for utility functions."""

    @given(x=integers(min_value=-1000, max_value=1000),
           y=integers(min_value=-1000, max_value=1000))
    def test_vec2_function(self, x, y):
        """Global vec2() function should work consistently."""
        vec = pymui.vec2(x, y)
        assert isinstance(vec, pymui.Vec2)
        assert vec.x == x
        assert vec.y == y

    @given(x=integers(min_value=-1000, max_value=1000),
           y=integers(min_value=-1000, max_value=1000),
           w=integers(min_value=0, max_value=1000),
           h=integers(min_value=0, max_value=1000))
    def test_rect_function(self, x, y, w, h):
        """Global rect() function should work consistently."""
        rect = pymui.rect(x, y, w, h)
        assert isinstance(rect, pymui.Rect)
        assert rect.x == x
        assert rect.y == y
        assert rect.w == w
        assert rect.h == h

    @given(r=integers(min_value=0, max_value=255),
           g=integers(min_value=0, max_value=255),
           b=integers(min_value=0, max_value=255),
           a=integers(min_value=0, max_value=255))
    def test_color_function(self, r, g, b, a):
        """Global color() function should work consistently."""
        color = pymui.color(r, g, b, a)
        assert isinstance(color, pymui.Color)
        assert color.r == r
        assert color.g == g
        assert color.b == b
        assert color.a == a

    @given(x=floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
           a=floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
           b=floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    def test_clamp_function(self, x, a, b):
        """Clamp function should work correctly with various inputs."""
        # Ensure a <= b
        if a > b:
            a, b = b, a

        result = pymui.clamp(x, a, b)

        # Result should be within bounds
        assert a <= result <= b

        # Test boundary conditions
        if x <= a:
            assert result == a
        elif x >= b:
            assert result == b
        else:
            assert result == x


class TestInputValidation:
    """Property-based tests for input validation."""

    def test_context_creation_stability(self):
        """Context creation should be stable and repeatable."""
        # Create multiple contexts
        contexts = []
        for _ in range(10):
            ctx = pymui.Context()
            contexts.append(ctx)

        # All should be valid instances
        for ctx in contexts:
            assert isinstance(ctx, pymui.Context)

    @given(invalid_buffer_size=integers(max_value=1))
    def test_textbox_invalid_buffer_size(self, invalid_buffer_size):
        """Textbox should reject invalid buffer sizes."""
        with pytest.raises(ValueError):
            pymui.Textbox(invalid_buffer_size)

    @given(large_buffer_size=integers(min_value=100000, max_value=1000000))
    def test_textbox_large_buffer_size(self, large_buffer_size):
        """Textbox should handle large buffer sizes appropriately."""
        try:
            textbox = pymui.Textbox(large_buffer_size)
            # If successful, should work normally
            textbox.text = "test"
            assert textbox.text == "test"
        except (ValueError, MemoryError):
            # Expected for very large sizes
            pass


class TestSliderBoundaries:
    """Property-based tests for slider boundary conditions."""

    def setup_method(self):
        """Set up context for each test."""
        self.ctx = pymui.Context()

    @given(value=floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
           low=floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
           high=floats(min_value=50.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    def test_slider_bounds_respected(self, value, low, high):
        """Slider should respect min/max bounds."""
        # Ensure proper ordering
        if low > high:
            low, high = high, low

        begin_in_window(self.ctx)
        try:
            result, new_value = self.ctx.slider(value, low, high)

            # New value should be within bounds (with floating point tolerance)
            assert low - 0.001 <= new_value <= high + 0.001

            # Result should be a valid flag combination
            assert isinstance(result, int)
            assert result >= 0

        except (ValueError, OverflowError):
            # Acceptable for edge cases
            pass
        finally:
            end_in_window(self.ctx)

    @given(equal_bounds=floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    def test_slider_equal_bounds(self, equal_bounds):
        """Slider should handle equal min/max bounds."""
        begin_in_window(self.ctx)
        try:
            result, new_value = self.ctx.slider(equal_bounds, equal_bounds, equal_bounds)

            # Value should be the bound value
            assert abs(new_value - equal_bounds) < 0.001

        except (ValueError, OverflowError):
            pass
        finally:
            end_in_window(self.ctx)


# Custom test for edge cases that were problematic
class TestEdgeCaseRegression:
    """Tests for specific edge cases that have caused issues."""

    def test_empty_string_handling(self):
        """Empty strings should be handled safely."""
        ctx = pymui.Context()
        begin_in_window(ctx)

        # These should not crash
        ctx.text("")
        ctx.label("")

        end_in_window(ctx)

    def test_minimal_window(self):
        """Minimal window should work."""
        ctx = pymui.Context()
        ctx.begin()

        if ctx.begin_window("Test", pymui.Rect(0, 0, 1, 1)):
            ctx.end_window()

        ctx.end()

    def test_zero_size_rect(self):
        """Zero-size rect should be handled."""
        rect = pymui.Rect(0, 0, 0, 0)
        assert rect.w == 0
        assert rect.h == 0

    def test_textbox_boundary_conditions(self):
        """Test textbox with exact boundary conditions."""
        tb = pymui.Textbox(4)  # Minimal usable size

        # Empty string
        tb.text = ""
        assert tb.text == ""

        # Single character
        tb.text = "A"
        assert tb.text == "A"

        # Text that exactly fits
        tb.text = "ABC"  # 3 chars + null terminator = 4 bytes
        assert tb.text == "ABC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])