from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import BadZipFile, ZipFile

SCHEMA_VERSION = "1.0.0"
PARSER_VERSION = "1.0.0"
SOURCE_YEAR = 2025
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = REPOSITORY_ROOT / "data" / "source" / "census" / "2025_Gaz_zcta_national.zip"
SOURCE_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2025_Gazetteer/2025_Gaz_zcta_national.zip"
)
RETRIEVED_AT = datetime(2026, 8, 8, tzinfo=UTC)
EXPECTED_FIELDS = {
    "GEOID",
    "GEOIDFQ",
    "ALAND",
    "AWATER",
    "ALAND_SQMI",
    "AWATER_SQMI",
    "INTPTLAT",
    "INTPTLONG",
}


class LocationDataError(ValueError):
    """Raised when a location source snapshot violates its data contract."""


@dataclass(frozen=True)
class PostalAreaCoordinate:
    postal_code: str
    latitude: float
    longitude: float
    coordinate_method: str
    source_locator: str


@dataclass(frozen=True)
class LocationDataset:
    id: str
    schema_version: str
    parser_version: str
    source_id: str
    source_title: str
    source_path: str
    source_url: str
    source_publisher: str
    source_sha256: str
    source_media_type: str
    source_retrieved_at: datetime
    source_license: str
    locations: tuple[PostalAreaCoordinate, ...]


def _relative_source_path(source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return source_path.name


def build_location_dataset(source_path: Path = DEFAULT_SOURCE) -> LocationDataset:
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    dataset_id = f"census-zcta-{SOURCE_YEAR}-{source_sha256[:16]}"

    try:
        with ZipFile(io.BytesIO(source_bytes)) as archive:
            members = [name for name in archive.namelist() if not name.endswith("/")]
            if len(members) != 1 or not members[0].endswith(".txt"):
                raise LocationDataError("The Census snapshot must contain exactly one text file.")
            with archive.open(members[0]) as raw_file:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw_file, encoding="utf-8-sig"), delimiter="|"
                )
                if set(reader.fieldnames or ()) != EXPECTED_FIELDS:
                    raise LocationDataError("The Census snapshot has an unexpected column layout.")

                locations: list[PostalAreaCoordinate] = []
                seen_postal_codes: set[str] = set()
                for line_number, row in enumerate(reader, start=2):
                    postal_code = row.get("GEOID") or ""
                    if not re.fullmatch(r"\d{5}", postal_code):
                        raise LocationDataError(
                            f"Invalid ZCTA {postal_code!r} on source line {line_number}."
                        )
                    if postal_code in seen_postal_codes:
                        raise LocationDataError(f"Duplicate ZCTA {postal_code!r}.")

                    try:
                        latitude = float(row.get("INTPTLAT") or "")
                        longitude = float(row.get("INTPTLONG") or "")
                    except (TypeError, ValueError) as error:
                        raise LocationDataError(
                            f"Invalid coordinates for ZCTA {postal_code!r}."
                        ) from error
                    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                        raise LocationDataError(
                            f"Coordinates for ZCTA {postal_code!r} are outside valid bounds."
                        )

                    seen_postal_codes.add(postal_code)
                    locations.append(
                        PostalAreaCoordinate(
                            postal_code=postal_code,
                            latitude=latitude,
                            longitude=longitude,
                            coordinate_method="census_zcta_representative_point",
                            source_locator=f"{members[0]}:GEOID={postal_code}",
                        )
                    )
    except BadZipFile as error:
        raise LocationDataError(
            "The Census location snapshot is not a valid ZIP archive."
        ) from error

    if not locations:
        raise LocationDataError("The Census location snapshot contains no ZCTA records.")
    if [location.postal_code for location in locations] != sorted(seen_postal_codes):
        raise LocationDataError("ZCTA records must be ordered by postal code.")

    return LocationDataset(
        id=dataset_id,
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        source_id=f"sha256:{source_sha256}",
        source_title="2025 Census Gazetteer: ZIP Code Tabulation Areas",
        source_path=_relative_source_path(source_path),
        source_url=SOURCE_URL,
        source_publisher="United States Census Bureau",
        source_sha256=source_sha256,
        source_media_type="application/zip",
        source_retrieved_at=RETRIEVED_AT,
        source_license="U.S. Government work; attribution requested",
        locations=tuple(locations),
    )
