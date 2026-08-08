from __future__ import annotations

import csv
import hashlib
import io
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
PARSER_VERSION = "1.0.0"
DATASET_KIND = "noaa_normals_1991_2020"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = (
    REPOSITORY_ROOT / "data/source/noaa/normals-1991-2020/annualseasonal-by-station-v1.0.1.tar.gz"
)
SOURCE_URL = (
    "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/archive/"
    "us-climate-normals_1991-2020_v1.0.1_annualseasonal_multivariate_by-station_"
    "c20230404.tar.gz"
)
README_SHA256 = "feb4e1dd5914c8d35eccd017e114c6e5d352b1e217602cb622a67ad6670c3c21"
RETRIEVED_AT = datetime(2026, 8, 8, tzinfo=UTC)

VARIABLES = (
    "ANN-TAVG-NORMAL",
    "ANN-TMIN-NORMAL",
    "ANN-TMAX-NORMAL",
    "ANN-PRCP-NORMAL",
    "ANN-GRDD-BASE50",
    "ANN-TMIN-PRBLST-T32FP50",
    "ANN-TMIN-PRBFST-T32FP50",
    "ANN-TMIN-PRBGSL-T32FP50",
)
COMPLETENESS_RANK = {"S": 0, "R": 1, "P": 2, "E": 3}
REJECTED_MEASUREMENT_FLAGS = {"M", "V", "Y", "Z"}


class NoaaNormalsDataError(ValueError):
    """Raised when the pinned NOAA normals snapshot is invalid."""


@dataclass(frozen=True)
class NoaaStationNormal:
    station_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float | None
    annual_mean_f: float
    annual_minimum_f: float
    annual_maximum_f: float
    annual_precipitation_in: float
    growing_degree_days_base_50_f: float
    last_spring_frost_50: str
    first_fall_frost_50: str
    growing_season_days_50: int
    completeness_class: str
    minimum_years: int
    source_locator: str


@dataclass(frozen=True)
class NoaaNormalsDataset:
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
    stations: tuple[NoaaStationNormal, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_source_path(source_path: Path) -> str:
    try:
        return source_path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return source_path.name


def _clean(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def _valid_date(value: str) -> bool:
    try:
        datetime.strptime(f"2000/{value}", "%Y/%m/%d")
    except ValueError:
        return False
    return True


def _parse_station(row: dict[str, str], locator: str) -> NoaaStationNormal | None:
    if any(not _clean(row, variable) for variable in VARIABLES):
        return None
    if any(
        _clean(row, f"meas_flag_{variable}") in REJECTED_MEASUREMENT_FLAGS for variable in VARIABLES
    ):
        return None

    completeness = [_clean(row, f"comp_flag_{variable}") for variable in VARIABLES]
    if any(value not in COMPLETENESS_RANK for value in completeness):
        return None

    try:
        years = [int(_clean(row, f"years_{variable}")) for variable in VARIABLES]
        last_frost = _clean(row, "ANN-TMIN-PRBLST-T32FP50")
        first_frost = _clean(row, "ANN-TMIN-PRBFST-T32FP50")
        if not _valid_date(last_frost) or not _valid_date(first_frost):
            return None
        station_id = _clean(row, "STATION")
        if not station_id:
            return None
        elevation = _clean(row, "ELEVATION")
        return NoaaStationNormal(
            station_id=station_id,
            name=_clean(row, "NAME"),
            latitude=float(_clean(row, "LATITUDE")),
            longitude=float(_clean(row, "LONGITUDE")),
            elevation_m=float(elevation) if elevation else None,
            annual_mean_f=float(_clean(row, "ANN-TAVG-NORMAL")),
            annual_minimum_f=float(_clean(row, "ANN-TMIN-NORMAL")),
            annual_maximum_f=float(_clean(row, "ANN-TMAX-NORMAL")),
            annual_precipitation_in=float(_clean(row, "ANN-PRCP-NORMAL")),
            growing_degree_days_base_50_f=float(_clean(row, "ANN-GRDD-BASE50")),
            last_spring_frost_50=last_frost,
            first_fall_frost_50=first_frost,
            growing_season_days_50=round(float(_clean(row, "ANN-TMIN-PRBGSL-T32FP50"))),
            completeness_class=max(completeness, key=COMPLETENESS_RANK.__getitem__),
            minimum_years=min(years),
            source_locator=locator,
        )
    except (TypeError, ValueError):
        return None


def build_noaa_normals_dataset(source_path: Path = DEFAULT_SOURCE) -> NoaaNormalsDataset:
    """Validate and normalize the pinned national NOAA station archive."""

    source_path = source_path.resolve()
    if not source_path.is_file():
        raise NoaaNormalsDataError(f"NOAA normals archive not found: {source_path}")
    readme_path = source_path.with_name("README.txt")
    if not readme_path.is_file() or _sha256(readme_path) != README_SHA256:
        raise NoaaNormalsDataError("NOAA normals README is missing or has changed.")

    source_sha = _sha256(source_path)
    stations: dict[str, NoaaStationNormal] = {}
    try:
        with tarfile.open(source_path, "r:gz") as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith(".csv"):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                with io.TextIOWrapper(stream, encoding="utf-8-sig", newline="") as text_stream:
                    row = next(csv.DictReader(text_stream), None)
                if row is None:
                    continue
                station = _parse_station(row, member.name)
                if station is None:
                    continue
                if station.station_id in stations:
                    raise NoaaNormalsDataError(f"Duplicate station: {station.station_id}")
                stations[station.station_id] = station
    except (csv.Error, OSError, tarfile.TarError) as error:
        raise NoaaNormalsDataError(f"Could not parse NOAA normals archive: {error}") from error

    if not stations:
        raise NoaaNormalsDataError("NOAA normals archive has no qualifying stations.")

    dataset_id = f"noaa-normals-1991-2020-{source_sha[:16]}"
    return NoaaNormalsDataset(
        id=dataset_id,
        dataset_kind=DATASET_KIND,
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        source_id=f"source-{dataset_id}",
        source_title="U.S. Climate Normals 1991–2020, Annual/Seasonal by Station v1.0.1",
        source_path=_relative_source_path(source_path),
        source_url=SOURCE_URL,
        source_publisher="NOAA National Centers for Environmental Information",
        source_sha256=source_sha,
        source_media_type="application/gzip",
        source_retrieved_at=RETRIEVED_AT,
        source_license="U.S. Government public data; dataset citation required",
        stations=tuple(stations[key] for key in sorted(stations)),
    )
