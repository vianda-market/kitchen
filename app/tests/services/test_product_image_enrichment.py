"""
Unit tests for _populate_product_image_signed_urls in entity_service.

Tests the response-builder logic that decides when image_signed_urls is populated,
without touching GCS (get_image_asset_signed_urls is mocked).
"""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from app.config import Status
from app.schemas.consolidated_schemas import ProductEnrichedResponseSchema
from app.services.entity_service import _populate_product_image_signed_urls


def _make_product(
    *,
    institution_id=None,
    product_id=None,
    image_asset_id=None,
    image_pipeline_status=None,
    image_moderation_status=None,
) -> ProductEnrichedResponseSchema:
    """Build a minimal ProductEnrichedResponseSchema for testing."""
    # Pydantic mypy plugin treats Field(None, exclude=True) fields as required in
    # strict type-checking — supply explicit None for all such fields.
    return ProductEnrichedResponseSchema(
        product_id=product_id or uuid4(),
        institution_id=institution_id or uuid4(),
        institution_name="Test Institution",
        name="Test Product",
        name_i18n=None,
        ingredients=None,
        ingredients_i18n=None,
        description=None,
        description_i18n=None,
        dietary=None,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_date=datetime.now(UTC),
        image_asset_id=image_asset_id,
        image_pipeline_status=image_pipeline_status,
        image_moderation_status=image_moderation_status,
        image_signed_urls=None,
    )


MOCK_URLS = {"hero": "https://gcs/hero", "card": "https://gcs/card", "thumbnail": "https://gcs/thumb"}


class TestPopulateProductImageSignedUrls:
    """Tests for the image_signed_urls population logic."""

    def test_no_image_asset_leaves_signed_urls_null(self):
        """Products with no image_asset row get image_signed_urls=None."""
        product = _make_product(image_pipeline_status=None)
        with patch("app.utils.gcs.get_image_asset_signed_urls") as mock_gcs:
            _populate_product_image_signed_urls([product])
        mock_gcs.assert_not_called()
        assert product.image_signed_urls is None

    def test_pending_status_leaves_signed_urls_null(self):
        """Products with pipeline_status='pending' get image_signed_urls=None."""
        product = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="pending",
            image_moderation_status="pending",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls") as mock_gcs:
            _populate_product_image_signed_urls([product])
        mock_gcs.assert_not_called()
        assert product.image_signed_urls is None

    def test_processing_status_leaves_signed_urls_null(self):
        """Products with pipeline_status='processing' get image_signed_urls=None."""
        product = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="processing",
            image_moderation_status="pending",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls") as mock_gcs:
            _populate_product_image_signed_urls([product])
        mock_gcs.assert_not_called()
        assert product.image_signed_urls is None

    def test_rejected_status_leaves_signed_urls_null(self):
        """Products with pipeline_status='rejected' get image_signed_urls=None."""
        product = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="rejected",
            image_moderation_status="rejected",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls") as mock_gcs:
            _populate_product_image_signed_urls([product])
        mock_gcs.assert_not_called()
        assert product.image_signed_urls is None

    def test_failed_status_leaves_signed_urls_null(self):
        """Products with pipeline_status='failed' get image_signed_urls=None."""
        product = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="failed",
            image_moderation_status="pending",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls") as mock_gcs:
            _populate_product_image_signed_urls([product])
        mock_gcs.assert_not_called()
        assert product.image_signed_urls is None

    def test_ready_status_populates_signed_urls(self):
        """Products with pipeline_status='ready' get image_signed_urls populated from GCS."""
        inst_id = uuid4()
        prod_id = uuid4()
        product = _make_product(
            institution_id=inst_id,
            product_id=prod_id,
            image_asset_id=uuid4(),
            image_pipeline_status="ready",
            image_moderation_status="passed",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls", return_value=MOCK_URLS) as mock_gcs:
            _populate_product_image_signed_urls([product])
        mock_gcs.assert_called_once_with(inst_id, prod_id)
        assert product.image_signed_urls == MOCK_URLS

    def test_ready_status_gcs_returns_empty_yields_null(self):
        """When GCS helper returns {} (blobs missing), image_signed_urls stays None."""
        product = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="ready",
            image_moderation_status="passed",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls", return_value={}):
            _populate_product_image_signed_urls([product])
        assert product.image_signed_urls is None

    def test_per_request_cache_avoids_duplicate_gcs_calls(self):
        """Duplicate product_id in the list only calls GCS once (cache hit)."""
        inst_id = uuid4()
        prod_id = uuid4()
        asset_id = uuid4()
        p1 = _make_product(
            institution_id=inst_id,
            product_id=prod_id,
            image_asset_id=asset_id,
            image_pipeline_status="ready",
            image_moderation_status="passed",
        )
        p2 = _make_product(
            institution_id=inst_id,
            product_id=prod_id,
            image_asset_id=asset_id,
            image_pipeline_status="ready",
            image_moderation_status="passed",
        )
        with patch("app.utils.gcs.get_image_asset_signed_urls", return_value=MOCK_URLS) as mock_gcs:
            _populate_product_image_signed_urls([p1, p2])
        # GCS called only once despite two products with the same key
        assert mock_gcs.call_count == 1
        assert p1.image_signed_urls == MOCK_URLS
        assert p2.image_signed_urls == MOCK_URLS

    def test_mixed_list_handles_each_product_correctly(self):
        """List with a mix of statuses: only 'ready' products get signed URLs."""
        ready_prod = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="ready",
            image_moderation_status="passed",
        )
        pending_prod = _make_product(
            image_asset_id=uuid4(),
            image_pipeline_status="pending",
            image_moderation_status="pending",
        )
        no_image_prod = _make_product(image_pipeline_status=None)

        with patch("app.utils.gcs.get_image_asset_signed_urls", return_value=MOCK_URLS):
            _populate_product_image_signed_urls([ready_prod, pending_prod, no_image_prod])

        assert ready_prod.image_signed_urls == MOCK_URLS
        assert pending_prod.image_signed_urls is None
        assert no_image_prod.image_signed_urls is None

    def test_empty_list_is_a_no_op(self):
        """Empty list does not raise and does not call GCS."""
        with patch("app.utils.gcs.get_image_asset_signed_urls") as mock_gcs:
            _populate_product_image_signed_urls([])
        mock_gcs.assert_not_called()
