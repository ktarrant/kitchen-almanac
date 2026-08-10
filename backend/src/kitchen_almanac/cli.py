from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from kitchen_almanac import (
    cultivar_catalog,
    cultivar_pipeline,
    hardiness_data,
    location_data,
    noaa_normals_data,
    rutgers_extraction,
    rutgers_inventory,
    rutgers_taxonomy,
)
from kitchen_almanac.catalog import (
    DEFAULT_BROWSE_TAXONOMY_SOURCE,
    DEFAULT_OUTPUT,
    DEFAULT_SOURCE,
    DEFAULT_TAXONOMY_SOURCE,
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
from kitchen_almanac.services.cultivar_repository import (
    CultivarCatalogDependencyError,
    load_cultivar_catalog,
)
from kitchen_almanac.services.hardiness_service import enrich_all_garden_hardiness
from kitchen_almanac.services.location_repository import load_location_dataset
from kitchen_almanac.services.noaa_normals_service import enrich_all_garden_noaa_normals

app = typer.Typer(no_args_is_help=True, help="Kitchen Almanac development and data tools.")
catalog_app = typer.Typer(no_args_is_help=True, help="Build and publish crop catalogs.")
db_app = typer.Typer(no_args_is_help=True, help="Manage the application database.")
location_app = typer.Typer(no_args_is_help=True, help="Validate and load location datasets.")
climate_app = typer.Typer(no_args_is_help=True, help="Validate and load climate evidence.")
cultivar_app = typer.Typer(no_args_is_help=True, help="Validate and load cultivar evidence.")
rutgers_app = typer.Typer(no_args_is_help=True, help="Inventory the primary Rutgers source corpus.")
app.add_typer(catalog_app, name="catalog")
app.add_typer(db_app, name="db")
app.add_typer(location_app, name="locations")
app.add_typer(climate_app, name="climate")
app.add_typer(cultivar_app, name="cultivars")
app.add_typer(rutgers_app, name="rutgers")

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@catalog_app.command("build")
def catalog_build(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_SOURCE,
    output: Annotated[Path, typer.Option(file_okay=True, dir_okay=False)] = DEFAULT_OUTPUT,
    taxonomy: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_TAXONOMY_SOURCE,
    browse_taxonomy: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_BROWSE_TAXONOMY_SOURCE,
) -> None:
    """Build a Rutgers-aligned catalog with retained legacy season metadata."""

    try:
        catalog = build_catalog(source, taxonomy, browse_taxonomy)
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
    taxonomy: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_TAXONOMY_SOURCE,
    browse_taxonomy: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_BROWSE_TAXONOMY_SOURCE,
) -> None:
    """Validate catalog structure, provenance, and current source digest."""

    try:
        catalog = read_catalog(catalog_path)
        errors = validate_catalog(catalog, source, taxonomy, browse_taxonomy)
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
    taxonomy: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_TAXONOMY_SOURCE,
    browse_taxonomy: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = DEFAULT_BROWSE_TAXONOMY_SOURCE,
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Load a validated catalog into an already-migrated database."""

    catalog = read_catalog(catalog_path)
    errors = validate_catalog(catalog, source, taxonomy, browse_taxonomy)
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


@cultivar_app.command("validate")
def cultivar_validate(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_catalog.DEFAULT_SOURCE,
) -> None:
    """Validate the reviewed cultivar evidence snapshot."""

    try:
        catalog = cultivar_catalog.build_cultivar_catalog(source)
    except cultivar_catalog.CultivarCatalogError as error:
        typer.echo(f"Cultivar validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"Cultivar catalog {catalog.id} is valid ({len(catalog.data['cultivars'])} cultivars)."
    )


@cultivar_app.command("fetch")
def cultivar_fetch(
    staged: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_STAGED,
) -> None:
    """Fetch locally retained source documents and verify their reviewed checksums."""

    try:
        fetched, present = cultivar_pipeline.fetch_staged_sources(staged)
    except cultivar_pipeline.CultivarPipelineError as error:
        typer.echo(f"Cultivar source fetch failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Fetched {fetched} source snapshots; {present} already verified.")


@cultivar_app.command("reconcile")
def cultivar_reconcile(
    base: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_BASE,
    staged: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_STAGED,
    decisions: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_DECISIONS,
) -> None:
    """Report exact and possible identity collisions before publication."""

    try:
        base_data = cultivar_pipeline.read_pipeline_json(base, "base cultivar catalog")
        staged_data = cultivar_pipeline.read_pipeline_json(staged, "staged cultivar data")
        decision_data = cultivar_pipeline.read_pipeline_json(
            decisions, "cultivar review decisions"
        )
        errors = [
            *cultivar_pipeline.validate_staged_cultivars(staged_data),
            *cultivar_pipeline.validate_review_decisions(staged_data, decision_data),
        ]
        if errors:
            raise cultivar_pipeline.CultivarPipelineError(" ".join(errors))
        report = cultivar_pipeline.reconcile_candidates(base_data, staged_data, decision_data)
    except cultivar_pipeline.CultivarPipelineError as error:
        typer.echo(f"Cultivar reconciliation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    for item in report:
        matches = ",".join(item.exact_matches) or item.possible_match or "none"
        typer.echo(f"{item.candidate_id}: {item.decision}; identity match={matches}")
    typer.echo(f"Reviewed {len(report)} staged cultivar candidates.")


@cultivar_app.command("publish")
def cultivar_publish(
    base: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_BASE,
    staged: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_STAGED,
    decisions: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_pipeline.DEFAULT_DECISIONS,
    output: Annotated[Path, typer.Option(file_okay=True, dir_okay=False)] = (
        cultivar_pipeline.DEFAULT_OUTPUT
    ),
) -> None:
    """Build the deterministic approved snapshot from reviewed staged evidence."""

    try:
        data = cultivar_pipeline.build_expanded_snapshot(
            base,
            staged,
            decisions,
            verify_snapshots=True,
        )
        cultivar_pipeline.write_expanded_snapshot(data, output)
        catalog = cultivar_catalog.build_cultivar_catalog(output)
    except (
        cultivar_pipeline.CultivarPipelineError,
        cultivar_catalog.CultivarCatalogError,
    ) as error:
        typer.echo(f"Cultivar publication failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Published {len(data['cultivars'])} cultivars to {output}")
    typer.echo(f"Dataset: {catalog.id}")


@cultivar_app.command("load")
def cultivar_load(
    source: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = cultivar_catalog.DEFAULT_SOURCE,
    database_url: Annotated[str | None, typer.Option(envvar="KITCHEN_ALMANAC_DATABASE_URL")] = None,
) -> None:
    """Publish approved cultivar identities, traits, and listings."""

    try:
        catalog = cultivar_catalog.build_cultivar_catalog(source)
    except cultivar_catalog.CultivarCatalogError as error:
        typer.echo(f"Cultivar validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    try:
        with Session(make_engine(database_url)) as session:
            inserted = load_cultivar_catalog(session, catalog)
    except CultivarCatalogDependencyError as error:
        typer.echo(f"Cultivar load failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    action = "Loaded" if inserted else "Already present"
    typer.echo(f"{action}: {catalog.id}")


@rutgers_app.command("fetch")
def rutgers_fetch(
    manifest: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_inventory.DEFAULT_MANIFEST,
) -> None:
    """Fetch checksum-pinned sections of the Rutgers primary corpus."""

    try:
        fetched, present = rutgers_inventory.fetch_sources(manifest)
    except rutgers_inventory.RutgersInventoryError as error:
        typer.echo(f"Rutgers source fetch failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Fetched {fetched} Rutgers source snapshots; {present} already verified.")


@rutgers_app.command("inventory")
def rutgers_build_inventory(
    manifest: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_inventory.DEFAULT_MANIFEST,
    output: Annotated[Path, typer.Option(file_okay=True, dir_okay=False)] = (
        rutgers_inventory.DEFAULT_REPORT
    ),
) -> None:
    """Build a deterministic, review-only coverage report from retained PDFs."""

    try:
        report = rutgers_inventory.build_coverage_report(manifest)
        rutgers_inventory.write_coverage_report(report, output)
    except rutgers_inventory.RutgersInventoryError as error:
        typer.echo(f"Rutgers inventory failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    summary = report["summary"]
    typer.echo(
        f"Inventoried {summary['document_count']} documents and {summary['page_count']} pages "
        f"for {summary['crop_count']} crops."
    )
    typer.echo(f"Wrote review-only coverage report to {output}")


@rutgers_app.command("extract")
def rutgers_extract_evidence(
    manifest: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_inventory.DEFAULT_MANIFEST,
    output: Annotated[Path, typer.Option(file_okay=True, dir_okay=False)] = (
        rutgers_extraction.DEFAULT_STAGED
    ),
) -> None:
    """Extract deterministic, review-gated evidence candidates from the corpus."""

    try:
        staged = rutgers_extraction.build_structured_evidence(manifest)
        rutgers_extraction.write_structured_evidence(staged, output)
    except (
        rutgers_inventory.RutgersInventoryError,
        rutgers_extraction.RutgersExtractionError,
    ) as error:
        typer.echo(f"Rutgers structured extraction failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Extracted {len(staged['candidates'])} review candidates to {output}")


@rutgers_app.command("taxonomy")
def rutgers_build_taxonomy_coverage(
    manifest: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_inventory.DEFAULT_MANIFEST,
    crosswalk: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_taxonomy.DEFAULT_CROSSWALK,
    output: Annotated[Path, typer.Option(file_okay=True, dir_okay=False)] = (
        rutgers_taxonomy.DEFAULT_REPORT
    ),
) -> None:
    """Build full-manual commodity taxonomy and minimum-evidence coverage."""

    try:
        report = rutgers_taxonomy.build_taxonomy_coverage_report(
            manifest_path=manifest,
            crosswalk_path=crosswalk,
        )
        rutgers_taxonomy.write_taxonomy_coverage_report(report, output)
    except rutgers_taxonomy.RutgersTaxonomyError as error:
        typer.echo(f"Rutgers taxonomy inventory failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    summary = report["summary"]
    typer.echo(
        f"Mapped {summary['rutgers_crop_concept_count']} crop concepts from "
        f"{summary['commodity_section_count']} commodity sections."
    )
    typer.echo(
        f"Exact: {summary['mapping_status_counts']['exact']}; "
        f"needs split: {summary['mapping_status_counts'].get('broader_catalog_identity', 0)}; "
        f"missing: {summary['mapping_status_counts'].get('missing_catalog_identity', 0)}."
    )
    typer.echo(f"Wrote taxonomy coverage report to {output}")


@rutgers_app.command("validate")
def rutgers_validate_inventory(
    report: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_inventory.DEFAULT_REPORT,
    manifest: Annotated[
        Path, typer.Option(exists=True, file_okay=True, dir_okay=False)
    ] = rutgers_inventory.DEFAULT_MANIFEST,
) -> None:
    """Verify corpus checksums and the committed deterministic coverage report."""

    try:
        errors = [
            *rutgers_inventory.validate_coverage_report(report, manifest),
            *rutgers_extraction.validate_committed_extraction(manifest_path=manifest),
            *rutgers_taxonomy.validate_committed_taxonomy_report(manifest_path=manifest),
        ]
    except (
        rutgers_inventory.RutgersInventoryError,
        rutgers_extraction.RutgersExtractionError,
        rutgers_taxonomy.RutgersTaxonomyError,
    ) as error:
        typer.echo(f"Rutgers inventory validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    if errors:
        for error in errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        "Rutgers corpus, page coverage, taxonomy coverage, structured evidence, and review "
        "are valid."
    )


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
