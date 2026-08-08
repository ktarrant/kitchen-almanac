from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from kitchen_almanac import hardiness_data, location_data, noaa_normals_data
from kitchen_almanac.catalog import (
    DEFAULT_OUTPUT,
    DEFAULT_SOURCE,
    CatalogError,
    build_catalog,
    read_catalog,
    validate_catalog,
    write_catalog,
)
from kitchen_almanac.database import make_engine
from kitchen_almanac.services.catalog_repository import load_catalog
from kitchen_almanac.services.climate_repository import (
    load_hardiness_dataset,
    load_noaa_normals_dataset,
)
from kitchen_almanac.services.hardiness_service import enrich_all_garden_hardiness
from kitchen_almanac.services.location_repository import load_location_dataset
from kitchen_almanac.services.noaa_normals_service import enrich_all_garden_noaa_normals

app = typer.Typer(no_args_is_help=True, help="Kitchen Almanac development and data tools.")
catalog_app = typer.Typer(no_args_is_help=True, help="Build and publish crop catalogs.")
db_app = typer.Typer(no_args_is_help=True, help="Manage the application database.")
location_app = typer.Typer(no_args_is_help=True, help="Validate and load location datasets.")
climate_app = typer.Typer(no_args_is_help=True, help="Validate and load climate evidence.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(db_app, name="db")
app.add_typer(location_app, name="locations")
app.add_typer(climate_app, name="climate")

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@catalog_app.command("build")
def catalog_build(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_SOURCE,
    output: Annotated[Path, typer.Option(file_okay=True, dir_okay=False)] = DEFAULT_OUTPUT,
) -> None:
    """Build a deterministic catalog from the seasonal Markdown reference."""

    try:
        catalog = build_catalog(source)
        write_catalog(catalog, output)
    except CatalogError as error:
        typer.echo(f"Catalog build failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Wrote {len(catalog['crops'])} crops to {output}")
    typer.echo(f"Dataset: {catalog['dataset_id']}")


@catalog_app.command("validate")
def catalog_validate(
    catalog_path: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_OUTPUT,
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_SOURCE,
) -> None:
    """Validate catalog structure, provenance, and current source digest."""

    try:
        catalog = read_catalog(catalog_path)
        errors = validate_catalog(catalog, source)
    except CatalogError as error:
        typer.echo(f"Catalog validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    if errors:
        for error in errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Catalog {catalog['dataset_id']} is valid ({len(catalog['crops'])} crops).")


@catalog_app.command("load")
def catalog_load(
    catalog_path: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_OUTPUT,
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_SOURCE,
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Load a validated catalog into an already-migrated database."""

    catalog = read_catalog(catalog_path)
    errors = validate_catalog(catalog, source)
    if errors:
        for error in errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=1)

    with Session(make_engine(database_url)) as session:
        inserted = load_catalog(session, catalog)
    action = "Loaded" if inserted else "Already present"
    typer.echo(f"{action}: {catalog['dataset_id']}")


@location_app.command("validate")
def location_validate(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = location_data.DEFAULT_SOURCE,
) -> None:
    """Validate the snapshotted Census postal-area coordinate source."""

    try:
        dataset = location_data.build_location_dataset(source)
    except location_data.LocationDataError as error:
        typer.echo(f"Location validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Location dataset {dataset.id} is valid ({len(dataset.locations)} ZCTAs).")


@location_app.command("load")
def location_load(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = location_data.DEFAULT_SOURCE,
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Load the validated Census postal-area coordinates into the database."""

    try:
        dataset = location_data.build_location_dataset(source)
    except location_data.LocationDataError as error:
        typer.echo(f"Location validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    with Session(make_engine(database_url)) as session:
        inserted = load_location_dataset(session, dataset)
    action = "Loaded" if inserted else "Already present"
    typer.echo(f"{action}: {dataset.id}")


@climate_app.command("validate-hardiness")
def hardiness_validate(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = hardiness_data.DEFAULT_SOURCE,
) -> None:
    """Validate the snapshotted 2023 USDA hardiness raster."""

    try:
        dataset = hardiness_data.build_hardiness_dataset(source)
    except hardiness_data.HardinessDataError as error:
        typer.echo(f"Hardiness validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Hardiness dataset {dataset.id} is valid.")


@climate_app.command("load-hardiness")
def hardiness_load(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = hardiness_data.DEFAULT_SOURCE,
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Load USDA hardiness evidence and enrich existing garden profiles."""

    try:
        dataset = hardiness_data.build_hardiness_dataset(source)
    except hardiness_data.HardinessDataError as error:
        typer.echo(f"Hardiness validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    with Session(make_engine(database_url)) as session:
        inserted = load_hardiness_dataset(session, dataset)
        enriched = enrich_all_garden_hardiness(session)
    action = "Loaded" if inserted else "Already present"
    typer.echo(f"{action}: {dataset.id}; enriched {enriched} garden profiles.")


@climate_app.command("validate-noaa")
def noaa_validate(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = noaa_normals_data.DEFAULT_SOURCE,
) -> None:
    """Validate the snapshotted NOAA 1991–2020 station normals."""

    try:
        dataset = noaa_normals_data.build_noaa_normals_dataset(source)
    except noaa_normals_data.NoaaNormalsDataError as error:
        typer.echo(f"NOAA normals validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"NOAA normals dataset {dataset.id} is valid ({len(dataset.stations)} stations).")


@climate_app.command("load-noaa")
def noaa_load(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = noaa_normals_data.DEFAULT_SOURCE,
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Load NOAA normals and enrich existing garden profiles."""

    try:
        dataset = noaa_normals_data.build_noaa_normals_dataset(source)
    except noaa_normals_data.NoaaNormalsDataError as error:
        typer.echo(f"NOAA normals validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    with Session(make_engine(database_url)) as session:
        inserted = load_noaa_normals_dataset(session, dataset)
        enriched = enrich_all_garden_noaa_normals(session)
    action = "Loaded" if inserted else "Already present"
    typer.echo(f"{action}: {dataset.id}; enriched {enriched} garden profiles.")


@db_app.command("upgrade")
def db_upgrade(
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Apply all database migrations."""

    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    if database_url:
        alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")
    typer.echo("Database is at the latest revision.")


if __name__ == "__main__":
    app()
