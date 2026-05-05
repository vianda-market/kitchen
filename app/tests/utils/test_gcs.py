"""
Unit tests for image-asset GCS helpers added in image-pipeline-uploads-atomic.

Tests covered:
- generate_image_asset_write_signed_url — returns (url, expiry) tuple with correct blob path
- get_image_asset_signed_urls — returns dict with hero/card/thumbnail keys; returns {} when
  any blob is missing
- delete_image_asset_blobs — calls delete_file for all four keys; swallows per-blob errors
"""

from datetime import datetime
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

from app.config.settings import settings as _settings

INSTITUTION_ID = str(uuid4())
PRODUCT_ID = str(uuid4())


class TestGenerateImageAssetWriteSignedUrl:
    """generate_image_asset_write_signed_url returns a PUT signed URL + expiry datetime."""

    @patch("app.utils.gcs.os.getenv", return_value="")
    @patch("app.utils.gcs.get_gcs_client")
    def test_returns_tuple_with_signed_url_and_expiry(self, mock_get_client, mock_getenv):
        """Returns (str, datetime) tuple; expiry is UTC-aware."""
        signed_url = "https://storage.googleapis.com/signed?X-Goog-Signature=abc"
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = signed_url
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        with (
            patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"),
            patch.object(_settings, "GCS_SIGNED_URL_EXPIRATION_SECONDS", 900),
        ):
            from app.utils.gcs import generate_image_asset_write_signed_url

            url, expiry = generate_image_asset_write_signed_url(INSTITUTION_ID, PRODUCT_ID)

        assert url == signed_url
        assert isinstance(expiry, datetime)
        assert expiry.tzinfo is not None  # must be timezone-aware

    @patch("app.utils.gcs.os.getenv", return_value="")
    @patch("app.utils.gcs.get_gcs_client")
    def test_blob_path_uses_correct_prefix(self, mock_get_client, mock_getenv):
        """Blob path is products/{institution_id}/{product_id}/original."""
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed-url"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        with (
            patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"),
            patch.object(_settings, "GCS_SIGNED_URL_EXPIRATION_SECONDS", 900),
        ):
            from app.utils.gcs import generate_image_asset_write_signed_url

            generate_image_asset_write_signed_url(INSTITUTION_ID, PRODUCT_ID)

        expected_blob = f"products/{INSTITUTION_ID}/{PRODUCT_ID}/original"
        mock_bucket.blob.assert_called_once_with(expected_blob)

    @patch("app.utils.gcs.os.getenv", return_value="")
    @patch("app.utils.gcs.get_gcs_client")
    def test_uses_put_method(self, mock_get_client, mock_getenv):
        """Signed URL is generated with method='PUT' for a write-only upload URL."""
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed-url"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        with (
            patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"),
            patch.object(_settings, "GCS_SIGNED_URL_EXPIRATION_SECONDS", 900),
        ):
            from app.utils.gcs import generate_image_asset_write_signed_url

            generate_image_asset_write_signed_url(INSTITUTION_ID, PRODUCT_ID)

        call_kwargs = mock_blob.generate_signed_url.call_args
        assert call_kwargs.kwargs.get("method") == "PUT"


class TestGetImageAssetSignedUrls:
    """get_image_asset_signed_urls returns {hero, card, thumbnail} or {} when a key is missing."""

    @patch("app.utils.gcs.os.getenv", return_value="")
    @patch("app.utils.gcs.get_gcs_client")
    def test_returns_all_three_keys_when_all_blobs_exist(self, mock_get_client, mock_getenv):
        """When hero, card, thumbnail all exist, returns a dict with all three keys."""

        def _make_blob(name):
            blob = MagicMock()
            blob.exists.return_value = True
            blob.generate_signed_url.return_value = f"https://signed/{name}"
            return blob

        mock_bucket = MagicMock()
        mock_bucket.blob.side_effect = lambda name: _make_blob(name.split("/")[-1])
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        with (
            patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"),
            patch.object(_settings, "GCS_SIGNED_URL_EXPIRATION_SECONDS", 900),
        ):
            from app.utils.gcs import get_image_asset_signed_urls

            result = get_image_asset_signed_urls(INSTITUTION_ID, PRODUCT_ID)

        assert set(result.keys()) == {"hero", "card", "thumbnail"}

    @patch("app.utils.gcs.os.getenv", return_value="")
    @patch("app.utils.gcs.get_gcs_client")
    def test_returns_empty_dict_when_hero_missing(self, mock_get_client, mock_getenv):
        """When hero blob does not exist, returns {} (fail-fast on first missing key)."""
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False  # hero missing
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        with (
            patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"),
            patch.object(_settings, "GCS_SIGNED_URL_EXPIRATION_SECONDS", 900),
        ):
            from app.utils.gcs import get_image_asset_signed_urls

            result = get_image_asset_signed_urls(INSTITUTION_ID, PRODUCT_ID)

        assert result == {}

    @patch("app.utils.gcs.get_gcs_client")
    def test_returns_empty_dict_when_bucket_not_configured(self, mock_get_client):
        """When GCS_SUPPLIER_BUCKET is empty, returns {} without touching GCS."""
        with patch.object(_settings, "GCS_SUPPLIER_BUCKET", ""):
            from app.utils.gcs import get_image_asset_signed_urls

            result = get_image_asset_signed_urls(INSTITUTION_ID, PRODUCT_ID)

        mock_get_client.assert_not_called()
        assert result == {}

    @patch("app.utils.gcs.os.getenv", return_value="")
    @patch("app.utils.gcs.get_gcs_client")
    def test_returns_empty_dict_when_sign_raises(self, mock_get_client, mock_getenv):
        """When generate_signed_url raises, returns {} (safe fallback)."""
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.generate_signed_url.side_effect = Exception("signing error")
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_get_client.return_value = mock_client

        with (
            patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"),
            patch.object(_settings, "GCS_SIGNED_URL_EXPIRATION_SECONDS", 900),
        ):
            from app.utils.gcs import get_image_asset_signed_urls

            result = get_image_asset_signed_urls(INSTITUTION_ID, PRODUCT_ID)

        assert result == {}


class TestDeleteImageAssetBlobs:
    """delete_image_asset_blobs purges all four keys; individual errors are swallowed."""

    @patch("app.utils.gcs.delete_file")
    def test_deletes_all_four_keys(self, mock_delete_file):
        """Calls delete_file for original, hero, card, thumbnail."""
        with patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"):
            from app.utils.gcs import delete_image_asset_blobs

            delete_image_asset_blobs(INSTITUTION_ID, PRODUCT_ID)

        expected_calls = [
            call("vianda-supplier", f"products/{INSTITUTION_ID}/{PRODUCT_ID}/original"),
            call("vianda-supplier", f"products/{INSTITUTION_ID}/{PRODUCT_ID}/hero"),
            call("vianda-supplier", f"products/{INSTITUTION_ID}/{PRODUCT_ID}/card"),
            call("vianda-supplier", f"products/{INSTITUTION_ID}/{PRODUCT_ID}/thumbnail"),
        ]
        mock_delete_file.assert_has_calls(expected_calls, any_order=False)
        assert mock_delete_file.call_count == 4

    @patch("app.utils.gcs.delete_file")
    def test_continues_after_individual_blob_error(self, mock_delete_file):
        """Per-blob GCS errors do not abort the purge; remaining keys still deleted."""
        mock_delete_file.side_effect = [Exception("not found"), None, None, None]

        with patch.object(_settings, "GCS_SUPPLIER_BUCKET", "vianda-supplier"):
            from app.utils.gcs import delete_image_asset_blobs

            delete_image_asset_blobs(INSTITUTION_ID, PRODUCT_ID)  # must not raise

        assert mock_delete_file.call_count == 4

    @patch("app.utils.gcs.delete_file")
    def test_no_op_when_bucket_not_configured(self, mock_delete_file):
        """When GCS_SUPPLIER_BUCKET is empty, does nothing (bucket not configured)."""
        with patch.object(_settings, "GCS_SUPPLIER_BUCKET", ""):
            from app.utils.gcs import delete_image_asset_blobs

            delete_image_asset_blobs(INSTITUTION_ID, PRODUCT_ID)

        mock_delete_file.assert_not_called()
