"""
Portion size display utilities.

Maps numeric average_portion_size (1-3) to human-readable labels.
Enforces minimum review threshold before returning averages.
"""

MIN_REVIEWS_FOR_AVERAGE = 5


def bucket_portion_size(average: float | None, review_count: int) -> str:
    """
    Map average_portion_size (1-3) to display label.

    Returns 'insufficient_reviews' when review_count < MIN_REVIEWS_FOR_AVERAGE
    or when average is None.

    Args:
        average: Raw average portion size rating (1-3) from reviews
        review_count: Number of reviews for the vianda

    Returns:
        One of: 'light', 'standard', 'large', 'insufficient_reviews'
    """
    if review_count < MIN_REVIEWS_FOR_AVERAGE or average is None:
        return "insufficient_reviews"
    if average < 1.5:
        return "light"
    if average < 2.5:
        return "standard"
    return "large"
