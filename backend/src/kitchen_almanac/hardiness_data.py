from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

SCHEMA_VERSION = "1.0.0"
PARSER_VERSION = "1.0.0"
EXTRACTOR_VERSION = "1.0.0"
DATASET_KIND = "usda_hardiness_2023"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = (
    REPOSITORY_ROOT / "data" / "source" / "usda" / "phzm-2023" / "2023ConusNAD83_Clip.tif"
)
SUPPORTING_FILE_SHA256 = {
    "2023ConusNAD83_Clip.tif.xml": (
        "3bf13e02cb21b54bd5100816a1225178001c696b3f135ae0c7bdd93148bb95ea"
    ),
    "README.txt": "382bf5aa3b4b09e19dfb02213dfde7fac34ecced52648ca61f7a45da34ff75a3",
}
SOURCE_URL = "https://ndownloader.figshare.com/files/44868940"
SOURCE_PAGE_URL = (
    "https://catalog.data.gov/dataset/"
    "2023-usda-plant-hardiness-zone-map-mean-annual-extreme-low-temperature-rasters"
)
RETRIEVED_AT = datetime(2026, 8, 8, tzinfo=UTC)


class HardinessDataError(ValueError):
    """Raised when the USDA hardiness snapshot cannot be validated or sampled."""


@dataclass(frozen=True)
class HardinessDataset:
    id: str
    dataset_kind: str
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


@dataclass(frozen=True)
class HardinessSample:
    zone: str
    mean_annual_extreme_minimum_f: float
    raster_value: int
    row: int
    column: int
    source_locator: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_source_path(source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return source_path.name


def hardiness_zone_from_centi_fahrenheit(value: int) -> str:
    half_zone = max(0, min(25, (value + 6000) // 500))
    zone_number = half_zone // 2 + 1
    subzone = "a" if half_zone % 2 == 0 else "b"
    return f"{zone_number}{subzone}"


def build_hardiness_dataset(source_path: Path = DEFAULT_SOURCE) -> HardinessDataset:
    source_sha256 = _sha256(source_path)
    for filename, expected_sha256 in SUPPORTING_FILE_SHA256.items():
        supporting_path = source_path.parent / filename
        if not supporting_path.is_file() or _sha256(supporting_path) != expected_sha256:
            raise HardinessDataError(
                f"USDA supporting snapshot {filename!r} is missing or changed."
            )

    try:
        with rasterio.open(source_path) as raster:
            if raster.driver != "GTiff" or raster.count != 1 or raster.dtypes != ("int16",):
                raise HardinessDataError("The USDA snapshot has an unexpected raster layout.")
            if raster.crs is None or raster.crs.to_epsg() != 4269:
                raise HardinessDataError("The USDA snapshot must use NAD83 coordinates.")
            if raster.nodata != -32768:
                raise HardinessDataError("The USDA snapshot has an unexpected no-data value.")
    except rasterio.errors.RasterioIOError as error:
        raise HardinessDataError("The USDA snapshot is not a readable GeoTIFF.") from error

    return HardinessDataset(
        id=f"usda-phzm-2023-{source_sha256[:16]}",
        dataset_kind=DATASET_KIND,
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        source_id=f"sha256:{source_sha256}",
        source_title="2023 USDA Plant Hardiness Zone Map CONUS raster",
        source_path=_relative_source_path(source_path),
        source_url=SOURCE_URL,
        source_publisher="USDA Agricultural Research Service and OSU PRISM Climate Group",
        source_sha256=source_sha256,
        source_media_type="image/tiff",
        source_retrieved_at=RETRIEVED_AT,
        source_license="Creative Commons Attribution 4.0 International",
    )


def sample_hardiness(
    source_path: Path,
    *,
    latitude: float,
    longitude: float,
    expected_sha256: str,
) -> HardinessSample | None:
    if _sha256(source_path) != expected_sha256:
        raise HardinessDataError("The USDA raster checksum does not match the loaded dataset.")

    try:
        with rasterio.open(source_path) as raster:
            if raster.crs is None:
                raise HardinessDataError("The USDA raster has no coordinate reference system.")
            x_values, y_values = transform("EPSG:4326", raster.crs, [longitude], [latitude])
            x, y = x_values[0], y_values[0]
            if not (
                raster.bounds.left <= x < raster.bounds.right
                and raster.bounds.bottom < y <= raster.bounds.top
            ):
                return None

            row, column = raster.index(x, y)
            raster_value = int(raster.read(1, window=Window(column, row, 1, 1))[0, 0])
            if raster.nodata is not None and raster_value == int(raster.nodata):
                return None
    except rasterio.errors.RasterioIOError as error:
        raise HardinessDataError("The loaded USDA raster is not readable.") from error

    return HardinessSample(
        zone=hardiness_zone_from_centi_fahrenheit(raster_value),
        mean_annual_extreme_minimum_f=raster_value / 100,
        raster_value=raster_value,
        row=row,
        column=column,
        source_locator=(
            f"{source_path.name}:band=1,row={row},column={column};"
            f"WGS84={latitude:.6f},{longitude:.6f}"
        ),
    )
