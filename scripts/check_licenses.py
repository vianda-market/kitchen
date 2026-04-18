#!/usr/bin/env python3
"""License compliance gate for production dependencies.

Reads the currently-installed environment, rejects any package whose license
is not in ALLOWED_SPDX_PATTERNS (plus explicit per-package allowlist entries
for packages with non-SPDX metadata we've individually verified).

Run locally:
    pip install pip-licenses
    pip install -r requirements.txt
    python scripts/check_licenses.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

# SPDX fragments (case-insensitive substring match) that we accept without
# further review. Anything else requires a PACKAGE_ALLOWLIST entry explaining
# why it's safe.
ALLOWED_SPDX_PATTERNS: tuple[str, ...] = (
    "mit",  # MIT, MIT License, MIT-CMU
    "apache",  # Apache-2.0, Apache Software License, Apache License 2.0
    "bsd",  # BSD, BSD-2-Clause, BSD-3-Clause, 3-Clause BSD License
    "isc",  # ISC License (ISCL)
    "mpl",  # Mozilla Public License 2.0 (MPL 2.0)
    "psf",  # Python Software Foundation License, PSF-2.0
    "python software foundation",
    "unlicense",  # The Unlicense is public-domain, fine for our use
)

# License substrings that MUST cause failure even if they happen to contain
# an allowed fragment (e.g. "LGPL" contains "GPL"; we reject both).
FORBIDDEN_SPDX_PATTERNS: tuple[str, ...] = (
    "gpl",  # GPL, LGPL, AGPL — all copyleft, incompatible with our distribution model
    "unknown",
)

# Packages whose pip metadata is ambiguous but whose actual license is known
# from the upstream project. Each entry must cite the reason.
PACKAGE_ALLOWLIST: dict[str, str] = {
    # Metadata says "LICENSE.txt" — upstream file is plain Apache-2.0.
    # Source: https://github.com/googleapis/python-crc32c/blob/main/LICENSE
    "google-crc32c": "Apache-2.0 (upstream LICENSE file; metadata is UNKNOWN)",
    # Metadata is a raw dump of the Apache 2.0 license text rather than SPDX.
    # Source: https://github.com/googleads/google-ads-python
    "google-ads": "Apache-2.0 (metadata is raw license text)",
    # Metadata says "LICENSE.txt" — upstream is the Facebook Platform License,
    # a custom license that allows use of the SDK for interacting with the
    # Facebook advertising platform. Required by app.gateways.ads.meta.*.
    # Source: https://github.com/facebook/facebook-python-business-sdk
    "facebook_business": "Facebook Platform License (SDK for Meta ads integration)",
}

# Packages we accept despite LGPL metadata. Python packages are dynamically
# linked, which LGPL permits; still, we document each one so this isn't a
# silent loophole for all LGPL code.
LGPL_PACKAGE_ALLOWLIST: dict[str, str] = {
    # LGPL psycopg2 is the canonical PostgreSQL adapter; dynamic linking is
    # the use pattern LGPL explicitly permits.
    "psycopg2-binary": "LGPL; dynamic linking per LGPL §6",
    # Same rationale — pycountry ships LGPLv2 ISO data tables.
    "pycountry": "LGPLv2; dynamic linking per LGPL §6",
}


def _lic_matches(license_str: str, patterns: tuple[str, ...]) -> bool:
    lic = license_str.lower()
    return any(p in lic for p in patterns)


def main() -> int:
    raw = subprocess.check_output(
        ["pip-licenses", "--format=json", "--with-urls"],
        text=True,
    )
    packages = json.loads(raw)

    violations: list[str] = []
    for pkg in packages:
        name = pkg["Name"]
        version = pkg["Version"]
        license_str = pkg.get("License", "") or ""
        # Collapse whitespace/newlines from packages that dumped license text
        # into the metadata field (e.g. google-ads).
        license_str = re.sub(r"\s+", " ", license_str).strip()

        if name in PACKAGE_ALLOWLIST:
            continue
        if name in LGPL_PACKAGE_ALLOWLIST:
            continue

        if _lic_matches(license_str, FORBIDDEN_SPDX_PATTERNS):
            violations.append(f"{name}=={version}: {license_str!r} (forbidden)")
            continue
        if _lic_matches(license_str, ALLOWED_SPDX_PATTERNS):
            continue

        violations.append(
            f"{name}=={version}: {license_str!r} (not on allowlist; "
            f"add to PACKAGE_ALLOWLIST with justification or replace the package)"
        )

    if violations:
        print("License check FAILED:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            f"\nAllowlist is defined in {sys.argv[0]}. Any new non-standard license requires review.",
            file=sys.stderr,
        )
        return 1

    print(f"License check OK ({len(packages)} packages).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
