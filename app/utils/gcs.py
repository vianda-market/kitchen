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


def upload_qr_code(
    qr_code_id: str | UUID, restaurant_id: str | UUID, file_data: bytes
) -> str:
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


def upload_product_image(
    product_id: str | UUID,
    institution_id: str | UUID,
    full_data: bytes,
    thumb_data: bytes,
    content_type: str,
) -> tuple[str, str]:
    """
    Upload product full + thumbnail to supplier bucket. Rollback full on thumbnail failure.
    Returns (blob_full, blob_thumb).
    """
    from app.config.settings import settings

    bucket = settings.GCS_SUPPLIER_BUCKET
    blob_full = f"products/{institution_id}/{product_id}/image"
    blob_thumb = f"products/{institution_id}/{product_id}/thumbnail"
    md5_full = hashlib.md5(full_data).digest()
    md5_thumb = hashlib.md5(thumb_data).digest()

    try:
        upload_file(bucket, blob_full, full_data, content_type, md5_hash=md5_full)
        upload_file(bucket, blob_thumb, thumb_data, content_type, md5_hash=md5_thumb)
        return blob_full, blob_thumb
    except Exception:
        try:
            delete_file(bucket, blob_full)
        except Exception:
            pass
        raise


def get_product_image_signed_url(
    product_id: str | UUID, institution_id: str | UUID
) -> str:
    """Generate signed URL for product full image."""
    from app.config.settings import settings

    blob_name = f"products/{institution_id}/{product_id}/image"
    return generate_signed_url(
        settings.GCS_SUPPLIER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def get_product_thumbnail_signed_url(
    product_id: str | UUID, institution_id: str | UUID
) -> str:
    """Generate signed URL for product thumbnail."""
    from app.config.settings import settings

    blob_name = f"products/{institution_id}/{product_id}/thumbnail"
    return generate_signed_url(
        settings.GCS_SUPPLIER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def get_placeholder_signed_url() -> str:
    """Generate signed URL for product placeholder from internal bucket."""
    from app.config.settings import settings

    blob_name = "placeholder/product_default.png"
    return generate_signed_url(
        settings.GCS_INTERNAL_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def delete_product_image(product_id: str | UUID, institution_id: str | UUID) -> None:
    """Delete product image and thumbnail from supplier bucket."""
    from app.config.settings import settings

    bucket = settings.GCS_SUPPLIER_BUCKET
    for suffix in ("/image", "/thumbnail"):
        blob_name = f"products/{institution_id}/{product_id}{suffix}"
        try:
            delete_file(bucket, blob_name)
        except Exception:
            pass


def delete_qr_code_blob(blob_name: str) -> None:
    """Delete QR code blob from internal bucket."""
    from app.config.settings import settings

    delete_file(settings.GCS_INTERNAL_BUCKET, blob_name)


# ── Stubs for future phases ──


def upload_profile_picture(
    user_id: str | UUID, file_data: bytes, content_type: str
) -> str:
    """Upload profile picture to customer bucket. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"profile/{user_id}/picture"
    return upload_file(
        settings.GCS_CUSTOMER_BUCKET, blob_name, file_data, content_type
    )


def get_profile_picture_signed_url(user_id: str | UUID) -> str:
    """Generate signed URL for profile picture. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"profile/{user_id}/picture"
    return generate_signed_url(
        settings.GCS_CUSTOMER_BUCKET,
        blob_name,
        settings.GCS_SIGNED_URL_EXPIRATION_SECONDS,
    )


def upload_employer_logo(
    employer_id: str | UUID, file_data: bytes, content_type: str
) -> str:
    """Upload employer logo to employer bucket. (Future phase.)"""
    from app.config.settings import settings

    blob_name = f"logos/{employer_id}/logo"
    return upload_file(
        settings.GCS_EMPLOYER_BUCKET, blob_name, file_data, content_type
    )


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


def resolve_product_image_urls(row: dict) -> dict:
    """
    Resolve product image URLs to signed URLs when using GCS.
    Mutates row in place; returns row.
    """
    from app.config.settings import settings

    if not settings.GCS_SUPPLIER_BUCKET:
        return row
    storage_path = row.get("image_storage_path") or row.get("product_image_storage_path")
    if not storage_path:
        return row
    if storage_path == "placeholder/product_default.png":
        url = get_placeholder_signed_url()
        if "image_url" in row:
            row["image_url"] = url
        if "image_thumbnail_url" in row:
            row["image_thumbnail_url"] = url
        if "product_image_url" in row:
            row["product_image_url"] = url
        return row
    if storage_path.startswith("products/"):
        parts = storage_path.split("/")
        if len(parts) >= 4:
            institution_id, product_id = parts[1], parts[2]
            full_url = get_product_image_signed_url(product_id, institution_id)
            thumb_url = get_product_thumbnail_signed_url(product_id, institution_id)
            if "image_url" in row:
                row["image_url"] = full_url
            if "image_thumbnail_url" in row:
                row["image_thumbnail_url"] = thumb_url
            if "product_image_url" in row:
                row["product_image_url"] = full_url
    return row


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
