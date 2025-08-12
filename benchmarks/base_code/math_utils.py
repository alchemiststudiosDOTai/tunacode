from typing import List, Union


def calculate_mean(numbers: List[Union[int, float]]) -> float:
    """
    Calculate the arithmetic mean of a list of numbers.

    Args:
        numbers: List of numbers

    Returns:
        Arithmetic mean

    Note: This implementation has bugs with edge cases!
    """
    # BUG: Doesn't handle empty list properly
    if not numbers:
        # This should raise a meaningful error, not divide by zero
        return sum(numbers) / len(numbers)  # Will cause ZeroDivisionError

    # BUG: Integer division could cause precision loss
    return sum(numbers) / len(numbers)


def calculate_median(numbers: List[Union[int, float]]) -> float:
    """
    Calculate the median of a list of numbers.

    Args:
        numbers: List of numbers

    Returns:
        Median value
    """
    # BUG: Doesn't handle empty list
    if not numbers:
        # Should raise meaningful error
        return numbers[0]  # Will cause IndexError

    sorted_nums = sorted(numbers)
    n = len(sorted_nums)

    if n % 2 == 0:
        # Even number of elements
        mid1 = sorted_nums[n // 2 - 1]
        mid2 = sorted_nums[n // 2]
        return (mid1 + mid2) / 2
    else:
        # Odd number of elements
        return float(sorted_nums[n // 2])


def calculate_variance(numbers: List[Union[int, float]]) -> float:
    """
    Calculate the variance of a list of numbers.

    Args:
        numbers: List of numbers

    Returns:
        Variance
    """
    # BUG: Will fail on empty list due to mean calculation bug
    if len(numbers) < 2:
        # Should handle single element case
        return 0.0

    mean = calculate_mean(numbers)  # This will fail on empty list
    squared_diffs = [(x - mean) ** 2 for x in numbers]

    # Population variance (N denominator)
    return sum(squared_diffs) / len(numbers)


def safe_divide(numerator: Union[int, float], denominator: Union[int, float]) -> float:
    """
    Safely divide two numbers.

    Args:
        numerator: Number to divide
        denominator: Number to divide by

    Returns:
        Result of division

    Raises:
        ValueError: If denominator is zero
    """
    if denominator == 0:
        raise ValueError("Division by zero is not allowed")

    return numerator / denominator
