from __future__ import annotations

from kitchen_almanac.noaa_normals_data import build_noaa_normals_dataset


def test_pinned_noaa_normals_snapshot_is_reproducible() -> None:
    dataset = build_noaa_normals_dataset()

    assert dataset.id == "noaa-normals-1991-2020-0fdb814203150780"
    assert dataset.source_path == (
        "data/source/noaa/normals-1991-2020/annualseasonal-by-station-v1.0.1.tar.gz"
    )
    assert len(dataset.stations) == 6402
    assert [station.station_id for station in dataset.stations] == sorted(
        station.station_id for station in dataset.stations
    )

    station = next(station for station in dataset.stations if station.station_id == "USW00013743")
    assert station.name == "WASHINGTON REAGAN AP, VA US"
    assert station.annual_mean_f == 59.3
    assert station.annual_precipitation_in == 41.82
    assert station.growing_degree_days_base_50_f == 4709.0
    assert station.last_spring_frost_50 == "03/24"
    assert station.first_fall_frost_50 == "11/18"
    assert station.growing_season_days_50 == 241
    assert station.completeness_class == "S"
    assert station.minimum_years == 25
