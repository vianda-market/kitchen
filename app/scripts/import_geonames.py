#!/usr/bin/env python3
"""
GeoNames + ISO 4217 import tooling for Vianda's `external.*` schema.

Downloads raw external reference data from GeoNames and ISO 4217 sources,
filters alternate names to the locales and entity IDs we actually use, and
writes TSVs ready to be loaded via Postgres `COPY` into the `external.*`
tables.

Usage
-----

    python3 app/scripts/import_geonames.py

Outputs are written to app/db/seed/external/ by default:

    geonames_country_info.tsv       — stripped countryInfo.txt (comments removed)
    geonames_admin1_codes.tsv       — admin1CodesASCII.txt transformed to our schema
                                      (splits "US.CA" into country_iso + admin1_code)
    geonames_cities5000.tsv         — cities5000.txt pass-through (column order matches schema)
    geonames_alternate_names.tsv    — alternateNamesV2.txt filtered to {en, es, pt} and to
                                      only the geonames_ids present in our country/admin1/city
                                      files; booleans converted to Postgres text-format t/f
    iso4217_currencies.tsv          — ISO 4217 currency list from datasets/currency-codes,
                                      withdrawn currencies dropped, deduped by AlphabeticCode

Design notes
------------

* **Stdlib only.** Runs on any Python 3.8+ without extra deps.
* **Deterministic.** Running twice against the same upstream snapshot produces
  byte-identical TSVs (alternate-names filter iterates in source order).
* **Streaming for alternate names.** alternateNamesV2.txt unzipped is ~1 GB; we
  read it line-by-line and emit filtered rows so memory stays bounded.
* **Source URLs are hard-coded.** GeoNames dumps live at stable URLs under
  https://download.geonames.org/export/dump/ and have for a decade. If one moves,
  update `SOURCES` below.
* **Attribution.** GeoNames data is CC-BY 4.0 — see docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md.

Re-running this script after a GeoNames update is the manual refresh path. A
future diff-based refresh that flags changes against core.market_info copies
lives in the backlog (see docs/plans/country_city_data_structure.md).
"""

import argparse
import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

GEONAMES_BASE = "https://download.geonames.org/export/dump"

SOURCES = {
    "country_info": {
        "url": f"{GEONAMES_BASE}/countryInfo.txt",
        "output": "geonames_country_info.tsv",
    },
    "admin1": {
        "url": f"{GEONAMES_BASE}/admin1CodesASCII.txt",
        "output": "geonames_admin1_codes.tsv",
    },
    "cities5000": {
        "url": f"{GEONAMES_BASE}/cities5000.zip",
        "member": "cities5000.txt",
        "output": "geonames_cities5000.tsv",
    },
    "alternate_names": {
        "url": f"{GEONAMES_BASE}/alternateNamesV2.zip",
        "member": "alternateNamesV2.txt",
        "output": "geonames_alternate_names.tsv",
    },
    "iso4217": {
        "url": "https://raw.githubusercontent.com/datasets/currency-codes/master/data/codes-all.csv",
        "output": "iso4217_currencies.tsv",
    },
}

# Locales we support in user-facing UIs. Keep in sync with settings.SUPPORTED_LOCALES.
LOCALES = {"en", "es", "pt"}

DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "app" / "db" / "seed" / "external"


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fetch(url: str) -> bytes:
    _log(f"  GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "vianda-import-geonames/1.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def extract_zip_member(zip_bytes: bytes, member: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open(member) as f:
            return f.read()


def write_tsv(path: Path, lines) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
    size_kb = path.stat().st_size / 1024
    _log(f"  wrote {path.name:<32} ({size_kb:>9.1f} KB)")


# ---------------------------------------------------------------------------
# Processors — one per source
# ---------------------------------------------------------------------------

def process_country_info(raw: bytes) -> list[str]:
    """
    GeoNames countryInfo.txt ships with ~50 lines of `#` comments at the top.
    Strip those and return the 19-column data rows in source order.

    Column order matches the source (our external.geonames_country DDL declares
    columns in that same order, so the committed TSV is byte-identical to the
    raw GeoNames data minus comments).
    """
    out: list[str] = []
    for line in raw.decode("utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        out.append(line)
    return out


def process_admin1(raw: bytes) -> list[str]:
    """
    admin1CodesASCII.txt is 4 columns:  code<tab>name<tab>nameAscii<tab>geonameId
    where `code` is e.g. "US.CA" — the country ISO joined to the admin1 code.

    We transform into 6 columns to match external.geonames_admin1:
        admin1_full_code, country_iso, admin1_code, name, ascii_name, geonames_id

    Splitting `code` at the dot now (instead of at COPY time via a generated
    column or trigger) is cheap and keeps the loader SQL trivial.
    """
    out: list[str] = []
    skipped = 0
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            skipped += 1
            continue
        full_code, name, ascii_name, gid = parts
        if "." not in full_code:
            skipped += 1
            continue
        country_iso, admin1_code = full_code.split(".", 1)
        out.append("\t".join([full_code, country_iso, admin1_code, name, ascii_name, gid]))
    if skipped:
        _log(f"  WARN: skipped {skipped} malformed admin1 rows")
    return out


def process_cities5000(raw: bytes) -> list[str]:
    """
    cities5000.txt has 19 columns in a fixed order. Our external.geonames_city
    DDL matches that order (with field renames — e.g. `country_code` → `country_iso`),
    so this is a straight pass-through.
    """
    out: list[str] = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        out.append(line)
    return out


def _gids_from_column(lines, col_index: int):
    for line in lines:
        parts = line.split("\t")
        if col_index < len(parts) and parts[col_index]:
            yield parts[col_index]


def build_id_set(country_lines, admin1_lines, city_lines) -> set[str]:
    """
    Collect every geonames_id referenced by our imported country/admin1/city
    rows. The alternate-names filter uses this set to drop any row that refers
    to an entity we don't care about — which is most of the ~13M-row file.
    """
    ids: set[str] = set()
    # country_info: geonames_id lives at column 16 (0-indexed).
    ids.update(_gids_from_column(country_lines, 16))
    # admin1 (transformed): geonames_id is the last column, index 5.
    ids.update(_gids_from_column(admin1_lines, 5))
    # cities5000: geonames_id is the first column, index 0.
    ids.update(_gids_from_column(city_lines, 0))
    return ids


def process_alternate_names(raw: bytes, id_set: set[str], locales: set[str]) -> list[str]:
    """
    alternateNamesV2.txt is ~13M rows globally. We keep a row only when:
      * its `geonameid` is in our in-scope id_set (country/admin1/city we imported), AND
      * its `isolanguage` is one of our supported UI locales.

    Source columns (10):
        alternateNameId, geonameid, isolanguage, alternate_name,
        isPreferredName, isShortName, isColloquial, isHistoric, from, to

    Output columns (8):
        alternate_name_id, geonames_id, iso_language, alternate_name,
        is_preferred, is_short, is_colloquial, is_historic

    `from`/`to` (historic date ranges) are dropped — we don't use them.

    Boolean columns in the source are either `1` (truthy) or empty (falsy).
    We translate to Postgres text-format `t`/`f` so COPY (FORMAT text) picks
    them up natively.
    """
    out: list[str] = []
    scanned = 0
    kept = 0

    def b(v: str) -> str:
        return "t" if v == "1" else "f"

    for raw_line in raw.decode("utf-8").splitlines():
        scanned += 1
        if scanned % 1_000_000 == 0:
            _log(f"    alternate_names: scanned {scanned:>10,}, kept {kept:>7,}")
        if not raw_line:
            continue
        parts = raw_line.split("\t")
        if len(parts) < 8:
            continue
        alt_id, gid, iso_lang, alt_name = parts[0], parts[1], parts[2], parts[3]
        is_pref, is_short, is_colloq, is_hist = parts[4], parts[5], parts[6], parts[7]
        if iso_lang not in locales:
            continue
        if gid not in id_set:
            continue
        if not alt_id or not alt_name:
            continue
        out.append("\t".join([
            alt_id, gid, iso_lang, alt_name,
            b(is_pref), b(is_short), b(is_colloq), b(is_hist),
        ]))
        kept += 1

    _log(f"    alternate_names: scanned {scanned:,}, kept {kept:,}")
    return out


def process_iso4217(raw: bytes) -> list[str]:
    """
    Parse datasets/currency-codes codes-all.csv into our schema:
        code<tab>name<tab>numeric_code<tab>minor_unit

    Source CSV header:
        Entity,Currency,AlphabeticCode,NumericCode,MinorUnit,WithdrawalDate

    Rules:
      * drop rows with a non-empty WithdrawalDate (withdrawn currencies)
      * require 3-letter AlphabeticCode and non-empty NumericCode
      * dedupe by AlphabeticCode (a code can repeat across multiple countries —
        ISO assigns currencies to entities, not the other way around)
      * minor_unit of "N.A." (currencies without subdivision, e.g. XAU gold)
        becomes "0" — the table expects an integer
      * sort by code for deterministic output
    """
    out: list[str] = []
    seen: set[str] = set()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    for row in reader:
        if (row.get("WithdrawalDate") or "").strip():
            continue
        code = (row.get("AlphabeticCode") or "").strip()
        numeric = (row.get("NumericCode") or "").strip()
        name = (row.get("Currency") or "").strip()
        minor = (row.get("MinorUnit") or "").strip()
        if len(code) != 3 or not numeric or not name:
            continue
        if code in seen:
            continue
        seen.add(code)
        if not minor.isdigit():
            minor = "0"
        out.append("\t".join([code, name, numeric, minor]))
    out.sort()
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help=f"output directory for committed TSVs (default: {DEFAULT_OUT_DIR})",
    )
    args = ap.parse_args()
    out_dir = Path(args.out)

    _log("== GeoNames countryInfo.txt ==")
    country_raw = fetch(SOURCES["country_info"]["url"])
    country_lines = process_country_info(country_raw)
    write_tsv(out_dir / SOURCES["country_info"]["output"], country_lines)

    _log("== GeoNames admin1CodesASCII.txt ==")
    admin1_raw = fetch(SOURCES["admin1"]["url"])
    admin1_lines = process_admin1(admin1_raw)
    write_tsv(out_dir / SOURCES["admin1"]["output"], admin1_lines)

    _log("== GeoNames cities5000.zip ==")
    cities_zip = fetch(SOURCES["cities5000"]["url"])
    cities_raw = extract_zip_member(cities_zip, SOURCES["cities5000"]["member"])
    city_lines = process_cities5000(cities_raw)
    write_tsv(out_dir / SOURCES["cities5000"]["output"], city_lines)

    _log("== Building in-scope geonames_id set ==")
    id_set = build_id_set(country_lines, admin1_lines, city_lines)
    _log(f"  {len(id_set):,} unique geonames_ids")

    _log("== GeoNames alternateNamesV2.zip (largest file) ==")
    alt_zip = fetch(SOURCES["alternate_names"]["url"])
    alt_raw = extract_zip_member(alt_zip, SOURCES["alternate_names"]["member"])
    alt_lines = process_alternate_names(alt_raw, id_set, LOCALES)
    write_tsv(out_dir / SOURCES["alternate_names"]["output"], alt_lines)

    _log("== ISO 4217 currency codes ==")
    iso_raw = fetch(SOURCES["iso4217"]["url"])
    iso_lines = process_iso4217(iso_raw)
    write_tsv(out_dir / SOURCES["iso4217"]["output"], iso_lines)

    _log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
