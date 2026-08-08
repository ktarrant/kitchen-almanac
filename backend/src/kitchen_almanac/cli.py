from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from kitchen_almanac import location_data
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
from kitchen_almanac.services.location_repository import load_location_dataset

app = typer.Typer(no_args_is_help=True, help="Kitchen Almanac development and data tools.")
catalog_app = typer.Typer(no_args_is_help=True, help="Build and publish crop catalogs.")
db_app = typer.Typer(no_args_is_help=True, help="Manage the application database.")
location_app = typer.Typer(no_args_is_help=True, help="Validate and load location datasets.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(db_app, name="db")
app.add_typer(location_app, name="locations")

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
