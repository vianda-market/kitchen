"""GCS (Google Cloud Storage) utilities for file upload, signed URLs, and deletion.

Uses ADC on Cloud Run; local creds (GOOGLE_APPLICATION_CREDENTIALS) for local dev.
"""

import base64
import datetime
import hashlib
import os
from uuid import UUID

from google.cloud import storage


def get_gcs_client() -> storage.Client:
    """Return GCS client. Uses ADC on Cloud Run, local creds locally."""
    return storage.Client()


def upload_file(
    bucket_name: str,
    blob_name: str,
    file_data: bytes,
    content_type: str,
    md5_hash: bytes | None = None,
) -> str:
    """
    Upload file to GCS. When md5_hash (raw 16-byte digest) is provided,
    GCS verifies integrity on upload.
    """
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if md5_hash:
        blob.md5_hash = base64.b64encode(md5_hash).decode()
    blob.upload_from_string(file_data, content_type=content_type)
    return blob_name


def generate_signed_url(
    bucket_name: str,
    blob_name: str,
    expiration_seconds: int = 3600,
) -> str:
    """
    Generate a time-limited signed URL for reading a file.
    On Cloud Run, uses impersonated credentials (GCS_SIGNING_SA_EMAIL).
    Local dev: uses default creds.
    """
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    service_account_email = os.getenv("GCS_SIGNING_SA_EMAIL", "")

    if service_account_email:
        import google.auth
        from google.auth import impersonated_credentials

        credentials, _ = google.auth.default()
        signing_credentials = impersonated_credentials.Credentials(
            source_credentials=credentials,
            target_principal=service_account_email,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=expiration_seconds),
            method="GET",
            credentials=signing_credentials,
        )

    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(seconds=expiration_seconds),
        method="GET",
    )


def delete_file(bucket_name: str, blob_name: str) -> None:
    """Delete a file from GCS."""
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()


# ── Convenience helpers per actor type ──


def upload_qr_code(qr_code_id: str | UUID, restaurant_id: str | UUID, file_data: bytes) -> str:
    """Upload QR code to internal bucket. Returns blob path."""
    from app.config.settings import settings

    blob_name = f"qrcodes/{restaurant_id}/{qr_code_id}.png"
    md5_hash = hashlib.md5(file_data).digest()
    upload_file(
        settings.GCS_INTERNAL_BUCKET,
        blob_name,
        file_data,
        "image/png",
        md5_hash=md5_hash,
    )
    return blob_name


def get_qr_code_signed_url(qr_code_id: str | UUID, restaurant_id: str | UUID) -> str:
    """Generate signed URL for QR code (24h expiry)."""
    from app.config.settings import settings

    blob_name = f"qrcodes/{restaurant_id}/{qr_code_id}.png"
    return generate_signed_url(
        settings.GCS_INTERNAL_BUCKET,
        blob_name,
        settings.GCS_QR_SIGNED_URL_EXPIRATION_SECONDS,
    )


def download_internal_bucket_blob_bytes(blob_name: str) -> bytes:
    """Download object bytes from GCS internal bucket (e.g. QR PNG under qrcodes/)."""
    from app.config.settings import settings

    if not settings.GCS_INTERNAL_BUCKET:
        raise ValueError("GCS_INTERNAL_BUCKET is not configured")
    client = get_gcs_client()
    bucket = client.bucket(settings.GCS_INTERNAL_BUCKET)
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()


def generate_image_asset_write_signed_url(
    institution_id: str | UUID,
    product_id: str | UUID,
) -> tuple[str, "datetime.datetime"]:
    """
    Generate a signed PUT URL for uploading a product image original to GCS.
    Returns (signed_url, expiry_datetime).
    Blob path: products/{institution_id}/{product_id}/original
    """
    from app.config.settings import settings

    blob_name = f"products/{institution_id}/{product_id}/original"
    expiration_seconds = settings.GCS_SIGNED_URL_EXPIRATION_SECONDS

    client = get_gcs_client()
    bucket = client.bucket(settings.GCS_SUPPLIER_BUCKET)
    blob = bucket.blob(blob_name)

    service_account_email = os.getenv("GCS_SIGNING_SA_EMAIL", "")
    expiration = datetime.timedelta(seconds=expiration_seconds)
    expiry_dt = datetime.datetime.now(datetime.UTC) + expiration

    if service_account_email:
        import google.auth
        from google.auth import impersonated_credentials

        credentials, _ = google.auth.default()
        signing_credentials = impersonated_credentials.Credentials(
            source_credentials=credentials,
            target_principal=service_account_email,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="PUT",
            credentials=signing_credentials,
        )
    else:
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="PUT",
        )

    return signed_url, expiry_dt


def get_image_asset_signed_urls(
    institution_id: str | UUID,
    product_id: str | UUID,
) -> dict[str, str]:
    """
    Generate signed read URLs for hero, card, thumbnail derived sizes.
    Does NOT include 'original' (private, pipeline-only).
    Returns {} if any key does not exist in the bucket.
    """
    from app.config.settings import settings

    bucket_name = settings.GCS_SUPPLIER_BUCKET
    if not bucket_name:
        return {}

    keys = ("hero", "card", "thumbnail")
    result: dict[str, str] = {}
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)

    service_account_email = os.getenv("GCS_SIGNING_SA_EMAIL", "")
    expiration = datetime.timedelta(seconds=settings.GCS_SIGNED_URL_EXPIRATION_SECONDS)

    for key in keys:
        blob_name = f"products/{institution_id}/{product_id}/{key}"
        blob = bucket.blob(blob_name)
        if not blob.exists():
            return {}
        try:
            if service_account_email:
                import google.auth
                from google.auth import impersonated_credentials

                credentials, _ = google.auth.default()
                signing_credentials = impersonated_credentials.Credentials(
                    source_credentials=credentials,
                    target_principal=service_account_email,
                    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method="GET",
                    credentials=signing_credentials,
                )
            else:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method="GET",
                )
            result[key] = url
        except Exception:
            return {}

    return result


def delete_image_asset_blobs(institution_id: str | UUID, product_id: str | UUID) -> None:
    """Purge original, hero, card, thumbnail blobs for a product image asset. Best-effort."""
    from app.config.settings import settings

    bucket_name = settings.GCS_SUPPLIER_BUCKET
    if not bucket_name:
        return

    for key in ("original", "hero", "card", "thumbnail"):
        blob_name = f"products/{institution_id}/{product_id}/{key}"
        try:
            delete_file(bucket_name, blob_name)
        except Exception:
            pass


def get_placeholder_signed_url() -> str:
    """Generate signed URL for product placeholder from internal bucket."""
    from app.config.settings import settings

    blob_name = "placeholder/product_default.png"
    return generate_signed_url(
        settings.GCS_INTERNAL_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def delete_qr_code_blob(blob_name: str) -> None:
    """Delete QR code blob from internal bucket."""
    from app.config.settings import settings

    delete_file(settings.GCS_INTERNAL_BUCKET, blob_name)


# ── Stubs for future phases ──


def upload_profile_picture(user_id: str | UUID, file_data: bytes, content_type: str) -> str:
    """Upload profile picture to customer bucket. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"profile/{user_id}/picture"
    return upload_file(settings.GCS_CUSTOMER_BUCKET, blob_name, file_data, content_type)


def get_profile_picture_signed_url(user_id: str | UUID) -> str:
    """Generate signed URL for profile picture. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"profile/{user_id}/picture"
    return generate_signed_url(
        settings.GCS_CUSTOMER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def upload_employer_logo(employer_id: str | UUID, file_data: bytes, content_type: str) -> str:
    """Upload employer logo to employer bucket. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"logos/{employer_id}/logo"
    return upload_file(settings.GCS_EMPLOYER_BUCKET, blob_name, file_data, content_type)


def get_employer_logo_signed_url(employer_id: str | UUID) -> str:
    """Generate signed URL for employer logo. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"logos/{employer_id}/logo"
    return generate_signed_url(
        settings.GCS_EMPLOYER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


# ── URL resolution for API responses ──


def resolve_qr_code_image_url(row: dict) -> dict:
    """
    Resolve QR code image URL to signed URL when using GCS.
    Mutates row in place; returns row.
    """
    from app.config.settings import settings

    if not settings.GCS_INTERNAL_BUCKET:
        return row
    storage_path = row.get("image_storage_path")
    if not storage_path or not storage_path.startswith("qrcodes/"):
        return row
    url = generate_signed_url(
        settings.GCS_INTERNAL_BUCKET,
        storage_path,
        settings.GCS_QR_SIGNED_URL_EXPIRATION_SECONDS,
    )
    if "qr_code_image_url" in row:
        row["qr_code_image_url"] = url
    return row


def upload_supplier_invoice_document(
    supplier_invoice_id: str | UUID,
    institution_entity_id: str | UUID,
    country_code: str,
    file_data: bytes,
    content_type: str,
) -> str:
    """Upload supplier invoice document to supplier bucket. Returns blob path."""
    from app.config.settings import settings

    blob_name = f"invoices/{country_code}/{institution_entity_id}/{supplier_invoice_id}/document"
    md5_hash = hashlib.md5(file_data).digest()
    upload_file(
        settings.GCS_SUPPLIER_BUCKET,
        blob_name,
        file_data,
        content_type,
        md5_hash=md5_hash,
    )
    return blob_name


def get_supplier_invoice_document_signed_url(
    supplier_invoice_id: str | UUID,
    institution_entity_id: str | UUID,
    country_code: str,
) -> str:
    """Generate signed URL for supplier invoice document (1h expiry)."""
    from app.config.settings import settings

    blob_name = f"invoices/{country_code}/{institution_entity_id}/{supplier_invoice_id}/document"
    return generate_signed_url(
        settings.GCS_SUPPLIER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def upload_supplier_w9_document(
    w9_id: str | UUID,
    institution_entity_id: str | UUID,
    file_data: bytes,
    content_type: str,
) -> str:
    """Upload signed W-9 PDF to supplier bucket. Returns blob path."""
    from app.config.settings import settings

    blob_name = f"w9/{institution_entity_id}/{w9_id}/document"
    md5_hash = hashlib.md5(file_data).digest()
    upload_file(
        settings.GCS_SUPPLIER_BUCKET,
        blob_name,
        file_data,
        content_type,
        md5_hash=md5_hash,
    )
    return blob_name


def get_supplier_w9_document_signed_url(
    w9_id: str | UUID,
    institution_entity_id: str | UUID,
) -> str:
    """Generate signed URL for W-9 document (1h expiry)."""
    from app.config.settings import settings

    blob_name = f"w9/{institution_entity_id}/{w9_id}/document"
    return generate_signed_url(
        settings.GCS_SUPPLIER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )
