from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac.db_models import (
    Crop,
    DatasetVersion,
    Wishlist,
    WishlistCandidate,
    WishlistEntry,
)
from kitchen_almanac.services.wishlist_resolver import (
    ResolutionMethod,
    ResolutionStatus,
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
    .selectinload(WishlistEntry.candidates)
    .selectinload(WishlistCandidate.crop),
)


def parse_wishlist_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def create_wishlist(
    session: Session,
    *,
    text: str,
    name: str = "My garden wishlist",
) -> Wishlist:
    dataset = session.scalar(select(DatasetVersion).where(DatasetVersion.active.is_(True)))
    if dataset is None:
        raise CatalogUnavailableError("Load a crop catalog before resolving a wishlist.")

    crops = session.scalars(
        select(Crop)
        .where(Crop.dataset_version_id == dataset.id)
        .options(selectinload(Crop.aliases))
        .order_by(Crop.canonical_name)
    ).all()
    if not crops:
        raise CatalogUnavailableError("The active crop catalog is empty.")

    now = datetime.now(UTC)
    wishlist = Wishlist(
        id=str(uuid4()),
        dataset_version_id=dataset.id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    for position, original_text in enumerate(parse_wishlist_lines(text), start=1):
        resolution = resolve_term(original_text, crops)
        entry = WishlistEntry(
            id=str(uuid4()),
            position=position,
            original_text=original_text,
            normalized_text=resolution.normalized_text,
            status=resolution.status,
            resolution_method=resolution.method,
            resolved_crop_id=resolution.resolved_crop.id if resolution.resolved_crop else None,
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
        wishlist.entries.append(entry)

    session.add(wishlist)
    session.commit()
    return get_wishlist(session, wishlist.id)


def get_wishlist(session: Session, wishlist_id: str) -> Wishlist:
    wishlist = session.scalar(
        select(Wishlist).where(Wishlist.id == wishlist_id).options(*WISHLIST_LOAD_OPTIONS)
    )
    if wishlist is None:
        raise WishlistNotFoundError(wishlist_id)
    return wishlist


def update_wishlist_entry(
    session: Session,
    *,
    wishlist_id: str,
    entry_id: str,
    crop_slug: str | None,
    keep_custom: bool,
) -> Wishlist:
    wishlist = get_wishlist(session, wishlist_id)
    entry = next((item for item in wishlist.entries if item.id == entry_id), None)
    if entry is None:
        raise WishlistNotFoundError(entry_id)

    if keep_custom:
        entry.status = ResolutionStatus.CUSTOM
        entry.resolution_method = ResolutionMethod.CUSTOM
        entry.resolved_crop = None
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

    wishlist.updated_at = datetime.now(UTC)
    session.commit()
    return get_wishlist(session, wishlist.id)
