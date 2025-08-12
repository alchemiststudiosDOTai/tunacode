import os
import sys

import pytest

# Add base_code directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'base_code'))

from math_utils import calculate_mean, calculate_median, calculate_variance, safe_divide


class TestCalculateMean:
    """Test cases for calculate_mean function."""

    def test_normal_case(self):
        """Test mean calculation with normal numbers."""
        assert calculate_mean([1, 2, 3, 4, 5]) == 3.0
        assert calculate_mean([2.5, 3.5, 4.5]) == 3.5

    def test_single_element(self):
        """Test mean calculation with single element."""
        assert calculate_mean([42]) == 42.0
        assert calculate_mean([3.14]) == 3.14

    def test_negative_numbers(self):
        """Test mean calculation with negative numbers."""
        assert calculate_mean([-1, -2, -3]) == -2.0
        assert calculate_mean([-5, 0, 5]) == 0.0

    def test_mixed_integers_floats(self):
        """Test mean calculation with mixed types."""
        assert calculate_mean([1, 2.0, 3]) == 2.0

    def test_empty_list(self):
        """Test mean calculation with empty list - should handle gracefully."""
        with pytest.raises((ZeroDivisionError, ValueError)):
            calculate_mean([])

    def test_large_numbers(self):
        """Test mean calculation with large numbers."""
        large_nums = [1000000, 2000000, 3000000]
        assert calculate_mean(large_nums) == 2000000.0


class TestCalculateMedian:
    """Test cases for calculate_median function."""

    def test_odd_length(self):
        """Test median with odd number of elements."""
        assert calculate_median([1, 3, 5]) == 3.0
        assert calculate_median([7, 1, 9, 3, 5]) == 5.0

    def test_even_length(self):
        """Test median with even number of elements."""
        assert calculate_median([1, 2, 3, 4]) == 2.5
        assert calculate_median([10, 20]) == 15.0

    def test_single_element(self):
        """Test median with single element."""
        assert calculate_median([42]) == 42.0

    def test_empty_list(self):
        """Test median with empty list - should handle gracefully."""
        with pytest.raises(IndexError):
            calculate_median([])

    def test_unsorted_input(self):
        """Test median with unsorted input."""
        assert calculate_median([5, 1, 9, 3, 7]) == 5.0

    def test_duplicates(self):
        """Test median with duplicate values."""
        assert calculate_median([1, 2, 2, 3]) == 2.0
        assert calculate_median([5, 5, 5]) == 5.0


class TestCalculateVariance:
    """Test cases for calculate_variance function."""

    def test_normal_case(self):
        """Test variance calculation with normal numbers."""
        # Variance of [1, 2, 3] = ((1-2)² + (2-2)² + (3-2)²) / 3 = 2/3
        result = calculate_variance([1, 2, 3])
        assert abs(result - 2/3) < 0.0001

    def test_identical_values(self):
        """Test variance with identical values."""
        assert calculate_variance([5, 5, 5, 5]) == 0.0

    def test_single_element(self):
        """Test variance with single element."""
        # Single element should return 0 variance
        assert calculate_variance([42]) == 0.0

    def test_empty_list(self):
        """Test variance with empty list - should handle gracefully."""
        with pytest.raises((ZeroDivisionError, ValueError)):
            calculate_variance([])

    def test_negative_numbers(self):
        """Test variance with negative numbers."""
        result = calculate_variance([-2, 0, 2])
        assert abs(result - 8/3) < 0.0001


class TestSafeDivide:
    """Test cases for safe_divide function."""

    def test_normal_division(self):
        """Test normal division cases."""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(7, 2) == 3.5
        assert safe_divide(-10, 2) == -5.0

    def test_division_by_zero(self):
        """Test division by zero handling."""
        with pytest.raises(ValueError, match="Division by zero is not allowed"):
            safe_divide(10, 0)

        with pytest.raises(ValueError, match="Division by zero is not allowed"):
            safe_divide(0, 0)

    def test_zero_numerator(self):
        """Test zero numerator."""
        assert safe_divide(0, 5) == 0.0

    def test_float_division(self):
        """Test division with floats."""
        assert abs(safe_divide(1.0, 3.0) - 0.3333333333333333) < 0.0001
