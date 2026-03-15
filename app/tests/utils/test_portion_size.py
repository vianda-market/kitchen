"""
Unit tests for portion_size utility (bucket_portion_size, minimum review threshold).
"""

import pytest

from app.utils.portion_size import bucket_portion_size, MIN_REVIEWS_FOR_AVERAGE


class TestBucketPortionSize:
    """Tests for bucket_portion_size bucketing and minimum threshold."""

    def test_min_reviews_constant(self):
        assert MIN_REVIEWS_FOR_AVERAGE == 5

    def test_returns_insufficient_reviews_when_review_count_below_threshold(self):
        """When review_count < 5, always returns insufficient_reviews regardless of average."""
        assert bucket_portion_size(1.0, 0) == "insufficient_reviews"
        assert bucket_portion_size(1.0, 1) == "insufficient_reviews"
        assert bucket_portion_size(2.0, 2) == "insufficient_reviews"
        assert bucket_portion_size(2.5, 3) == "insufficient_reviews"
        assert bucket_portion_size(3.0, 4) == "insufficient_reviews"

    def test_returns_insufficient_reviews_when_average_none_even_with_reviews(self):
        """When average is None, returns insufficient_reviews even if review_count >= 5."""
        assert bucket_portion_size(None, 5) == "insufficient_reviews"
        assert bucket_portion_size(None, 10) == "insufficient_reviews"

    def test_light_boundaries(self):
        """Average < 1.5 with enough reviews returns light."""
        assert bucket_portion_size(1.0, 5) == "light"
        assert bucket_portion_size(1.49, 5) == "light"
        assert bucket_portion_size(1.49, 10) == "light"

    def test_standard_boundaries(self):
        """Average 1.5 to 2.49 with enough reviews returns standard."""
        assert bucket_portion_size(1.5, 5) == "standard"
        assert bucket_portion_size(2.0, 5) == "standard"
        assert bucket_portion_size(2.49, 5) == "standard"
        assert bucket_portion_size(2.1, 15) == "standard"

    def test_large_boundaries(self):
        """Average >= 2.5 with enough reviews returns large."""
        assert bucket_portion_size(2.5, 5) == "large"
        assert bucket_portion_size(2.5, 10) == "large"
        assert bucket_portion_size(3.0, 5) == "large"
        assert bucket_portion_size(2.7, 20) == "large"
