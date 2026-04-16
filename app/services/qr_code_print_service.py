"""
HTML print page for supplier QR codes: base64-embedded PNG, market-aware address, print CSS.
"""

from __future__ import annotations

import base64
import html
import os

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from app.config.settings import settings
from app.schemas.consolidated_schemas import QRCodePrintContextSchema
from app.utils.address_formatting import format_street_display
from app.utils.log import log_error

_PRINT_CSS = """
@media print {
    body { margin: 0; padding: 0; }
    .no-print { display: none; }
    .qr-container {
        page-break-inside: avoid;
        width: 100%;
        text-align: center;
    }
    /* 2.75in: balance between label size and reliable camera scan at typical counter distance */
    img.qr-code {
        width: 2.75in;
        height: 2.75in;
        image-rendering: crisp-edges;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
}
@media screen {
    body {
        max-width: 4in;
        margin: 40px auto;
        font-family: sans-serif;
    }
    img.qr-code { width: 280px; height: 280px; }
    .print-btn {
        display: block;
        margin: 20px auto;
        padding: 10px 20px;
        cursor: pointer;
    }
}
"""


def autoprint_enabled(autoprint: str | None) -> bool:
    """True only when the query value is the word 'true' (case-insensitive).

    Callers must pass the raw query string from ``Query(None)``, not a FastAPI
    ``bool`` param (which would treat ``1`` and ``yes`` as true).
    """
    if autoprint is None:
        return False
    return autoprint.lower() == "true"


def load_qr_png_base64(image_storage_path: str) -> str:
    """Load QR PNG bytes from GCS or local disk; return base64 ASCII (no data URL prefix)."""
    path = (image_storage_path or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail="QR code has no stored image")

    try:
        if settings.GCS_INTERNAL_BUCKET and path.startswith("qrcodes/"):
            from app.utils.gcs import download_internal_bucket_blob_bytes

            raw = download_internal_bucket_blob_bytes(path)
        else:
            if not os.path.isfile(path):
                raise HTTPException(
                    status_code=500,
                    detail="QR code image file not found on server",
                )
            with open(path, "rb") as f:
                raw = f.read()
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Failed to load QR image for print: {e}")
        raise HTTPException(status_code=500, detail="Failed to load QR code image") from e

    return base64.b64encode(raw).decode("ascii")


def format_address_lines_for_print(ctx: QRCodePrintContextSchema) -> tuple[str, str]:
    """Market-aware street line + comma-separated locality line."""
    street = format_street_display(
        ctx.country_code or "",
        ctx.street_type,
        ctx.street_name,
        ctx.building_number,
    )
    locality_parts = [
        p.strip() for p in (ctx.city, ctx.province, ctx.postal_code, ctx.country_name) if p and str(p).strip()
    ]
    locality = ", ".join(locality_parts)
    return street, locality


def build_qr_code_print_html(
    ctx: QRCodePrintContextSchema,
    *,
    image_base64: str,
    autoprint: bool,
) -> str:
    """Full HTML document for print / preview."""
    street, locality = format_address_lines_for_print(ctx)
    name_esc = html.escape(ctx.restaurant_name)
    street_esc = html.escape(street) if street else ""
    locality_esc = html.escape(locality) if locality else ""
    data_uri = f"data:image/png;base64,{image_base64}"

    autoprint_script = ""
    if autoprint:
        autoprint_script = "<script>window.onload = function() { window.print(); }</script>"

    address_block = ""
    if street_esc or locality_esc:
        address_block = '<div class="address">'
        if street_esc:
            address_block += f"<p>{street_esc}</p>"
        if locality_esc:
            address_block += f"<p>{locality_esc}</p>"
        address_block += "</div>"

    footer = '<p class="footer">Scan to confirm pickup</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{name_esc}</title>
  <style>{_PRINT_CSS}</style>
  {autoprint_script}
</head>
<body>
  <button type="button" class="print-btn no-print" onclick="window.print()">Print</button>
  <h1>{name_esc}</h1>
  {address_block}
  <div class="qr-container">
    <img class="qr-code" src="{data_uri}" alt="QR code"/>
  </div>
  {footer}
</body>
</html>
"""


def qr_code_print_response(
    ctx: QRCodePrintContextSchema,
    *,
    autoprint: str | None,
) -> HTMLResponse:
    """Build HTMLResponse with embedded QR image."""
    b64 = load_qr_png_base64(ctx.image_storage_path)
    html_doc = build_qr_code_print_html(
        ctx,
        image_base64=b64,
        autoprint=autoprint_enabled(autoprint),
    )
    return HTMLResponse(content=html_doc, media_type="text/html")
