from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac.db_models import (
    Crop,
    Cultivar,
    CultivarDatasetVersion,
    DatasetVersion,
    GardenProfile,
    Wishlist,
    WishlistCandidate,
    WishlistCultivarCandidate,
    WishlistEntry,
)
from kitchen_almanac.services.garden_profile_service import GardenProfileNotFoundError
from kitchen_almanac.services.wishlist_resolver import (
    IntentKind,
    ResolutionMethod,
    ResolutionStatus,
    normalize_term,
    resolve_term,
)


class CatalogUnavailableError(RuntimeError):
    pass


class WishlistNotFoundError(LookupError):
    pass


class InvalidCropSelectionError(ValueError):
    pass


WISHLIST_LOAD_OPTIONS = (
    selectinload(Wishlist.entries).selectinload(WishlistEntry.resolved_crop),
    selectinload(Wishlist.entries)
    .selectinload(WishlistEntry.resolved_cultivar)
    .selectinload(Cultivar.crop),
    selectinload(Wishlist.entries)
    .selectinload(WishlistEntry.candidates)
    .selectinload(WishlistCandidate.crop),
    selectinload(Wishlist.entries)
    .selectinload(WishlistEntry.cultivar_candidates)
    .selectinload(WishlistCultivarCandidate.cultivar)
    .selectinload(Cultivar.crop),
)


def parse_wishlist_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _active_catalogs(
    session: Session,
) -> tuple[DatasetVersion, CultivarDatasetVersion | None]:
    dataset = session.scalar(select(DatasetVersion).where(DatasetVersion.active.is_(True)))
    if dataset is None:
        raise CatalogUnavailableError("Load a crop catalog before building a wishlist.")
    cultivar_dataset = session.scalar(
        select(CultivarDatasetVersion).where(
            CultivarDatasetVersion.active.is_(True),
            CultivarDatasetVersion.crop_dataset_version_id == dataset.id,
        )
    )
    return dataset, cultivar_dataset


def _cultivar_intent(normalized_text: str, crop: Crop) -> str:
    crop_aliases = sorted(
        {
            normalize_term(crop.canonical_name),
            *(normalize_term(alias.alias) for alias in crop.aliases),
        },
        key=len,
        reverse=True,
    )
    return next(
        (
            normalized_text[: -(len(alias) + 1)]
            for alias in crop_aliases
            if normalized_text.endswith(f" {alias}")
        ),
        normalized_text,
    )


def create_wishlist_builder(
    session: Session,
    *,
    garden_profile_id: str,
    name: str = "My garden wishlist",
) -> Wishlist:
    dataset, cultivar_dataset = _active_catalogs(session)
    if session.get(GardenProfile, garden_profile_id) is None:
        raise GardenProfileNotFoundError(garden_profile_id)
    now = datetime.now(UTC)
    wishlist = Wishlist(
        id=str(uuid4()),
        dataset_version_id=dataset.id,
        cultivar_dataset_version_id=cultivar_dataset.id if cultivar_dataset else None,
        garden_profile_id=garden_profile_id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    session.add(wishlist)
    session.commit()
    return get_wishlist(session, wishlist.id)


def create_wishlist(
    session: Session,
    *,
    text: str,
    garden_profile_id: str,
    name: str = "My garden wishlist",
) -> Wishlist:
    dataset, cultivar_dataset = _active_catalogs(session)

    crops = session.scalars(
        select(Crop)
        .where(Crop.dataset_version_id == dataset.id)
        .options(selectinload(Crop.aliases))
        .order_by(Crop.canonical_name)
    ).all()
    if not crops:
        raise CatalogUnavailableError("The active crop catalog is empty.")
    cultivars = (
        session.scalars(
            select(Cultivar)
            .where(
                Cultivar.cultivar_dataset_version_id == cultivar_dataset.id,
                Cultivar.review_status == "approved",
            )
            .options(selectinload(Cultivar.aliases), selectinload(Cultivar.crop))
            .order_by(Cultivar.canonical_name)
        ).all()
        if cultivar_dataset is not None
        else []
    )
    if session.get(GardenProfile, garden_profile_id) is None:
        raise GardenProfileNotFoundError(garden_profile_id)

    now = datetime.now(UTC)
    wishlist = Wishlist(
        id=str(uuid4()),
        dataset_version_id=dataset.id,
        cultivar_dataset_version_id=cultivar_dataset.id if cultivar_dataset else None,
        garden_profile_id=garden_profile_id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    for position, original_text in enumerate(parse_wishlist_lines(text), start=1):
        resolution = resolve_term(original_text, crops, cultivars)
        entry = WishlistEntry(
            id=str(uuid4()),
            position=position,
            original_text=original_text,
            normalized_text=resolution.normalized_text,
            status=resolution.status,
            resolution_method=resolution.method,
            resolved_crop_id=resolution.resolved_crop.id if resolution.resolved_crop else None,
            intent_kind=resolution.intent_kind,
            cultivar_intent_text=resolution.cultivar_intent_text,
            crop_type_intent=resolution.crop_type_intent,
            resolved_cultivar_id=(
                resolution.resolved_cultivar.id if resolution.resolved_cultivar else None
            ),
        )
        entry.candidates = [
            WishlistCandidate(
                crop_id=candidate.crop.id,
                rank=rank,
                score=candidate.score,
                matched_alias=candidate.matched_alias,
            )
            for rank, candidate in enumerate(resolution.candidates, start=1)
        ]
        entry.cultivar_candidates = [
            WishlistCultivarCandidate(
                cultivar_id=candidate.cultivar.id,
                rank=rank,
                score=candidate.score,
                matched_alias=candidate.matched_alias,
            )
            for rank, candidate in enumerate(resolution.cultivar_candidates, start=1)
        ]
        wishlist.entries.append(entry)

    session.add(wishlist)
    session.commit()
    return get_wishlist(session, wishlist.id)


def add_wishlist_entry(
    session: Session,
    *,
    wishlist_id: str,
    original_text: str,
    selection_kind: str,
    crop_slug: str | None,
    cultivar_slug: str | None,
) -> Wishlist:
    wishlist = get_wishlist(session, wishlist_id)
    normalized_text = normalize_term(original_text)
    position = max((entry.position for entry in wishlist.entries), default=0) + 1
    entry = WishlistEntry(
        id=str(uuid4()),
        position=position,
        original_text=original_text,
        normalized_text=normalized_text,
        status=ResolutionStatus.CUSTOM,
        resolution_method=ResolutionMethod.CUSTOM,
        intent_kind=IntentKind.CROP,
    )

    if selection_kind in {"crop", "custom_cultivar"}:
        crop = session.scalar(
            select(Crop).where(
                Crop.dataset_version_id == wishlist.dataset_version_id,
                Crop.slug == crop_slug,
            )
        )
        if crop is None:
            raise InvalidCropSelectionError(crop_slug or "")
        entry.resolved_crop = crop
        if selection_kind == "crop":
            entry.status = ResolutionStatus.RESOLVED
            entry.resolution_method = ResolutionMethod.USER_CONFIRMED
        else:
            entry.intent_kind = IntentKind.CULTIVAR
            entry.cultivar_intent_text = _cultivar_intent(normalized_text, crop)
    elif selection_kind == "cultivar":
        if wishlist.cultivar_dataset_version_id is None:
            raise InvalidCropSelectionError(cultivar_slug or "")
        cultivar = session.scalar(
            select(Cultivar)
            .where(
                Cultivar.cultivar_dataset_version_id == wishlist.cultivar_dataset_version_id,
                Cultivar.slug == cultivar_slug,
                Cultivar.review_status == "approved",
            )
            .options(selectinload(Cultivar.crop).selectinload(Crop.aliases))
        )
        if cultivar is None:
            raise InvalidCropSelectionError(cultivar_slug or "")
        entry.status = ResolutionStatus.RESOLVED
        entry.resolution_method = ResolutionMethod.USER_CONFIRMED
        entry.intent_kind = IntentKind.CULTIVAR
        entry.cultivar_intent_text = _cultivar_intent(normalized_text, cultivar.crop)
        entry.resolved_crop_id = cultivar.crop_id
        entry.resolved_cultivar = cultivar

    wishlist.entries.append(entry)
    wishlist.updated_at = datetime.now(UTC)
    session.commit()
    return get_wishlist(session, wishlist.id)


def get_wishlist(session: Session, wishlist_id: str) -> Wishlist:
    wishlist = session.scalar(
        select(Wishlist).where(Wishlist.id == wishlist_id).options(*WISHLIST_LOAD_OPTIONS)
    )
    if wishlist is None:
        raise WishlistNotFoundError(wishlist_id)
    return wishlist


def get_active_wishlist_for_profile(
    session: Session,
    garden_profile_id: str,
) -> Wishlist | None:
    if session.get(GardenProfile, garden_profile_id) is None:
        raise GardenProfileNotFoundError(garden_profile_id)
    return session.scalar(
        select(Wishlist)
        .where(Wishlist.garden_profile_id == garden_profile_id)
        .options(*WISHLIST_LOAD_OPTIONS)
        .order_by(Wishlist.updated_at.desc(), Wishlist.created_at.desc(), Wishlist.id)
    )


def remove_wishlist_entry(
    session: Session,
    *,
    wishlist_id: str,
    entry_id: str,
) -> Wishlist:
    wishlist = get_wishlist(session, wishlist_id)
    entry = next((item for item in wishlist.entries if item.id == entry_id), None)
    if entry is None:
        raise WishlistNotFoundError(entry_id)

    session.delete(entry)
    session.flush()
    remaining = [item for item in wishlist.entries if item.id != entry_id]
    for temporary_position, item in enumerate(remaining, start=1):
        item.position = -temporary_position
    session.flush()
    for position, item in enumerate(remaining, start=1):
        item.position = position
    wishlist.updated_at = datetime.now(UTC)
    session.commit()
    return get_wishlist(session, wishlist.id)


def update_wishlist_entry(
    session: Session,
    *,
    wishlist_id: str,
    entry_id: str,
    crop_slug: str | None,
    cultivar_slug: str | None,
    keep_custom: bool,
) -> Wishlist:
    wishlist = get_wishlist(session, wishlist_id)
    entry = next((item for item in wishlist.entries if item.id == entry_id), None)
    if entry is None:
        raise WishlistNotFoundError(entry_id)

    if keep_custom:
        entry.status = ResolutionStatus.CUSTOM
        entry.resolution_method = ResolutionMethod.CUSTOM
        entry.resolved_cultivar = None
        if entry.intent_kind == "crop":
            entry.resolved_crop = None
    elif cultivar_slug is not None:
        if wishlist.cultivar_dataset_version_id is None:
            raise InvalidCropSelectionError(cultivar_slug)
        cultivar = session.scalar(
            select(Cultivar).where(
                Cultivar.cultivar_dataset_version_id == wishlist.cultivar_dataset_version_id,
                Cultivar.slug == cultivar_slug,
                Cultivar.review_status == "approved",
            )
        )
        if cultivar is None:
            raise InvalidCropSelectionError(cultivar_slug)
        entry.status = ResolutionStatus.RESOLVED
        entry.resolution_method = ResolutionMethod.USER_CONFIRMED
        entry.intent_kind = "cultivar"
        entry.resolved_cultivar = cultivar
        entry.resolved_crop_id = cultivar.crop_id
    else:
        crop = session.scalar(
            select(Crop).where(
                Crop.dataset_version_id == wishlist.dataset_version_id,
                Crop.slug == crop_slug,
            )
        )
        if crop is None:
            raise InvalidCropSelectionError(crop_slug or "")
        entry.status = ResolutionStatus.RESOLVED
        entry.resolution_method = ResolutionMethod.USER_CONFIRMED
        entry.resolved_crop = crop
        entry.resolved_cultivar = None
        entry.intent_kind = "crop"

    wishlist.updated_at = datetime.now(UTC)
    session.commit()
    return get_wishlist(session, wishlist.id)
